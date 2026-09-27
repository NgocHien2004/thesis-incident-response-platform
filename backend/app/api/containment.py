from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from database import get_db
from app.models.containment import Containment, ContainmentStatus
from app.models.incident import Incident, IncidentStatus
from app.schemas.containment import (
    ContainmentCreate, ContainmentReview,
    ContainmentExecute, ContainmentOut
)
from app.core.dependencies import get_current_user, require_roles
from app.models.user import RoleEnum, User

router = APIRouter(prefix="/incidents/{incident_id}/containments", tags=["Containment"])

def _get_incident(incident_id: int, db: Session) -> Incident:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Không tìm thấy incident")
    return incident

# Xem danh sách containment
@router.get("/", response_model=List[ContainmentOut])
def list_containments(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _get_incident(incident_id, db)
    return db.query(Containment).filter(
        Containment.incident_id == incident_id
    ).order_by(Containment.proposed_at.desc()).all()

# IT đề xuất containment
@router.post("/", response_model=ContainmentOut)
def propose_containment(
    incident_id: int,
    payload: ContainmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc)
    )
):
    _get_incident(incident_id, db)

    if payload.risk_level not in ["low", "medium", "high"]:
        raise HTTPException(400, "risk_level phải là low, medium hoặc high")

    containment = Containment(
        incident_id=incident_id,
        action_type=payload.action_type,
        target=payload.target,
        reason=payload.reason,
        risk_level=payload.risk_level,
        status=ContainmentStatus.proposed,
        proposed_by=current_user.id,
        proposed_at=datetime.now(timezone.utc),
    )
    db.add(containment)
    db.commit()
    db.refresh(containment)
    return containment

# Analyst phê duyệt hoặc từ chối
@router.patch("/{containment_id}/review", response_model=ContainmentOut)
def review_containment(
    incident_id: int,
    containment_id: int,
    payload: ContainmentReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    containment = db.query(Containment).filter(
        Containment.id == containment_id,
        Containment.incident_id == incident_id
    ).first()
    if not containment:
        raise HTTPException(404, "Không tìm thấy đề xuất containment")
    if containment.status != ContainmentStatus.proposed:
        raise HTTPException(400, f"Đề xuất đang ở trạng thái '{containment.status}' — không thể review lại")

    containment.status      = ContainmentStatus.approved if payload.approved else ContainmentStatus.rejected
    containment.reviewed_by = current_user.id
    containment.reviewed_at = datetime.now(timezone.utc)
    containment.review_note = payload.review_note
    db.commit()
    db.refresh(containment)
    return containment

# IT thực hiện containment (mô phỏng — không tự động khóa hệ thống thật)
@router.patch("/{containment_id}/execute", response_model=ContainmentOut)
def execute_containment(
    incident_id: int,
    containment_id: int,
    payload: ContainmentExecute,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc)
    )
):
    containment = db.query(Containment).filter(
        Containment.id == containment_id,
        Containment.incident_id == incident_id
    ).first()
    if not containment:
        raise HTTPException(404, "Không tìm thấy đề xuất containment")
    if containment.status != ContainmentStatus.approved:
        raise HTTPException(
            400,
            "Chỉ có thể thực hiện containment đã được phê duyệt"
        )

    containment.status          = ContainmentStatus.executed
    containment.executed_by     = current_user.id
    containment.executed_at     = datetime.now(timezone.utc)
    containment.execution_note  = f"[MÔ PHỎNG] {payload.execution_note}"

    # Cập nhật trạng thái incident → contained
    incident = _get_incident(incident_id, db)
    if incident.status == IncidentStatus.investigating:
        incident.status = IncidentStatus.contained
        incident.contained_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(containment)
    return containment