from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
import hashlib
from database import get_db
from app.models.evidence import Evidence, ChainOfCustody
from app.models.incident import Incident
from app.schemas.evidence import EvidenceCreate, EvidenceOut, CustodyLogOut
from app.core.dependencies import get_current_user, require_roles
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
    _get_incident(incident_id, db)

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

# Khóa bằng chứng — không sửa được sau khi lock
@router.patch("/{evidence_id}/lock", response_model=EvidenceOut)
def lock_evidence(
    incident_id: int,
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_id,
        Evidence.incident_id == incident_id
    ).first()
    if not evidence:
        raise HTTPException(404, "Không tìm thấy bằng chứng")
    if evidence.is_locked:
        raise HTTPException(400, "Bằng chứng đã bị khóa trước đó")

    evidence.is_locked = True
    db.commit()
    db.refresh(evidence)

    _log_custody(
        evidence.id, "locked", current_user.id,
        "Khóa bằng chứng — không thể chỉnh sửa sau thời điểm này",
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