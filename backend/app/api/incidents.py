from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
import json
from database import get_db
from app.models.incident import Incident, IncidentStatus
from app.models.alert import Alert, AlertStatus
from app.schemas.incident import IncidentCreate, IncidentOut, IncidentStatusUpdate
from app.core.dependencies import get_current_user, require_roles
from app.models.user import RoleEnum, User

router = APIRouter(prefix="/incidents", tags=["Incidents"])

# Xem danh sách
@router.get("/", response_model=List[IncidentOut])
def list_incidents(
    status: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Incident)
    if status:
        query = query.filter(Incident.status == status)
    return query.order_by(Incident.created_at.desc()).all()

# Xem chi tiết
@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Không tìm thấy incident")
    return incident

# Xem alerts thuộc incident
@router.get("/{incident_id}/alerts")
def get_incident_alerts(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Không tìm thấy incident")
    alerts = db.query(Alert).filter(Alert.incident_id == incident_id).all()
    return alerts

# Tạo incident từ alert — chỉ Analyst
@router.post("/", response_model=IncidentOut)
def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    # Kiểm tra tất cả alert_ids tồn tại và đã triage
    alerts = []
    for aid in payload.alert_ids:
        alert = db.query(Alert).filter(Alert.id == aid).first()
        if not alert:
            raise HTTPException(404, f"Alert {aid} không tồn tại")
        if alert.status not in [AlertStatus.triaged, AlertStatus.escalated]:
            raise HTTPException(
                400,
                f"Alert {aid} chưa được triage — chỉ có thể tạo incident từ alert đã triage"
            )
        alerts.append(alert)

    # Tạo checklist mặc định nếu không truyền vào
    default_checklist = payload.checklist or [
        "Xác nhận phạm vi ảnh hưởng",
        "Thu thập bằng chứng",
        "Phân tích IOC",
        "Đề xuất containment",
        "Thông báo stakeholder",
    ]

    incident = Incident(
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        commander_id=payload.commander_id,
        created_by=current_user.id,
        checklist=json.dumps(default_checklist, ensure_ascii=False),
        detected_at=datetime.now(timezone.utc),
    )
    db.add(incident)
    db.flush()  # lấy incident.id trước khi commit

    # Gán incident_id cho các alert liên quan
    for alert in alerts:
        alert.incident_id = incident.id
        alert.status = AlertStatus.escalated

    db.commit()
    db.refresh(incident)
    return incident

# Cập nhật trạng thái incident — Analyst
@router.patch("/{incident_id}/status", response_model=IncidentOut)
def update_incident_status(
    incident_id: int,
    payload: IncidentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Không tìm thấy incident")

    # Ghi timestamp theo trạng thái
    now = datetime.now(timezone.utc)
    if payload.status == IncidentStatus.contained:
        incident.contained_at = now
    elif payload.status == IncidentStatus.closed:
        if not incident.contained_at:
            raise HTTPException(400, "Incident chưa được contained — không thể đóng")
        incident.resolved_at = now

    incident.status = payload.status
    db.commit()
    db.refresh(incident)
    return incident