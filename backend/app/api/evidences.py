from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
import hashlib
from database import get_db
from app.models.evidence import Evidence, ChainOfCustody, EvidenceType
from app.models.incident import Incident
from app.schemas.evidence import EvidenceCreate, EvidenceOut, CustodyLogOut, IntegrityOut
from app.core import evidence_store
from app.core.dependencies import get_current_user, require_roles
from app.core.rules import require_not_closed
from app.models.user import RoleEnum, User

router = APIRouter(prefix="/incidents/{incident_id}/evidences", tags=["Evidences"])

def _get_incident(incident_id: int, db: Session) -> Incident:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Không tìm thấy incident")
    return incident

def _log_custody(
    evidence_id: int,
    action: str,
    user_id: int,
    note: str,
    db: Session
):
    log = ChainOfCustody(
        evidence_id=evidence_id,
        action=action,
        performed_by=user_id,
        note=note,
        performed_at=datetime.now(timezone.utc)
    )
    db.add(log)
    db.commit()

def _get_evidence(incident_id: int, evidence_id: int, db: Session) -> Evidence:
    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_id,
        Evidence.incident_id == incident_id
    ).first()
    if not evidence:
        raise HTTPException(404, "Không tìm thấy bằng chứng")
    return evidence

def _check_integrity(evidence: Evidence) -> dict:
    """Băm lại dữ liệu đang lưu (tệp trong kho hoặc nội dung chữ) và so với mã băm ghi lúc thu thập."""
    if evidence.storage_key:
        checked = "file"
        res = evidence_store.hash_file(evidence.storage_key)
        actual, size = res if res else (None, None)
    elif evidence.content is not None:
        checked = "content"
        raw = evidence.content.encode("utf-8")
        actual, size = hashlib.sha256(raw).hexdigest(), len(raw)
    else:
        raise HTTPException(400, "Bằng chứng này không có tệp hay nội dung để kiểm tra")
    expected = (evidence.file_hash or "").strip().lower() or None
    if expected is None:
        raise HTTPException(400, "Bằng chứng chưa có mã băm ghi nhận lúc thu thập")
    ok = actual is not None and actual == expected
    if actual is None:
        message = "Không đọc được tệp trong kho lưu trữ"
    elif ok:
        message = "Mã băm khớp với bản ghi lúc thu thập"
    else:
        message = "Mã băm hiện tại KHÁC mã băm ghi nhận lúc thu thập"
    return {"ok": ok, "checked": checked, "expected": expected, "actual": actual,
            "size_bytes": size, "checked_at": datetime.now(timezone.utc), "message": message}

def _custody_note_failed(result: dict) -> str:
    return (f"Kiểm tra toàn vẹn KHÔNG đạt ({result['message']}). "
            f"Ghi nhận {result['expected']}, hiện tại {result['actual'] or 'không đọc được'}")

# Xem danh sách bằng chứng
@router.get("/", response_model=List[EvidenceOut])
def list_evidences(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _get_incident(incident_id, db)
    return db.query(Evidence).filter(Evidence.incident_id == incident_id).all()

# Xem chi tiết
@router.get("/{evidence_id}", response_model=EvidenceOut)
def get_evidence(
    incident_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_id,
        Evidence.incident_id == incident_id
    ).first()
    if not evidence:
        raise HTTPException(404, "Không tìm thấy bằng chứng")
    # Ghi log truy cập
    _log_custody(evidence.id, "accessed", current_user.id, "Xem chi tiết bằng chứng", db)
    return evidence

# Thu thập bằng chứng — IT và Analyst
@router.post("/", response_model=EvidenceOut)
def collect_evidence(
    incident_id: int,
    payload: EvidenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc)
    )
):
    require_not_closed(_get_incident(incident_id, db))

    # Tự tính hash nếu có content và chưa có hash
    file_hash = payload.file_hash
    if payload.content and not file_hash:
        file_hash = hashlib.sha256(
            payload.content.encode("utf-8")
        ).hexdigest()

    evidence = Evidence(
        incident_id=incident_id,
        title=payload.title,
        evidence_type=payload.evidence_type,
        description=payload.description,
        source=payload.source,
        file_hash=file_hash,
        file_path=payload.file_path,
        content=payload.content,
        is_locked=False,
        collected_by=current_user.id,
        collected_at=datetime.now(timezone.utc),
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    # Ghi chain of custody — thu thập
    _log_custody(
        evidence.id, "collected", current_user.id,
        f"Thu thập từ nguồn: {payload.source or 'không rõ'}",
        db
    )
    return evidence

# Thu thập bằng chứng dạng tệp — IT và Analyst
@router.post("/upload", response_model=EvidenceOut)
def upload_evidence(
    incident_id: int,
    request: Request,
    title: str = Form(...),
    evidence_type: EvidenceType = Form(EvidenceType.file),
    description: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc)
    )
):
    require_not_closed(_get_incident(incident_id, db))
    title = title.strip()
    if not title or len(title) > 200:
        raise HTTPException(422, "Tiêu đề không được để trống và tối đa 200 ký tự")
    if source and len(source) > 200:
        raise HTTPException(422, "Nguồn tối đa 200 ký tự")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > evidence_store.MAX_BYTES + 1024 * 1024:
        raise HTTPException(413, f"Tệp vượt quá giới hạn {evidence_store.MAX_MB} MB")

    key = evidence_store.new_key(incident_id)
    try:
        file_hash, size = evidence_store.save_stream(file.file, key)
    except evidence_store.TooLarge:
        raise HTTPException(413, f"Tệp vượt quá giới hạn {evidence_store.MAX_MB} MB")
    if size == 0:
        evidence_store.delete_quietly(key)
        raise HTTPException(400, "Tệp rỗng")

    name = evidence_store.safe_filename(file.filename)
    evidence = Evidence(
        incident_id=incident_id,
        title=title,
        evidence_type=evidence_type,
        description=description,
        source=source,
        file_hash=file_hash,
        original_filename=name,
        content_type=(file.content_type or "")[:100] or None,
        size_bytes=size,
        storage_key=key,
        is_locked=False,
        collected_by=current_user.id,
        collected_at=datetime.now(timezone.utc),
    )
    try:
        db.add(evidence)
        db.commit()
        db.refresh(evidence)
    except Exception:
        db.rollback()
        evidence_store.delete_quietly(key)
        raise

    _log_custody(
        evidence.id, "collected", current_user.id,
        f"Thu thập tệp \"{name}\" ({size} byte) từ nguồn: {source or 'không rõ'}. "
        f"SHA-256 tính trên byte nhận được: {file_hash}",
        db
    )
    return evidence

