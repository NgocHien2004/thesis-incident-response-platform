from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone
import json
from database import get_db
from app.models.incident import Incident, IncidentStatus
from app.models.alert import Alert, AlertStatus
from app.models.containment import Containment, ContainmentStatus
from app.models.recovery import RecoveryAction, RecoveryStatus
from app.models.audit_log import AuditLog
from app.core.audit import label_for
from sqlalchemy import or_, and_
from app.schemas.incident import IncidentCreate, IncidentOut, IncidentStatusUpdate
from app.core.dependencies import get_current_user, require_roles
from app.models.user import RoleEnum, User

router = APIRouter(prefix="/incidents", tags=["Incidents"])

# Bảng chuyển trạng thái hợp lệ (không cho nhảy bước tùy ý)
ALLOWED = {
    IncidentStatus.open:          {IncidentStatus.investigating},
    IncidentStatus.investigating: {IncidentStatus.contained},
    IncidentStatus.contained:     {IncidentStatus.recovering, IncidentStatus.investigating, IncidentStatus.closed},
    IncidentStatus.recovering:    {IncidentStatus.closed, IncidentStatus.investigating},
    IncidentStatus.closed:        {IncidentStatus.investigating},
}


def closure_unmet(db: Session, incident: Incident) -> list:
    """Tiêu chí đóng vụ việc (theo bước 9 và 11 của đề: recovery phải được chủ hệ thống xác nhận)."""
    unmet = []
    if not incident.contained_at:
        unmet.append("chưa có mốc khống chế (contained)")
    containments = db.query(Containment).filter(Containment.incident_id == incident.id).all()
    pending = [c for c in containments if c.status in (ContainmentStatus.proposed, ContainmentStatus.approved)]
    if pending:
        unmet.append(f"{len(pending)} đề xuất containment chưa xử lý xong")
    unverified = [c for c in containments if c.status == ContainmentStatus.executed]
    if unverified:
        unmet.append(f"{len(unverified)} containment đã thực hiện nhưng chưa được xác minh")
    actions = db.query(RecoveryAction).filter(RecoveryAction.incident_id == incident.id).all()
    active = [a for a in actions if a.status in (RecoveryStatus.pending, RecoveryStatus.in_progress)
              or (a.status == RecoveryStatus.done and not a.is_confirmed)]
    if active:
        unmet.append(f"{len(active)} hành động recovery chưa hoàn tất hoặc chưa được chủ hệ thống xác nhận")
    if not any(a.status == RecoveryStatus.done and a.is_confirmed for a in actions):
        unmet.append("chưa có hành động recovery nào được chủ hệ thống xác nhận")
    return unmet

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

    commander_id = payload.commander_id or current_user.id
    commander = db.query(User).filter(User.id == commander_id).first()
    if not commander or not commander.is_active or commander.role != RoleEnum.analyst_soc:
        raise HTTPException(400, "Commander phải là một tài khoản Analyst/SOC đang hoạt động")

    incident = Incident(
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        commander_id=commander_id,
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

# Cập nhật trạng thái incident — Analyst (đóng/mở lại: chỉ commander của vụ)
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

    current, new = incident.status, payload.status
    if new == current:
        raise HTTPException(400, f"Incident đã ở trạng thái '{current.value}'")
    if new not in ALLOWED[current]:
        raise HTTPException(400, f"Không thể chuyển từ '{current.value}' sang '{new.value}'")

    going_back = new == IncidentStatus.investigating and current != IncidentStatus.open
    if going_back and not (payload.note and payload.note.strip()):
        raise HTTPException(400, "Cần ghi lý do khi quay lại điều tra hoặc mở lại incident")
    if (new == IncidentStatus.closed or current == IncidentStatus.closed) \
            and incident.commander_id != current_user.id:
        raise HTTPException(403, "Chỉ commander của vụ mới được đóng hoặc mở lại incident")

    if new == IncidentStatus.contained:
        done = db.query(Containment).filter(
            Containment.incident_id == incident_id,
            Containment.status.in_([ContainmentStatus.executed, ContainmentStatus.verified])
        ).count()
        if not done:
            raise HTTPException(400, "Cần ít nhất một containment đã thực hiện trước khi chuyển sang 'contained'")
    if new == IncidentStatus.recovering:
        if not db.query(RecoveryAction).filter(RecoveryAction.incident_id == incident_id).count():
            raise HTTPException(400, "Cần có ít nhất một hành động recovery trước khi chuyển sang 'recovering'")
    if new == IncidentStatus.closed:
        unmet = closure_unmet(db, incident)
        if unmet:
            raise HTTPException(400, "Chưa đủ tiêu chí đóng: " + "; ".join(unmet))

    now = datetime.now(timezone.utc)
    if new == IncidentStatus.contained and not incident.contained_at:
        incident.contained_at = now
    if new == IncidentStatus.closed:
        incident.resolved_at = now
    if current == IncidentStatus.closed:
        incident.resolved_at = None

    db.info["audit_note"] = payload.note
    incident.status = new
    db.commit()
    db.refresh(incident)
    return incident


# Timeline của incident — dựng từ nhật ký kiểm toán
@router.get("/{incident_id}/timeline")
def incident_timeline(
    incident_id: int,
    include_views: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Không tìm thấy incident")
    alert_ids = [a.id for a in db.query(Alert.id).filter(Alert.incident_id == incident_id).all()]
    cond = AuditLog.incident_id == incident_id
    if alert_ids:
        cond = or_(cond, and_(AuditLog.entity_type == "alert", AuditLog.entity_id.in_(alert_ids)))
    rows = db.query(AuditLog).filter(cond).order_by(AuditLog.at.asc(), AuditLog.id.asc()).all()

    items = []
    for r in rows:
        detail = json.loads(r.detail) if r.detail else {}
        if r.action == "custody.created" and detail.get("action") == "accessed" and not include_views:
            continue
        items.append({
            "id": r.id, "at": r.at, "actor": r.username or "system", "role": r.role,
            "action": r.action, "label": label_for(r.action, detail),
            "entity_type": r.entity_type, "entity_id": r.entity_id, "detail": detail,
        })
    return items
