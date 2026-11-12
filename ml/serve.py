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
DATA_DIR  = "data/ids/processed"

print("Loading RF model...")
rf_model     = joblib.load(os.path.join(MODEL_DIR, "rf_binary.pkl"))
scaler       = joblib.load(os.path.join(DATA_DIR,  "scaler.pkl"))
feature_cols = joblib.load(os.path.join(DATA_DIR,  "feature_cols.pkl"))

email_model, email_coef = None, None
_email_path = os.path.join(MODEL_DIR, "email_svm.pkl")
if os.path.isfile(_email_path):
    print("Loading email model...")
    email_model = joblib.load(_email_path)
    _cal = email_model.steps[1][1]
    email_coef = np.mean([c.estimator.coef_[0] for c in _cal.calibrated_classifiers_], axis=0)
else:
    print("Không thấy models/email_svm.pkl: /classify_email sẽ trả 503 (chạy python train_email.py để tạo)")

network_multi, network_labels = None, None
_multi_path = os.path.join(MODEL_DIR, "rf_multiclass.pkl")
_labels_path = os.path.join(MODEL_DIR, "network_labels.json")
if os.path.isfile(_multi_path) and os.path.isfile(_labels_path):
    print("Loading multiclass RF model...")
    network_multi = joblib.load(_multi_path)
    with open(_labels_path, encoding="utf-8") as _f:
        network_labels = json.load(_f)
else:
    print("Không thấy rf_multiclass.pkl: /predict/batch dùng mô hình nhị phân (nhãn BENIGN/ATTACK)")

# ATT&CK là tùy chọn: bản v2 của backend không dùng; thiếu module hoặc chỉ mục thì bỏ qua
searcher, attck_version = None, {"version": "none"}
try:
    print("Loading ATT&CK index...")
    from attck_search import Searcher
    searcher      = Searcher(MODEL_DIR)
    attck_version = searcher.version
except Exception as _e:
    print(f"Bỏ qua ATT&CK ({_e.__class__.__name__}: {_e}); các endpoint /attck và /alert/suggest sẽ trả 503")

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

class FeatureContribution(BaseModel):
    name: str
    value: float
    importance: float   # độ quan trọng toàn cục của đặc trưng trong rừng cây
    score: float        # importance × |giá trị đã chuẩn hóa|: mức nổi bật của đặc trưng với luồng này

class ClassifyResponse(BaseModel):
    is_attack: bool
    attack_probability: float
    severity_suggestion: str
    zone: str          # auto_close / review / urgent
    top_features: List[FeatureContribution] = []
    ai_generated: bool = True
    model_version: str = "rf_binary_v1"

class EmailRequest(BaseModel):
    subject: str = ""
    body: str
    has_html: bool = False
    attachments: List[str] = []

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

def strip_indicators(text: str) -> str:
    text = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", " ", text)
    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"\b[\w-]+(?:\.[\w-]+)+\b", " ", text)
    return text

def search_attck(query: str, top_k: int = 5) -> list:
    if searcher is None:
        raise HTTPException(503, "Chưa có chỉ mục ATT&CK (attck_search.py hoặc models/attck_*)")
    return searcher.search(query, top_k)

# ── Endpoints ──