# Kiểm tra toàn vẹn — băm lại dữ liệu đang lưu và so với mã băm lúc thu thập
@router.post("/{evidence_id}/verify", response_model=IntegrityOut)
def verify_evidence(
    incident_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc)
    )
):
    evidence = _get_evidence(incident_id, evidence_id, db)
    result = _check_integrity(evidence)
    if result["ok"]:
        _log_custody(evidence.id, "verified", current_user.id,
                     f"Kiểm tra toàn vẹn đạt: SHA-256 khớp {result['actual']}", db)
    else:
        _log_custody(evidence.id, "integrity_failed", current_user.id, _custody_note_failed(result), db)
    return result

# Cấp bản sao làm việc — tệp gốc trong kho không bao giờ được phát ra trực tiếp
@router.get("/{evidence_id}/download")
def download_working_copy(
    incident_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc)
    )
):
    evidence = _get_evidence(incident_id, evidence_id, db)
    if not evidence.storage_key:
        raise HTTPException(404, "Bằng chứng này không có tệp đính kèm")
    result = _check_integrity(evidence)
    if not result["ok"]:
        _log_custody(evidence.id, "integrity_failed", current_user.id, _custody_note_failed(result), db)
        raise HTTPException(409, "Tệp gốc không còn khớp mã băm ghi nhận hoặc không đọc được; không cấp bản sao làm việc")
    name = evidence.original_filename or f"bang-chung-{evidence.id}"
    _log_custody(
        evidence.id, "working_copy_issued", current_user.id,
        f"Cấp bản sao làm việc của \"{name}\" ({result['size_bytes']} byte); "
        f"SHA-256 {result['actual']} đã kiểm tra khớp bản gốc ngay trước khi cấp",
        db
    )
    return FileResponse(
        evidence_store.path_for(evidence.storage_key),
        media_type="application/octet-stream",
        filename=name,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
    )

# Lock bằng chứng — IT và Analyst đều được lock
@router.patch("/{evidence_id}/lock", response_model=EvidenceOut)
def lock_evidence(
    incident_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        RoleEnum.analyst_soc, RoleEnum.it_helpdesk  #thêm it_helpdesk
    ))
):
    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_id,
        Evidence.incident_id == incident_id
    ).first()
    if not evidence:
        raise HTTPException(404, "Không tìm thấy bằng chứng")
    if evidence.is_locked:
        raise HTTPException(400, "Bằng chứng đã bị khóa trước đó")

    lock_note = "Khóa bằng chứng — không thể chỉnh sửa sau thời điểm này"
    if evidence.storage_key:
        result = _check_integrity(evidence)
        if not result["ok"]:
            _log_custody(evidence.id, "integrity_failed", current_user.id, _custody_note_failed(result), db)
            raise HTTPException(409, "Tệp gốc không còn khớp mã băm ghi nhận; không thể khóa")
        lock_note = (f"Khóa bằng chứng — SHA-256 {result['actual']} đã kiểm tra khớp lúc khóa; "
                     "không thể chỉnh sửa sau thời điểm này")

    evidence.is_locked = True
    db.commit()
    db.refresh(evidence)

    _log_custody(
        evidence.id, "locked", current_user.id,
        lock_note,
        db
    )
    return evidence

# Xem chain of custody
@router.get("/{evidence_id}/custody", response_model=List[CustodyLogOut])
def get_custody_log(
    incident_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_id,
        Evidence.incident_id == incident_id
    ).first()
    if not evidence:
        raise HTTPException(404, "Không tìm thấy bằng chứng")
    return db.query(ChainOfCustody).filter(
        ChainOfCustody.evidence_id == evidence_id
    ).order_by(ChainOfCustody.performed_at.asc()).all()