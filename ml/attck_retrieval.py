import json
import joblib
import os
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR  = "data"
MODEL_DIR = "models"
os.makedirs(MODEL_DIR, exist_ok=True)

# ── Bước 1: Load ATT&CK data ──
print("Loading ATT&CK data...")
with open(os.path.join(DATA_DIR, "attck_enterprise.json"), encoding="utf-8") as f:
    attck_data = json.load(f)

techniques = [
    obj for obj in attck_data["objects"]
    if obj.get("type") == "attack-pattern"
    and not obj.get("revoked", False)
    and not obj.get("x_mitre_deprecated", False)
]
print(f"Loaded {len(techniques)} techniques")

# ── Bước 2: Trích xuất thông tin từng technique ──
def get_technique_id(tech):
    for ref in tech.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id", "")
    return ""

def get_tactic(tech):
    phases = tech.get("kill_chain_phases", [])
    return [p["phase_name"] for p in phases if p.get("kill_chain_name") == "mitre-attack"]

tech_records = []
for t in techniques:
    tid   = get_technique_id(t)
    name  = t.get("name", "")
    desc  = t.get("description", "")
    tactics = get_tactic(t)

    # Lấy detection hints
    detection = t.get("x_mitre_detection", "")

    # Tạo document để index (name + description + detection)
    document = f"{name}. {desc} {detection}".strip()

    tech_records.append({
        "id":        tid,
        "name":      name,
        "tactics":   tactics,
        "description": desc[:300],  # rút gọn cho response
        "document":  document,
        "url":       f"https://attack.mitre.org/techniques/{tid.replace('.', '/')}/"
    })

print(f"Extracted {len(tech_records)} technique records")

# ── Bước 3: Build TF-IDF index ──
print("Building TF-IDF index...")
documents = [r["document"] for r in tech_records]

vectorizer = TfidfVectorizer(
    max_features=10000,
    ngram_range=(1, 2),       # unigram + bigram
    stop_words="english",
    sublinear_tf=True,         # log TF
)
tfidf_matrix = vectorizer.fit_transform(documents)
print(f"TF-IDF matrix: {tfidf_matrix.shape}")

# ── Bước 4: Lưu index ──
print("Saving index...")
joblib.dump(vectorizer,   os.path.join(MODEL_DIR, "attck_vectorizer.pkl"))
joblib.dump(tfidf_matrix, os.path.join(MODEL_DIR, "attck_tfidf_matrix.pkl"))
joblib.dump(tech_records, os.path.join(MODEL_DIR, "attck_tech_records.pkl"))

# Lưu phiên bản ATT&CK đang dùng
attck_version = {
    "version": "14.1",
    "spec_version": attck_data.get("spec_version"),
    "technique_count": len(tech_records),
    "indexed_at": str(__import__("datetime").datetime.utcnow()),
}
with open(os.path.join(MODEL_DIR, "attck_version.json"), "w") as f:
    json.dump(attck_version, f, indent=2)

print("Index saved!")

# ── Bước 5: Retrieval + Reranking function ──
def search_attck(query: str, top_k: int = 5) -> list:
    """
    Retrieval: TF-IDF cosine similarity
    Reranking: boost score nếu tên technique xuất hiện trong query
    """
    # Retrieval
    query_vec = vectorizer.transform([query])
    scores    = cosine_similarity(query_vec, tfidf_matrix).flatten()

    # Lấy top 20 candidates trước khi rerank
    candidate_indices = np.argsort(scores)[::-1][:20]

    # Reranking: boost nếu tên technique match với query
    query_lower = query.lower()
    results = []
    for idx in candidate_indices:
        tech   = tech_records[idx]
        score  = float(scores[idx])

        # Boost score nếu tên xuất hiện trong query
        if tech["name"].lower() in query_lower:
            score *= 1.5

        # Boost nếu tactic keywords match
        tactic_keywords = {
            "brute force": "credential-access",
            "phishing": "initial-access",
            "scan": "discovery",
            "lateral": "lateral-movement",
            "exfil": "exfiltration",
            "malware": "execution",
            "persistence": "persistence",
            "privilege": "privilege-escalation",
        }
        for kw, tactic in tactic_keywords.items():
            if kw in query_lower and tactic in tech["tactics"]:
                score *= 1.2
                break

        results.append({
            "rank":        len(results) + 1,
            "id":          tech["id"],
            "name":        tech["name"],
            "tactics":     tech["tactics"],
            "description": tech["description"],
            "url":         tech["url"],
            "score":       round(score, 4),
        })

    # Sort lại sau reranking
    results.sort(key=lambda x: x["score"], reverse=True)

    # Gán lại rank
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results[:top_k]

# ── Test ──
print("\n── Test retrieval ──")
test_queries = [
    "brute force SSH login attempts from external IP",
    "phishing email with malicious attachment",
    "lateral movement using stolen credentials",
    "port scan reconnaissance activity",
]

for q in test_queries:
    print(f"\nQuery: '{q}'")
    results = search_attck(q, top_k=3)
    for r in results:
        print(f"  [{r['rank']}] {r['id']} — {r['name']} (score={r['score']}) | tactics: {r['tactics']}")

print("\n✓ ATT&CK retrieval engine ready!")