import json
import os
import time
import requests
from sqlalchemy.orm import Session
from app.models.ml_model import MLModel, Label
from app.core.constants import BENIGN_LABELS
from app.core.timeutils import utcnow

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8001")

# Khi mất kết nối tới dịch vụ AI (tắt, khởi động lại, mạng chập chờn) thì chờ và thử lại trước khi báo lỗi.
# Đây là khoảng chờ giữa các lần thử, tổng khoảng 30 giây; gọi lại một lô là an toàn vì dự đoán không đổi trạng thái.
RETRY_DELAYS = tuple(float(x) for x in os.getenv("AI_RETRY_DELAYS", "1,2,4,8,15").split(",") if x.strip())

class AIError(Exception):
    pass

def _call(method: str, path: str, timeout: int, retry: bool = False, **kw):
    delays = list(RETRY_DELAYS) if retry else []
    while True:
        try:
            resp = requests.request(method, AI_SERVICE_URL + path, timeout=timeout, **kw)
            break
        except requests.ConnectionError as e:
            # Chưa nhận được phản hồi nào: dịch vụ chưa nối lại được, đợi rồi thử lại
            if delays:
                time.sleep(delays.pop(0))
                continue
            raise AIError(f"Không kết nối được dịch vụ AI: {e.__class__.__name__}")
        except requests.RequestException as e:
            raise AIError(f"Không kết nối được dịch vụ AI: {e.__class__.__name__}")
    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise AIError(f"Dịch vụ AI trả lỗi {resp.status_code}: {str(detail)[:300]}")
    try:
        return resp.json()
    except ValueError:
        raise AIError("Dịch vụ AI trả dữ liệu không đọc được")

def is_online() -> bool:
    # Chỉ kiểm tra dịch vụ AI có đang trả lời không (không đổi gì trong CSDL)
    try:
        return requests.get(AI_SERVICE_URL + "/", timeout=3).status_code == 200
    except requests.RequestException:
        return False

def fetch_info() -> dict:
    return _call("GET", "/info", 15)

def predict_batch(task_type: str, rows: list) -> dict:
    data = _call("POST", "/predict/batch", 300, retry=True, json={"task_type": task_type, "rows": rows})
    results = data.get("results")
    if not isinstance(results, list) or len(results) != len(rows):
        raise AIError("Dịch vụ AI trả số kết quả không khớp số dòng gửi lên")
    for r in results:
        if not isinstance(r, dict) or "label" not in r or "confidence" not in r:
            raise AIError("Dịch vụ AI trả kết quả thiếu nhãn hoặc confidence")
    return data

def default_dangerous(label: str) -> bool:
    return label.strip().upper() not in BENIGN_LABELS

def ensure_label(db: Session, data_type: str, code: str) -> Label:
    row = db.query(Label).filter(Label.data_type == data_type, Label.code == code).first()
    if not row:
        row = Label(data_type=data_type, code=code, name_vi=code, is_dangerous=default_dangerous(code), is_active=True)
        db.add(row)
        db.flush()
    return row

def sync_models(db: Session) -> list:
    # Lấy danh sách mô hình đang chạy ở dịch vụ AI, ghi vào bảng models và bổ sung nhãn mới
    info = fetch_info()
    out = []
    for m in info.get("models", []):
        task, version = m.get("task_type"), m.get("version")
        if task not in ("network", "email") or not version:
            continue
        row = db.query(MLModel).filter(MLModel.task_type == task, MLModel.version == version).first()
        if not row:
            row = MLModel(task_type=task, version=version, name=m.get("name") or version)
            db.add(row)
        row.name = m.get("name") or row.name
        row.file_path = m.get("file_path")
        row.preprocessor_path = m.get("preprocessor_path")
        if m.get("metrics") is not None:
            row.metrics_json = json.dumps(m["metrics"], ensure_ascii=False)
        if m.get("features") is not None:
            row.feature_names = json.dumps(m["features"], ensure_ascii=False)
        row.is_active = bool(m.get("loaded", True))
        db.flush()
        if row.is_active:
            for other in db.query(MLModel).filter(MLModel.task_type == task, MLModel.id != row.id).all():
                other.is_active = False
            for code in m.get("labels", []):
                ensure_label(db, task, code)
        out.append(row)
    db.commit()
    return out

def get_active_model(db: Session, task_type: str) -> MLModel:
    row = db.query(MLModel).filter(MLModel.task_type == task_type, MLModel.is_active == True).first()  # noqa: E712
    if row:
        return row
    sync_models(db)
    row = db.query(MLModel).filter(MLModel.task_type == task_type, MLModel.is_active == True).first()  # noqa: E712
    if not row:
        raise AIError("Dịch vụ AI chưa có mô hình " + ("luồng mạng" if task_type == "network" else "email"))
    return row
