import hashlib
import json
import os
from typing import List

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from email_features import URL_RE, to_text

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "models")
DATA_DIR = os.path.join(HERE, "data", "ids", "processed")
MAX_BATCH = 5000


def require(path: str, hint: str) -> str:
    if not os.path.isfile(path):
        raise SystemExit(f"Thiếu {os.path.relpath(path, HERE)}. {hint}")
    return path


def version_of(prefix: str, path: str) -> str:
    # Phiên bản theo nội dung file mô hình: huấn luyện lại thì phiên bản đổi
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return f"{prefix}_{h.hexdigest()[:8]}"


# ── Mô hình luồng mạng: bắt buộc, thiếu file nào thì dừng hẳn ──
print("Loading network model...")
_multi_path = require(os.path.join(MODEL_DIR, "rf_multiclass.pkl"), "Chạy python train_multiclass.py")
_labels_path = require(os.path.join(MODEL_DIR, "network_labels.json"), "File này do train_multiclass.py tạo")
_scaler_path = require(os.path.join(DATA_DIR, "scaler.pkl"), "Chạy python preprocess.py")
_features_path = require(os.path.join(DATA_DIR, "feature_cols.pkl"), "Chạy python preprocess.py")

network_model = joblib.load(_multi_path)
scaler = joblib.load(_scaler_path)
feature_cols = joblib.load(_features_path)
with open(_labels_path, encoding="utf-8") as _f:
    network_labels = json.load(_f)
if int(max(network_model.classes_)) >= len(network_labels):
    raise SystemExit("network_labels.json có ít nhãn hơn số lớp của mô hình; huấn luyện lại bằng train_multiclass.py")
NETWORK_VERSION = version_of("rf_multiclass", _multi_path)

# ── Mô hình email: thiếu thì /predict/batch cho email trả 503, /info báo loaded = false ──
_email_path = os.path.join(MODEL_DIR, "email_svm.pkl")
email_model, EMAIL_VERSION = None, "email_svm_none"
if os.path.isfile(_email_path):
    print("Loading email model...")
    email_model = joblib.load(_email_path)
    EMAIL_VERSION = version_of("email_svm", _email_path)
else:
    print("Không thấy models/email_svm.pkl: nguồn email sẽ không dùng được (chạy python train_email.py)")

print(f"Network {NETWORK_VERSION} ({len(network_labels)} nhãn) | Email {EMAIL_VERSION}")

_feature_names = [str(c) for c in feature_cols]
_feature_lookup = {name.strip().casefold(): name for name in _feature_names}

app = FastAPI(title="AI Service")


class BatchRequest(BaseModel):
    task_type: str
    rows: List[dict]


def to_float(v) -> float:
    try:
        x = float(v)
    except (ValueError, TypeError):
        return 0.0
    return x if np.isfinite(x) else 0.0


def predict_network(rows: List[dict]):
    X = np.zeros((len(rows), len(_feature_names)))
    for i, row in enumerate(rows):
        by_name = {}
        for k, v in row.items():
            name = _feature_lookup.get(str(k).strip().casefold())
            if name is not None:
                by_name[name] = v
        for j, col in enumerate(_feature_names):
            X[i, j] = to_float(by_name.get(col, 0))
    proba = network_model.predict_proba(scaler.transform(X))
    classes = [network_labels[int(c)] for c in network_model.classes_]
    best = proba.argmax(axis=1)
    return [{"label": classes[b], "confidence": round(float(proba[i, b]), 4)} for i, b in enumerate(best)]


def predict_email(rows: List[dict]):
    texts = []
    for r in rows:
        body = str(r.get("body", ""))[:30000]
        urls = URL_RE.findall(body)
        urls += [u for u in (r.get("urls") or []) if u not in urls]
        texts.append(to_text({"subject": str(r.get("subject", ""))[:500], "body": body, "urls": urls,
                              "has_html": False, "attachments": []}))
    spam = email_model.predict_proba(texts)[:, 1]
    return [{"label": "SPAM" if p >= 0.5 else "NON_SPAM", "confidence": round(float(max(p, 1 - p)), 4)} for p in spam]


@app.get("/")
def root():
    return {"service": "AI Service", "status": "ready", "network": NETWORK_VERSION,
            "email": EMAIL_VERSION if email_model is not None else None}


@app.get("/info")
def info():
    return {"models": [
        {"task_type": "network", "name": "Random Forest nhiều lớp", "version": NETWORK_VERSION, "loaded": True,
         "labels": network_labels, "features": _feature_names,
         "file_path": os.path.relpath(_multi_path, HERE), "preprocessor_path": os.path.relpath(_scaler_path, HERE)},
        {"task_type": "email", "name": "TF-IDF + Linear SVM", "version": EMAIL_VERSION,
         "loaded": email_model is not None, "labels": ["NON_SPAM", "SPAM"],
         "file_path": os.path.relpath(_email_path, HERE)},
    ]}


@app.post("/predict/batch")
def predict_batch(payload: BatchRequest):
    if not payload.rows:
        raise HTTPException(400, "Danh sách dòng rỗng")
    if len(payload.rows) > MAX_BATCH:
        raise HTTPException(400, f"Tối đa {MAX_BATCH} dòng mỗi lô")
    if payload.task_type == "network":
        return {"task_type": "network", "model_version": NETWORK_VERSION, "results": predict_network(payload.rows)}
    if payload.task_type == "email":
        if email_model is None:
            raise HTTPException(503, "Chưa có mô hình email (models/email_svm.pkl)")
        return {"task_type": "email", "model_version": EMAIL_VERSION, "results": predict_email(payload.rows)}
    raise HTTPException(400, "task_type phải là network hoặc email")