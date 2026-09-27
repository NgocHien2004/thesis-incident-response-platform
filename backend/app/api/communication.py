from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
import json
from database import get_db
from app.models.communication import Communication, CommStatus
from app.models.incident import Incident
from app.schemas.communication import CommunicationCreate, CommunicationOut
from app.core.dependencies import get_current_user, require_roles
from app.models.user import RoleEnum, User

router = APIRouter(prefix="/incidents/{incident_id}/communications", tags=["Communications"])

def _get_incident(incident_id: int, db: Session) -> Incident:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Không tìm thấy incident")
    return incident

# Xem danh sách thông báo
@router.get("/", response_model=List[CommunicationOut])
def list_communications(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _get_incident(incident_id, db)
    return db.query(Communication).filter(
        Communication.incident_id == incident_id
    ).order_by(Communication.created_at.desc()).all()

# Tạo thông báo (draft) — Analyst
@router.post("/", response_model=CommunicationOut)
def create_communication(
    incident_id: int,
    payload: CommunicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    _get_incident(incident_id, db)
    comm = Communication(
        incident_id=incident_id,
        comm_type=payload.comm_type,
        subject=payload.subject,
        content=payload.content,
        recipients=json.dumps(payload.recipients, ensure_ascii=False),
        status=CommStatus.draft,
        sent_by=current_user.id,
    )
    db.add(comm)
    db.commit()
    db.refresh(comm)
    return comm

# Phê duyệt nội dung — Analyst
@router.patch("/{comm_id}/approve", response_model=CommunicationOut)
def approve_communication(
    incident_id: int,
    comm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    comm = db.query(Communication).filter(
        Communication.id == comm_id,
        Communication.incident_id == incident_id
    ).first()
    if not comm:
        raise HTTPException(404, "Không tìm thấy thông báo")
    if comm.status != CommStatus.draft:
        raise HTTPException(400, "Chỉ có thể phê duyệt thông báo ở trạng thái draft")

    comm.is_approved = True
    comm.approved_by = current_user.id
    db.commit()
    db.refresh(comm)
    return comm

# Gửi thông báo — chỉ được gửi sau khi đã approved
@router.patch("/{comm_id}/send", response_model=CommunicationOut)
def send_communication(
    incident_id: int,
    comm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    comm = db.query(Communication).filter(
        Communication.id == comm_id,
        Communication.incident_id == incident_id
    ).first()
    if not comm:
        raise HTTPException(404, "Không tìm thấy thông báo")
    if not comm.is_approved:
        raise HTTPException(400, "Thông báo chưa được phê duyệt — không thể gửi")
    if comm.status == CommStatus.sent:
        raise HTTPException(400, "Thông báo đã được gửi trước đó")

    comm.status  = CommStatus.sent
    comm.sent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(comm)
    return comm

# Stakeholder xác nhận đã đọc
@router.patch("/{comm_id}/acknowledge", response_model=CommunicationOut)
def acknowledge_communication(
    incident_id: int,
    comm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    comm = db.query(Communication).filter(
        Communication.id == comm_id,
        Communication.incident_id == incident_id
    ).first()
    if not comm:
        raise HTTPException(404, "Không tìm thấy thông báo")
    if comm.status != CommStatus.sent:
        raise HTTPException(400, "Thông báo chưa được gửi")

    comm.status           = CommStatus.acknowledged
    comm.acknowledged_by  = current_user.id
    comm.acknowledged_at  = datetime.now(timezone.utc)
    db.commit()
    db.refresh(comm)
    return comm

# Xem lịch sử thông báo — ai được thông báo gì, lúc nào
@router.get("/log")
def communication_log(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _get_incident(incident_id, db)
    comms = db.query(Communication).filter(
        Communication.incident_id == incident_id
    ).order_by(Communication.sent_at.asc()).all()
    return [
        {
            "id": c.id,
            "type": c.comm_type,
            "subject": c.subject,
            "recipients": json.loads(c.recipients),
            "status": c.status,
            "sent_by": c.sent_by,
            "sent_at": c.sent_at,
            "acknowledged_by": c.acknowledged_by,
            "acknowledged_at": c.acknowledged_at,
            "is_approved": c.is_approved,
        }
        for c in comms
    ]