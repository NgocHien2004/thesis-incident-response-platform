from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import json
from database import get_db
from app.models.postmortem import Postmortem
from app.models.incident import Incident, IncidentStatus
from app.schemas.postmortem import PostmortemCreate, PostmortemUpdate, PostmortemOut
from app.core.dependencies import get_current_user, require_roles
from app.models.user import RoleEnum, User

router = APIRouter(prefix="/incidents/{incident_id}/postmortem", tags=["Postmortem"])

def _get_incident(incident_id: int, db: Session) -> Incident:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Không tìm thấy incident")
    return incident

# Xem postmortem
@router.get("/", response_model=PostmortemOut)
def get_postmortem(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pm = db.query(Postmortem).filter(
        Postmortem.incident_id == incident_id
    ).first()
    if not pm:
        raise HTTPException(404, "Chưa có postmortem cho incident này")
    return pm

# Tạo postmortem — chỉ Analyst
@router.post("/", response_model=PostmortemOut)
def create_postmortem(
    incident_id: int,
    payload: PostmortemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    incident = _get_incident(incident_id, db)

    # Kiểm tra chưa có postmortem
    existing = db.query(Postmortem).filter(
        Postmortem.incident_id == incident_id
    ).first()
    if existing:
        raise HTTPException(400, "Incident này đã có postmortem — dùng PUT để cập nhật")

    pm = Postmortem(
        incident_id=incident_id,
        root_cause=payload.root_cause,
        timeline=json.dumps(
            [e.model_dump() for e in payload.timeline],
            ensure_ascii=False
        ),
        impact=payload.impact,
        lessons_learned=payload.lessons_learned,
        action_items=json.dumps(
            [a.model_dump() for a in (payload.action_items or [])],
            ensure_ascii=False
        ),
        responsible_party=payload.responsible_party,
        created_by=current_user.id,
    )
    db.add(pm)

    # Cập nhật root_cause vào incident
    incident.root_cause = payload.root_cause
    db.commit()
    db.refresh(pm)
    return pm

# Cập nhật postmortem
@router.put("/", response_model=PostmortemOut)
def update_postmortem(
    incident_id: int,
    payload: PostmortemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    pm = db.query(Postmortem).filter(
        Postmortem.incident_id == incident_id
    ).first()
    if not pm:
        raise HTTPException(404, "Chưa có postmortem — dùng POST để tạo")
    if pm.is_finalized:
        raise HTTPException(400, "Postmortem đã được finalize — không thể chỉnh sửa")

    pm.root_cause       = payload.root_cause
    pm.timeline         = json.dumps(
        [e.model_dump() for e in payload.timeline], ensure_ascii=False
    )
    pm.impact           = payload.impact
    pm.lessons_learned  = payload.lessons_learned
    pm.action_items     = json.dumps(
        [a.model_dump() for a in (payload.action_items or [])], ensure_ascii=False
    )
    pm.responsible_party = payload.responsible_party
    db.commit()
    db.refresh(pm)
    return pm

# Finalize postmortem + đóng incident
@router.patch("/finalize", response_model=PostmortemOut)
def finalize_postmortem(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc))
):
    pm = db.query(Postmortem).filter(
        Postmortem.incident_id == incident_id
    ).first()
    if not pm:
        raise HTTPException(404, "Chưa có postmortem")
    if pm.is_finalized:
        raise HTTPException(400, "Đã finalize rồi")

    # Kiểm tra action_items có đủ không
    action_items = json.loads(pm.action_items or "[]")
    if not action_items:
        raise HTTPException(
            400,
            "Cần có ít nhất 1 action item trước khi finalize"
        )

    pm.is_finalized = True
    pm.finalized_by = current_user.id
    pm.finalized_at = datetime.now(timezone.utc)

    # Đóng incident
    incident = _get_incident(incident_id, db)
    incident.status     = IncidentStatus.closed
    incident.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(pm)
    return pm

# Cập nhật trạng thái action item
@router.patch("/action-items/{item_index}")
def update_action_item(
    incident_id: int,
    item_index: int,
    done: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pm = db.query(Postmortem).filter(
        Postmortem.incident_id == incident_id
    ).first()
    if not pm:
        raise HTTPException(404, "Không tìm thấy postmortem")

    items = json.loads(pm.action_items or "[]")
    if item_index >= len(items):
        raise HTTPException(400, f"Không có action item index {item_index}")

    items[item_index]["done"] = done
    pm.action_items = json.dumps(items, ensure_ascii=False)
    db.commit()
    return {"message": f"Action item {item_index} cập nhật thành {'done' if done else 'pending'}"}