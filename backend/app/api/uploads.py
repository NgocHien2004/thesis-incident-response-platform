import hashlib
import json
import os
import re
import shutil
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from database import get_db
from app.core.dependencies import get_current_user
from app.core.constants import DATA_TYPES, EMAIL_ONLY_FORMATS, FILE_FORMATS, UPLOADABLE_STATUSES
from app.core.paging import chunks
from app.core.storage import UPLOAD_STORAGE_DIR
from app.core.timeutils import utcnow
from app.models.user import User
from app.models.incident import Incident
from app.models.upload import Upload
from app.models.alert import Alert, AlertMoveHistory
from app.models.ml_model import MLModel
from app.schemas.upload import UploadOut
from app.services import classifier
from app.services.classifier import AIError
from app.services.parsing import Schema, ValidationError, validate_file
from app.services.settings_store import get_int
from app.services.upload_processing import process_upload
from app.api.incidents import get_incident_or_404

router = APIRouter(tags=["Uploads"])

CHUNK = 1024 * 1024

def clean_filename(name: str) -> str:
    name = os.path.basename((name or "").replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:255] or "upload"

def upload_out(db: Session, up: Upload, warnings: list = None) -> dict:
    model = db.get(MLModel, up.model_id) if up.model_id else None
    user = db.get(User, up.uploaded_by)
    return {
        "id": up.id, "incident_id": up.incident_id, "original_filename": up.original_filename,
        "data_type": up.data_type, "file_hash": up.file_hash, "file_size_bytes": up.file_size_bytes,
        "row_count": up.row_count, "processed_rows": up.processed_rows, "status": up.status,
        "error_message": up.error_message, "model_id": up.model_id,
        "model_name": model.name if model else None, "model_version": model.version if model else None,
        "threshold_used": up.threshold_used,
        "dangerous_labels_used": json.loads(up.dangerous_labels_used) if up.dangerous_labels_used else [],
        "alert_count": up.alert_count, "avg_confidence": up.avg_confidence,
        "label_distribution": json.loads(up.label_distribution) if up.label_distribution else {},
        "uploaded_by": up.uploaded_by, "uploaded_by_name": user.full_name if user else None,
        "uploaded_at": up.uploaded_at, "processed_at": up.processed_at, "warnings": warnings or [],
    }

def delete_upload_files(db: Session, incident_id: int):
    for up in db.query(Upload).filter(Upload.incident_id == incident_id).all():
        try:
            os.remove(up.stored_path)
        except OSError:
            pass
        db.delete(up)

def _remove(path: str):
    try:
        os.remove(path)
    except OSError:
        pass

@router.post("/incidents/{incident_id}/uploads", response_model=UploadOut, status_code=202)
def create_upload(incident_id: int, background: BackgroundTasks, data_type: str = Form(...),
                  file: UploadFile = File(...), db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    inc = get_incident_or_404(db, incident_id)
    if inc.status not in UPLOADABLE_STATUSES:
        raise HTTPException(409, "Chỉ upload được khi sự cố ở trạng thái Mới hoặc Đang xử lý")
    if data_type not in DATA_TYPES:
        raise HTTPException(422, "Nguồn dữ liệu phải là network hoặc email")
    original = clean_filename(file.filename)
    ext = os.path.splitext(original)[1].lower()
    if ext not in FILE_FORMATS:
        raise HTTPException(422, "Chỉ nhận file .csv, .json, .eml hoặc .zip (chứa các file .eml)")
    if FILE_FORMATS[ext] in EMAIL_ONLY_FORMATS and data_type != "email":
        raise HTTPException(422, "File .eml và .zip chỉ dùng được cho nguồn Email")

    max_bytes = get_int(db, "max_upload_mb") * 1024 * 1024
    folder = os.path.join(UPLOAD_STORAGE_DIR, str(inc.id))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, uuid.uuid4().hex + ext)
    sha, size = hashlib.sha256(), 0
    try:
        with open(path, "wb") as out:
            while True:
                chunk = file.file.read(CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"File vượt quá {max_bytes // (1024 * 1024)} MB")
                sha.update(chunk)
                out.write(chunk)
    except HTTPException:
        _remove(path)
        raise
    except OSError:
        _remove(path)
        raise HTTPException(500, "Không ghi được file lên kho lưu trữ")
    if size == 0:
        _remove(path)
        raise HTTPException(422, "File rỗng")
    digest = sha.hexdigest()

    # Mỗi file (theo nội dung) chỉ được upload một lần trong toàn hệ thống, kể cả ở sự cố khác.
    # File đã lỗi (failed) không tính, nên upload lại được. File upload nhầm thì xóa đi (DELETE /uploads/{id}) rồi upload lại.
    dup = (db.query(Upload, Incident.code).join(Incident, Incident.id == Upload.incident_id)
           .filter(Upload.file_hash == digest, Upload.status != "failed")
           .order_by(Upload.id).first())
    if dup:
        _remove(path)
        d, code = dup
        if d.incident_id == inc.id:
            raise HTTPException(409, f"File này đã được upload vào sự cố (upload #{d.id}, {d.original_filename})")
        raise HTTPException(409, f"File này đã được upload vào sự cố {code} (upload #{d.id}, {d.original_filename})")

    try:
        model = classifier.get_active_model(db, data_type)
        if data_type == "network" and not model.feature_names:
            classifier.sync_models(db)
            db.refresh(model)
    except AIError as e:
        _remove(path)
        raise HTTPException(503, str(e))
    try:
        features = json.loads(model.feature_names) if model.feature_names else None
        schema = Schema(data_type, features)
        rows = validate_file(path, FILE_FORMATS[ext], schema, get_int(db, "max_rows"))
    except ValidationError as e:
        _remove(path)
        raise HTTPException(422, str(e))

    up = Upload(incident_id=inc.id, original_filename=original, stored_path=path, file_hash=digest,
                data_type=data_type, file_size_bytes=size, row_count=rows, processed_rows=0,
                status="pending", model_id=model.id, uploaded_by=user.id)
    db.add(up)
    db.commit()
    db.refresh(up)
    background.add_task(process_upload, up.id)
    return upload_out(db, up)

