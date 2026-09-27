from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
from database import get_db
from app.models.recovery import RecoveryAction, RecoveryStatus
from app.models.incident import Incident, IncidentStatus
from app.schemas.recovery import (
    RecoveryActionCreate, RecoveryActionUpdate,
    RecoveryConfirm, RecoveryActionOut
)
from app.core.dependencies import get_current_user, require_roles
from app.models.user import RoleEnum, User

router = APIRouter(prefix="/incidents/{incident_id}/recovery", tags=["Recovery"])

def _get_incident(incident_id: int, db: Session) -> Incident:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Không tìm thấy incident")
    return incident

# Xem danh sách recovery actions
@router.get("/", response_model=List[RecoveryActionOut])
def list_recovery_actions(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _get_incident(incident_id, db)
    return db.query(RecoveryAction).filter(
        RecoveryAction.incident_id == incident_id
    ).order_by(RecoveryAction.created_at.asc()).all()

# Tạo recovery action — IT và Analyst
@router.post("/", response_model=RecoveryActionOut)
def create_recovery_action(
    incident_id: int,
    payload: RecoveryActionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc)
    )
):
    _get_incident(incident_id, db)
    action = RecoveryAction(
        incident_id=incident_id,
        action_type=payload.action_type,
        description=payload.description,
        assigned_to=payload.assigned_to,
        created_by=current_user.id,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action

# Cập nhật trạng thái — IT thực hiện
@router.patch("/{action_id}/status", response_model=RecoveryActionOut)
def update_recovery_status(
    incident_id: int,
    action_id: int,
    payload: RecoveryActionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc)
    )
):
    action = db.query(RecoveryAction).filter(
        RecoveryAction.id == action_id,
        RecoveryAction.incident_id == incident_id
    ).first()
    if not action:
        raise HTTPException(404, "Không tìm thấy recovery action")

    action.status = payload.status
    action.note   = payload.note
    if payload.status == RecoveryStatus.done:
        action.executed_by = current_user.id
        action.executed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(action)
    return action

# Stakeholder xác nhận hệ thống đã phục hồi
@router.patch("/{action_id}/confirm", response_model=RecoveryActionOut)
def confirm_recovery(
    incident_id: int,
    action_id: int,
    payload: RecoveryConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(RoleEnum.stakeholder, RoleEnum.analyst_soc)
    )
):
    action = db.query(RecoveryAction).filter(
        RecoveryAction.id == action_id,
        RecoveryAction.incident_id == incident_id
    ).first()
    if not action:
        raise HTTPException(404, "Không tìm thấy recovery action")
    if action.status != RecoveryStatus.done:
        raise HTTPException(400, "Chỉ có thể xác nhận action đã hoàn thành (status: done)")

    action.is_confirmed = True
    action.confirmed_by = current_user.id
    action.confirmed_at = datetime.now(timezone.utc)
    action.confirm_note = payload.confirm_note

    # Kiểm tra tất cả action đã confirmed chưa
    all_actions = db.query(RecoveryAction).filter(
        RecoveryAction.incident_id == incident_id
    ).all()
    all_confirmed = all(a.is_confirmed for a in all_actions)

    # Nếu tất cả đã confirmed → incident chuyển sang recovering
    if all_confirmed:
        incident = _get_incident(incident_id, db)
        if incident.status == IncidentStatus.contained:
            incident.status = IncidentStatus.recovering
            db.commit()

    db.commit()
    db.refresh(action)
    return action

# Xem tóm tắt tiến độ recovery
@router.get("/summary")
def recovery_summary(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _get_incident(incident_id, db)
    actions = db.query(RecoveryAction).filter(
        RecoveryAction.incident_id == incident_id
    ).all()
    total       = len(actions)
    done        = sum(1 for a in actions if a.status == RecoveryStatus.done)
    confirmed   = sum(1 for a in actions if a.is_confirmed)
    return {
        "total": total,
        "done": done,
        "confirmed": confirmed,
        "pending": sum(1 for a in actions if a.status == RecoveryStatus.pending),
        "all_confirmed": confirmed == total and total > 0,
    }