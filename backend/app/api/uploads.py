import hashlib
import json
import os
import re
import shutil
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from typing import Optional
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from database import get_db
from app.core.dependencies import get_current_user
from app.core.constants import (BENIGN_LABELS, DATA_TYPES, EMAIL_ONLY_FORMATS, FILE_FORMATS, UPLOAD_STATUSES,
                                UPLOADABLE_STATUSES)
from app.core.paging import apply_page, chunks, page_response
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

def benign_count(distribution: dict) -> int:
    # Số dòng được phân loại bình thường (BENIGN, NON_SPAM, HAM): các dòng này không sinh cảnh báo nên không có
    # bản ghi trong bảng alerts, chỉ còn con số trong phân bố nhãn của file
    return sum(int(n) for label, n in distribution.items() if str(label).strip().upper() in BENIGN_LABELS)

def upload_out(db: Session, up: Upload, warnings: list = None) -> dict:
    model = db.get(MLModel, up.model_id) if up.model_id else None
    user = db.get(User, up.uploaded_by)
    inc = db.get(Incident, up.incident_id)
    distribution = json.loads(up.label_distribution) if up.label_distribution else {}
    return {
        "id": up.id, "incident_id": up.incident_id, "incident_code": inc.code if inc else None,
        "original_filename": up.original_filename,
        "data_type": up.data_type, "file_hash": up.file_hash, "file_size_bytes": up.file_size_bytes,
        "row_count": up.row_count, "processed_rows": up.processed_rows, "status": up.status,
        "error_message": up.error_message, "model_id": up.model_id,
        "model_name": model.name if model else None, "model_version": model.version if model else None,
        "threshold_used": up.threshold_used,
        "dangerous_labels_used": json.loads(up.dangerous_labels_used) if up.dangerous_labels_used else [],
        "alert_count": up.alert_count, "avg_confidence": up.avg_confidence,
        "label_distribution": distribution, "benign_count": benign_count(distribution),
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

# Thứ tự sắp xếp danh sách file; mỗi khóa dùng các cột khác nhau (SQL Server không cho lặp cột trong ORDER BY)
UPLOAD_SORTS = {
    "newest": lambda: [Upload.uploaded_at.desc(), Upload.id.desc()],
    "oldest": lambda: [Upload.uploaded_at.asc(), Upload.id.asc()],
    "name":   lambda: [Upload.original_filename.asc(), Upload.id.desc()],
    "alerts": lambda: [Upload.alert_count.desc(), Upload.id.desc()],
}

@router.get("/uploads")
def list_all_uploads(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
    q: Optional[str] = None, data_type: Optional[str] = None, status: Optional[str] = None,
    incident_id: Optional[int] = None, sort: str = "newest",
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    # Danh sách mọi file đã upload (kể cả file chỉ có dòng bình thường, không sinh cảnh báo nào).
    # Hai file có thể trùng tên (chống trùng theo nội dung, không theo tên): name_count cho biết, còn id,
    # sự cố và thời gian upload để phân biệt.
    if sort not in UPLOAD_SORTS:
        raise HTTPException(422, "sort không hợp lệ")
    if data_type and data_type not in DATA_TYPES:
        raise HTTPException(422, "Nguồn không hợp lệ")
    if status and status not in UPLOAD_STATUSES:
        raise HTTPException(422, "Trạng thái file không hợp lệ")
    query = (db.query(Upload, Incident.code, User.full_name)
             .join(Incident, Incident.id == Upload.incident_id)
             .outerjoin(User, User.id == Upload.uploaded_by))
    text = (q or "").strip()
    if text:
        digits = text.lstrip("#")
        match = [Upload.original_filename.contains(text, autoescape=True),
                 Incident.code.contains(text, autoescape=True)]
        if digits.isdigit() and len(digits) <= 9:
            match.append(Upload.id == int(digits))
        query = query.filter(or_(*match))
    if data_type:
        query = query.filter(Upload.data_type == data_type)
    if status:
        query = query.filter(Upload.status == status)
    if incident_id is not None:
        query = query.filter(Upload.incident_id == incident_id)
    rows, total = apply_page(query, UPLOAD_SORTS[sort](), page, page_size)

    ids = [u.id for u, _, _ in rows]
    verification = {}
    if ids:
        for uid, st, n in (db.query(Alert.upload_id, Alert.verification_status, func.count(Alert.id))
                           .filter(Alert.upload_id.in_(ids)).group_by(Alert.upload_id, Alert.verification_status)):
            verification.setdefault(uid, {})[st] = n
    same_name = {}
    if rows:
        for name, n in (db.query(Upload.original_filename, func.count(Upload.id))
                        .filter(Upload.original_filename.in_([u.original_filename for u, _, _ in rows]))
                        .group_by(Upload.original_filename)):
            same_name[name.lower()] = same_name.get(name.lower(), 0) + n

    items = []
    for u, code, uploader in rows:
        distribution = json.loads(u.label_distribution) if u.label_distribution else {}
        v = verification.get(u.id, {})
        items.append({
            "id": u.id, "incident_id": u.incident_id, "incident_code": code,
            "original_filename": u.original_filename, "name_count": same_name.get(u.original_filename.lower(), 1),
            "data_type": u.data_type, "file_size_bytes": u.file_size_bytes, "row_count": u.row_count,
            "status": u.status, "error_message": u.error_message, "alert_count": u.alert_count,
            "benign_count": benign_count(distribution),
            "unverified_count": v.get("unverified", 0), "verified_count": v.get("verified", 0),
            "dismissed_count": v.get("dismissed", 0),
            "avg_confidence": u.avg_confidence, "uploaded_by_name": uploader,
            "uploaded_at": u.uploaded_at, "processed_at": u.processed_at,
        })
    return page_response(items, total, page, page_size)

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