@router.get("/incidents/{incident_id}/uploads", response_model=list[UploadOut])
def list_uploads(incident_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_incident_or_404(db, incident_id)
    rows = db.query(Upload).filter(Upload.incident_id == incident_id).order_by(Upload.uploaded_at.desc(), Upload.id.desc()).all()
    return [upload_out(db, u) for u in rows]

@router.get("/uploads/{upload_id}", response_model=UploadOut)
def get_upload(upload_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    up = db.get(Upload, upload_id)
    if not up:
        raise HTTPException(404, "Không tìm thấy upload")
    return upload_out(db, up)

@router.delete("/uploads/{upload_id}", status_code=204)
def delete_upload(upload_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Xóa file upload nhầm cùng mọi cảnh báo sinh từ nó (kể cả đã xác minh); hash được giải phóng nên upload lại được.
    # Chỉ khi sự cố còn Mới hoặc Đang xử lý và file không đang xử lý.
    up = db.get(Upload, upload_id)
    if not up:
        raise HTTPException(404, "Không tìm thấy upload")
    inc = db.get(Incident, up.incident_id)
    if inc.status not in UPLOADABLE_STATUSES:
        raise HTTPException(409, "Chỉ xóa được file khi sự cố ở trạng thái Mới hoặc Đang xử lý")
    if up.status in ("pending", "processing"):
        raise HTTPException(409, "File đang xử lý, hãy đợi xong rồi mới xóa")
    # Cảnh báo của file đã được chuyển sang sự cố khác thì sự cố đó đang dùng: bắt chuyển về trước
    elsewhere = (db.query(Alert).filter(Alert.upload_id == up.id, Alert.incident_id.isnot(None),
                                        Alert.incident_id != up.incident_id).count())
    if elsewhere:
        raise HTTPException(409, f"{elsewhere} cảnh báo của file này đã được chuyển sang sự cố khác; "
                                 "hãy chuyển chúng về sự cố này trước khi xóa file")
    alert_ids = [r[0] for r in db.query(Alert.id).filter(Alert.upload_id == up.id).all()]
    # Thứ tự theo khóa ngoại: lịch sử chuyển, cảnh báo, rồi upload; chia khối để không vượt giới hạn tham số của SQL Server
    for part in chunks(alert_ids, 500):
        db.query(AlertMoveHistory).filter(AlertMoveHistory.alert_id.in_(part)).delete(synchronize_session=False)
        db.query(Alert).filter(Alert.id.in_(part)).delete(synchronize_session=False)
    path = up.stored_path
    db.delete(up)
    db.commit()
    _remove(path)   # xóa file sau khi giao dịch thành công; lỗi xóa file không làm hỏng dữ liệu