@app.get("/")
def root():
    return {
        "service": "AI Service",
        "models": ["rf_binary_v1"] + (["email_svm_v1"] if email_model is not None else []) + [f"attck_{attck_version['version']}"],
        "attck_version": attck_version["version"],
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

    importances = rf_model.feature_importances_
    contrib = importances * np.abs(X_scaled[0])
    top = [
        FeatureContribution(
            name=str(feature_cols[i]).strip(), value=round(feature_vec[i], 4),
            importance=round(float(importances[i]), 4), score=round(float(contrib[i]), 4),
        )
        for i in np.argsort(-contrib)[:5] if contrib[i] > 0
    ]

    return ClassifyResponse(
        is_attack=prob >= THRESHOLDS["review"],
        attack_probability=round(prob, 4),
        severity_suggestion=get_severity(prob),
        zone=get_zone(prob),
        top_features=top,
    )

@app.post("/classify_email", response_model=ClassifyResponse)
def classify_email(payload: EmailRequest):
    """Phân loại thư spam hoặc phishing theo nội dung (TF-IDF và Linear SVM đã hiệu chỉnh xác suất)."""
    if email_model is None:
        raise HTTPException(503, "Chưa có mô hình email (models/email_svm.pkl)")
    from email_features import URL_RE, to_text
    body = payload.body[:30000]
    text = to_text({"subject": payload.subject[:500], "body": body, "urls": URL_RE.findall(body),
                    "has_html": payload.has_html, "attachments": payload.attachments})
    prob = float(email_model.predict_proba([text])[0][1])
    vec = email_model.steps[0][1]
    x = vec.transform([text])
    names = vec.get_feature_names_out()
    contrib = x.multiply(email_coef).tocoo()
    items = sorted(zip(contrib.col, contrib.data, x[0, contrib.col].toarray()[0]), key=lambda t: -t[1])[:5]
    top = [FeatureContribution(name=str(names[c]), value=round(float(v), 4), importance=round(float(email_coef[c]), 4),
                               score=round(float(sc), 4)) for c, sc, v in items if sc > 0]
    return ClassifyResponse(
        is_attack=prob >= THRESHOLDS["review"],
        attack_probability=round(prob, 4),
        severity_suggestion=get_severity(prob),
        zone=get_zone(prob),
        top_features=top,
        model_version="email_svm_v1",
    )

# ── Phân loại theo lô cho backend quản lý sự cố ──
NETWORK_VERSION = "rf_multiclass_v1" if network_multi is not None else "rf_binary_v1"
EMAIL_VERSION = "email_svm_v1"
_feature_names = [str(c) for c in feature_cols]
_feature_lookup = {name.strip().casefold(): name for name in _feature_names}

class BatchRequest(BaseModel):
    task_type: str
    rows: List[dict]

def _to_float(v) -> float:
    try:
        x = float(v)
    except (ValueError, TypeError):
        return 0.0
    return x if np.isfinite(x) else 0.0

def _predict_network(rows: List[dict]):
    X = np.zeros((len(rows), len(feature_cols)))
    for i, row in enumerate(rows):
        by_name = {}
        for k, v in row.items():
            name = _feature_lookup.get(str(k).strip().casefold())
            if name is not None:
                by_name[name] = v
        for j, col in enumerate(_feature_names):
            X[i, j] = _to_float(by_name.get(col, 0))
    Xs = scaler.transform(X)
    if network_multi is not None:
        proba = network_multi.predict_proba(Xs)
        classes = [network_labels[int(c)] for c in network_multi.classes_]
    else:
        proba = rf_model.predict_proba(Xs)
        classes = ["BENIGN", "ATTACK"]
    best = proba.argmax(axis=1)
    return [{"label": classes[b], "confidence": round(float(proba[i, b]), 4)} for i, b in enumerate(best)]

def _predict_email(rows: List[dict]):
    from email_features import URL_RE, to_text
    texts = []
    for r in rows:
        body = str(r.get("body", ""))[:30000]
        urls = URL_RE.findall(body)
        urls += [u for u in (r.get("urls") or []) if u not in urls]
        texts.append(to_text({"subject": str(r.get("subject", ""))[:500], "body": body, "urls": urls,
                              "has_html": False, "attachments": []}))
    spam = email_model.predict_proba(texts)[:, 1]
    return [{"label": "SPAM" if p >= 0.5 else "NON_SPAM", "confidence": round(float(max(p, 1 - p)), 4)} for p in spam]

@app.get("/info")
def info():
    """Danh sách mô hình đang chạy, nhãn và cột đầu vào, để backend đồng bộ vào bảng models."""
    net_labels = network_labels if network_multi is not None else ["BENIGN", "ATTACK"]
    out = [{
        "task_type": "network", "name": "Random Forest" + (" nhiều lớp" if network_multi is not None else " nhị phân"),
        "version": NETWORK_VERSION, "loaded": True, "labels": net_labels, "features": _feature_names,
        "file_path": os.path.join(MODEL_DIR, "rf_multiclass.pkl" if network_multi is not None else "rf_binary.pkl"),
        "preprocessor_path": os.path.join(DATA_DIR, "scaler.pkl"),
    }]
    out.append({
        "task_type": "email", "name": "TF-IDF + Linear SVM", "version": EMAIL_VERSION,
        "loaded": email_model is not None, "labels": ["NON_SPAM", "SPAM"],
        "file_path": _email_path,
    })
    return {"models": out}

@app.post("/predict/batch")
def predict_batch(payload: BatchRequest):
    if not payload.rows:
        raise HTTPException(400, "Danh sách dòng rỗng")
    if len(payload.rows) > 5000:
        raise HTTPException(400, "Tối đa 5000 dòng mỗi lô")
    if payload.task_type == "network":
        return {"task_type": "network", "model_version": NETWORK_VERSION, "results": _predict_network(payload.rows)}
    if payload.task_type == "email":
        if email_model is None:
            raise HTTPException(503, "Chưa có mô hình email (models/email_svm.pkl)")
        return {"task_type": "email", "model_version": EMAIL_VERSION, "results": _predict_email(payload.rows)}
    raise HTTPException(400, "task_type phải là network hoặc email")

@app.get("/classify/schema")
def classify_schema():
    """Danh sách đặc trưng mô hình RF cần, để nơi gửi cảnh báo biết cần điền gì."""
    return {"features": [str(c) for c in feature_cols], "model_version": "rf_binary_v1"}

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
    if searcher is None:
        raise HTTPException(503, "Chưa có chỉ mục ATT&CK (attck_search.py hoặc models/attck_*)")
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
    techniques = search_attck(strip_indicators(f"{title}. {description}") or query, top_k=5)

    # Severity dựa trên keyword đơn giản (không dùng network features)
    severity = "medium"
    critical_kw = ["ransomware", "encrypt", "locked", "data exfil"]
    high_kw     = ["brute force", "phishing", "injection", "sql",
                   "malware", "backdoor", "attack", "intrusion",
                   "elevated privileges", "ddos"]
    low_kw      = ["info", "recon"]

    query_lower = (query + " " + searcher.translate(query)).lower()
    if any(k in query_lower for k in critical_kw):
        severity = "critical"
    elif any(k in query_lower for k in high_kw):
        severity = "high"
    elif any(k in query_lower for k in low_kw):
        severity = "low"
    # else: medium (default)

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