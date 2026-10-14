import os
import re
import json
import hashlib
import datetime
import collections

import joblib
import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import CountVectorizer

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
INDEX_FILE = "attck_bm25.pkl"
VERSION_FILE = "attck_version.json"
GLOSSARY_FILE = os.path.join(HERE, "attck_glossary_vi.json")

K1 = 1.5
B = 0.75
NAME_WEIGHT = 3
MAX_EXAMPLES = 40
NAME_BOOST = 1.5

VI_CHARS = re.compile(
    r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.I)


def technique_id(obj):
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id", "")
    return ""


def build_index(data_dir="data", model_dir="models"):
    os.makedirs(model_dir, exist_ok=True)
    path = os.path.join(data_dir, "attck_enterprise.json")
    raw = open(path, "rb").read()
    bundle = json.loads(raw.decode("utf-8"))
    objs = bundle["objects"]

    techs = [o for o in objs if o.get("type") == "attack-pattern"
             and not o.get("revoked", False) and not o.get("x_mitre_deprecated", False)]
    by_stix = {o["id"]: o for o in techs}

    examples = collections.defaultdict(list)
    for o in objs:
        if (o.get("type") == "relationship" and o.get("relationship_type") == "uses"
                and not o.get("revoked", False) and o.get("target_ref") in by_stix and o.get("description")):
            examples[o["target_ref"]].append(re.sub(r"\(Citation:[^)]*\)", "", o["description"]))

    records, docs = [], []
    for t in techs:
        tid = technique_id(t)
        name = t.get("name", "")
        desc = t.get("description", "")
        tactics = [p["phase_name"] for p in t.get("kill_chain_phases", []) if p.get("kill_chain_name") == "mitre-attack"]
        docs.append(" ".join([(name + ". ") * NAME_WEIGHT, desc, t.get("x_mitre_detection", ""),
                              " ".join(examples.get(t["id"], [])[:MAX_EXAMPLES])]))
        records.append({"id": tid, "name": name, "tactics": tactics, "description": desc[:300],
                        "url": f"https://attack.mitre.org/techniques/{tid.replace('.', '/')}/"})

    cv = CountVectorizer(stop_words="english")
    X = cv.fit_transform(docs).astype(float).tocoo()
    n_docs = X.shape[0]
    doc_len = np.asarray(X.tocsr().sum(1)).ravel()
    df = np.asarray((X.tocsr() > 0).sum(0)).ravel()
    idf = np.log(1 + (n_docs - df + 0.5) / (df + 0.5))
    denom = X.data + K1 * (1 - B + B * doc_len[X.row] / doc_len.mean())
    W = sp.csr_matrix(((X.data * (K1 + 1) / denom) * idf[X.col], (X.row, X.col)), shape=X.shape)

    joblib.dump({"vectorizer": cv, "weights": W, "records": records}, os.path.join(model_dir, INDEX_FILE))

    latest = max(t.get("modified", "") for t in techs)
    version = {
        "version": "ent-" + latest[:10],
        "latest_technique_modified": latest,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "spec_version": bundle.get("spec_version"),
        "technique_count": len(records),
        "procedure_examples": sum(len(v) for v in examples.values()),
        "source_url": SOURCE_URL,
        "retrieval": "bm25 + procedure examples + vi glossary",
        "indexed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    with open(os.path.join(model_dir, VERSION_FILE), "w", encoding="utf-8") as f:
        json.dump(version, f, indent=2, ensure_ascii=False)
    return version


class Searcher:
    def __init__(self, model_dir="models"):
        idx = joblib.load(os.path.join(model_dir, INDEX_FILE))
        self.vectorizer = idx["vectorizer"]
        self.weights = idx["weights"]
        self.records = idx["records"]
        self.names = [r["name"].lower() for r in self.records]
        with open(os.path.join(model_dir, VERSION_FILE), encoding="utf-8") as f:
            self.version = json.load(f)
        glossary = {}
        if os.path.exists(GLOSSARY_FILE):
            glossary = json.load(open(GLOSSARY_FILE, encoding="utf-8"))
        self.glossary = glossary
        self.pattern = None
        if glossary:
            keys = sorted(glossary, key=len, reverse=True)
            self.pattern = re.compile(r"(?<!\w)(" + "|".join(re.escape(k) for k in keys) + r")(?!\w)", re.I)

    def translate(self, query):
        if not self.pattern or not VI_CHARS.search(query):
            return query
        text = self.pattern.sub(lambda m: " " + self.glossary[m.group(1).lower()] + " ", query)
        return " ".join(w for w in text.split() if not VI_CHARS.search(w))

    def search(self, query, top_k=5):
        q = self.translate(query)
        qv = self.vectorizer.transform([q])
        qv.data[:] = 1
        scores = np.asarray(self.weights.dot(qv.T).todense()).ravel()
        ql = (query + " " + q).lower()
        for i, name in enumerate(self.names):
            if name in ql:
                scores[i] *= NAME_BOOST
        order = np.argsort(-scores)[:top_k]
        return [{**self.records[i], "rank": rank, "score": round(float(scores[i]), 4)}
                for rank, i in enumerate(order, 1)]
