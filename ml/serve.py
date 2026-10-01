from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import numpy as np
import joblib
import json
import os
import re

# ── Load models ──
MODEL_DIR = "models"
DATA_DIR  = "data/processed"

print("Loading RF model...")
rf_model     = joblib.load(os.path.join(MODEL_DIR, "rf_binary.pkl"))
scaler       = joblib.load(os.path.join(DATA_DIR,  "scaler.pkl"))
feature_cols = joblib.load(os.path.join(DATA_DIR,  "feature_cols.pkl"))

print("Loading ATT&CK index...")
vectorizer    = joblib.load(os.path.join(MODEL_DIR, "attck_vectorizer.pkl"))
tfidf_matrix  = joblib.load(os.path.join(MODEL_DIR, "attck_tfidf_matrix.pkl"))
tech_records  = joblib.load(os.path.join(MODEL_DIR, "attck_tech_records.pkl"))

with open(os.path.join(MODEL_DIR, "attck_version.json")) as f:
    attck_version = json.load(f)

print("All models loaded!")

# ── FastAPI ──
app = FastAPI(title="AI Service — Incident Response Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Schemas ──
class NetworkFeatures(BaseModel):
    features: dict   # {feature_name: value}

class ClassifyResponse(BaseModel):
    is_attack: bool
    attack_probability: float
    severity_suggestion: str
    zone: str          # auto_close / review / urgent
    ai_generated: bool = True
    model_version: str = "rf_binary_v1"

class AttckRequest(BaseModel):
    description: str
    top_k: Optional[int] = 5

class AttckResult(BaseModel):
    rank: int
    id: str
    name: str
    tactics: List[str]
    description: str
    url: str
    score: float

class AttckResponse(BaseModel):
    query: str
    results: List[AttckResult]
    attck_version: str
    ai_generated: bool = True

class AlertSuggestRequest(BaseModel):
    title: str
    description: Optional[str] = ""
    ioc: Optional[str] = ""
    source: Optional[str] = ""

class AlertSuggestResponse(BaseModel):
    severity_suggestion: str
    attck_techniques: List[AttckResult]
    summary: str
    ai_generated: bool = True
    warning: str = "Nội dung do AI tạo — cần Analyst xác nhận trước khi sử dụng"

# ── Helpers ──
THRESHOLDS = {"auto_close": 0.15, "review": 0.50, "urgent": 0.80}

def get_zone(prob: float) -> str:
    if prob < THRESHOLDS["auto_close"]:
        return "auto_close"
    elif prob < THRESHOLDS["urgent"]:
        return "review"
    return "urgent"

def get_severity(prob: float) -> str:
    if prob < 0.15: return "info"
    elif prob < 0.50: return "low"
    elif prob < 0.70: return "medium"
    elif prob < 0.90: return "high"
    return "critical"

def sanitize_input(text: str) -> str:
    """Chống prompt injection — lọc các pattern nguy hiểm."""
    dangerous_patterns = [
        r"ignore previous instructions",
        r"system prompt",
        r"<\|.*?\|>",
        r"\[INST\]",
        r"###\s*instruction",
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            raise HTTPException(400, "Input chứa nội dung không hợp lệ")
    # Giới hạn độ dài
    return text[:2000]

def search_attck(query: str, top_k: int = 5) -> list:
    from sklearn.metrics.pairwise import cosine_similarity
    query_vec = vectorizer.transform([query])
    scores    = cosine_similarity(query_vec, tfidf_matrix).flatten()
    candidate_indices = np.argsort(scores)[::-1][:20]

    query_lower = query.lower()
    results = []
    tactic_boost = {
        "brute force": "credential-access",
        "phishing": "initial-access",
        "scan": "discovery",
        "lateral": "lateral-movement",
        "exfil": "exfiltration",
        "malware": "execution",
        "persistence": "persistence",
        "privilege": "privilege-escalation",
    }
    for idx in candidate_indices:
        tech  = tech_records[idx]
        score = float(scores[idx])
        if tech["name"].lower() in query_lower:
            score *= 1.5
        for kw, tactic in tactic_boost.items():
            if kw in query_lower and tactic in tech["tactics"]:
                score *= 1.2
                break
        results.append({**tech, "score": round(score, 4), "rank": 0})

    results.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1
    return results[:top_k]

# ── Endpoints ──

@app.get("/")
def root():
    return {
        "service": "AI Service",
        "models": ["rf_binary_v1", f"attck_{attck_version['version']}"],
        "status": "ready"
    }

@app.post("/classify", response_model=ClassifyResponse)
def classify_alert(payload: NetworkFeatures):
    """Phân loại cảnh báo mạng — trả về xác suất tấn công và mức độ."""
    # Build feature vector theo đúng thứ tự
    feature_vec = []
    for col in feature_cols:
        val = payload.features.get(col, 0)
        try:
            val = float(val)
        except (ValueError, TypeError):
            val = 0.0
        # Lọc giá trị vô cực
        if not np.isfinite(val):
            val = 0.0
        feature_vec.append(val)

    X = np.array([feature_vec])
    X_scaled = scaler.transform(X)
    prob = float(rf_model.predict_proba(X_scaled)[0][1])

    return ClassifyResponse(
        is_attack=prob >= THRESHOLDS["review"],
        attack_probability=round(prob, 4),
        severity_suggestion=get_severity(prob),
        zone=get_zone(prob),
    )

@app.post("/attck/search", response_model=AttckResponse)
def search_techniques(payload: AttckRequest):
    """Ánh xạ mô tả sự cố sang MITRE ATT&CK techniques."""
    query = sanitize_input(payload.description)
    results = search_attck(query, top_k=min(payload.top_k or 5, 10))
    return AttckResponse(
        query=query,
        results=results,
        attck_version=attck_version["version"],
    )

@app.post("/alert/suggest", response_model=AlertSuggestResponse)
def suggest_for_alert(payload: AlertSuggestRequest):
    """
    Từ thông tin alert (title, description, ioc) →
    đề xuất mức độ và ATT&CK techniques.
    Nội dung AI tạo được đánh dấu rõ.
    """
    # Sanitize tất cả input trước khi xử lý
    title       = sanitize_input(payload.title)
    description = sanitize_input(payload.description or "")
    ioc         = sanitize_input(payload.ioc or "")

    # Ghép query từ các thông tin alert
    query = f"{title}. {description}. IOC: {ioc}".strip()

    # ATT&CK retrieval
    techniques = search_attck(query, top_k=5)

    # Severity dựa trên keyword đơn giản (không dùng network features)
    severity = "medium"
    critical_kw = ["ransomware", "encrypt", "locked", "data exfil"]
    high_kw     = ["brute force", "phishing", "injection", "sql",
                   "malware", "backdoor", "attack", "intrusion",
                   "elevated privileges", "ddos"]
    low_kw      = ["info", "recon"]

    query_lower = query.lower()
    if any(k in query_lower for k in critical_kw):
        severity = "critical"
    elif any(k in query_lower for k in high_kw):
        severity = "high"
    elif any(k in query_lower for k in low_kw):
        severity = "low"
    # else: medium (default)

    query_lower = query.lower()
    if any(k in query_lower for k in critical_kw):
        severity = "critical"
    elif any(k in query_lower for k in high_kw):
        severity = "high"
    elif any(k in query_lower for k in medium_kw):
        severity = "medium"
    elif any(k in query_lower for k in low_kw):
        severity = "low"

    # Tóm tắt ngắn
    top_techs = ", ".join(f"{t['id']} ({t['name']})" for t in techniques[:3])
    summary = (
        f"[AI] Alert '{title}' có thể liên quan đến: {top_techs}. "
        f"Mức độ đề xuất: {severity.upper()}. "
        f"Analyst cần xác nhận trước khi xử lý."
    )

    return AlertSuggestResponse(
        severity_suggestion=severity,
        attck_techniques=techniques,
        summary=summary,
    )