import hashlib
import time
from typing import Any, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Dịch vụ AI giả, kết quả xác định, dùng để kiểm thử luồng của backend mà không cần mô hình thật.
# Chạy: uvicorn fake_ai_service:app --port 8001 (trong thư mục tests)

FEATURES = [" Destination Port", " Flow Duration", " Total Fwd Packets", "Flow Bytes/s",
            " Fwd Header Length", " Fwd Header Length.1", " Packet Length Mean", "Init_Win_bytes_forward"]
NETWORK_LABELS = ["BENIGN", "DDoS", "PortScan"]
EMAIL_LABELS = ["NON_SPAM", "SPAM"]
VERSION = "fake_v1"

app = FastAPI(title="Fake AI Service")

class Batch(BaseModel):
    task_type: str
    rows: List[Any]

def _jitter(text: str) -> float:
    return int(hashlib.md5(text.encode()).hexdigest()[:4], 16) / 65535 * 0.09   # 0 đến 0.09

def classify_network(row: dict):
    dur = float(row[" Flow Duration"])
    pkts = float(row[" Total Fwd Packets"])
    if dur == 123456789:
        raise HTTPException(500, "Lỗi mô phỏng khi xử lý lô")
    if dur == 777777:
        time.sleep(2)   # mô phỏng mô hình chậm để kiểm thử trạng thái Đang xử lý
    if dur >= 1_000_000:
        return "DDoS", 0.90 + _jitter(str(dur))
    if pkts <= 1:
        return "PortScan", 0.60 + _jitter(str(dur))
    return "BENIGN", 0.90 + _jitter(str(dur))

def classify_email(row: dict):
    body = row["body"].lower()
    if "boom-crash" in body:
        raise HTTPException(500, "Lỗi mô phỏng khi xử lý lô")
    if "free money" in body or "verify your account" in body:
        return "SPAM", 0.95
    if len(row["urls"]) >= 3:
        return "SPAM", 0.70
    return "NON_SPAM", 0.90 + _jitter(body)

@app.get("/info")
def info():
    return {"models": [
        {"task_type": "network", "name": "Fake network model", "version": VERSION, "loaded": True,
         "labels": NETWORK_LABELS, "features": FEATURES, "metrics": {"note": "fake"}},
        {"task_type": "email", "name": "Fake email model", "version": VERSION, "loaded": True,
         "labels": EMAIL_LABELS, "metrics": {"note": "fake"}},
    ]}

@app.post("/predict/batch")
def predict(payload: Batch):
    if payload.task_type == "network":
        fn = classify_network
    elif payload.task_type == "email":
        fn = classify_email
    else:
        raise HTTPException(400, "task_type không hợp lệ")
    results = []
    for row in payload.rows:
        label, conf = fn(row)
        results.append({"label": label, "confidence": round(min(conf, 0.999), 4)})
    return {"task_type": payload.task_type, "model_version": VERSION, "results": results}
