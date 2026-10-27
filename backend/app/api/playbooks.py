from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from database import get_db
from app.models.playbook import Playbook, PlaybookStep, PlaybookType
from app.schemas.playbook import (
    PlaybookCreate, PlaybookUpdate, PlaybookOut, PlaybookSummary, PlaybookStepOut
)
from app.core.dependencies import get_current_user, require_roles
from app.models.user import RoleEnum, User

router = APIRouter(prefix="/playbooks", tags=["Playbooks"])


def _steps(db: Session, playbook_id: int):
    return db.query(PlaybookStep).filter(
        PlaybookStep.playbook_id == playbook_id
    ).order_by(PlaybookStep.step_order.asc()).all()


def _summary(pb: Playbook, steps) -> dict:
    return {
        "id": pb.id, "name": pb.name, "incident_type": pb.incident_type,
        "description": pb.description, "source": pb.source, "is_active": bool(pb.is_active),
        "step_count": len(steps), "required_count": sum(1 for s in steps if s.is_required),
        "created_at": pb.created_at, "updated_at": pb.updated_at,
    }


def _full(pb: Playbook, steps) -> PlaybookOut:
    return PlaybookOut(**_summary(pb, steps), steps=[PlaybookStepOut.model_validate(s) for s in steps])


def _name_taken(db: Session, name: str, except_id: Optional[int] = None) -> bool:
    q = db.query(Playbook).filter(func.lower(Playbook.name) == name.strip().lower())
    if except_id:
        q = q.filter(Playbook.id != except_id)
    return q.first() is not None


def _add_steps(db: Session, playbook_id: int, steps):
    for order, s in enumerate(steps, 1):
        db.add(PlaybookStep(
            playbook_id=playbook_id, step_order=order, title=s.title.strip(),
            description=s.description, phase=s.phase, owner_role=s.owner_role,
            due_hours=s.due_hours, is_required=s.is_required,
            reference=(s.reference or "").strip() or None,
        ))


# Danh sách playbook — mọi vai trò xem được
@router.get("/", response_model=List[PlaybookSummary])
def list_playbooks(
    incident_type: Optional[PlaybookType] = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Playbook)
    if incident_type:
        q = q.filter(Playbook.incident_type == incident_type)
    if active_only:
        q = q.filter(Playbook.is_active == True)  # noqa: E712
    out = []
    for pb in q.order_by(Playbook.name.asc()).all():
        out.append(_summary(pb, _steps(db, pb.id)))
    return out


@router.get("/{playbook_id}", response_model=PlaybookOut)
def get_playbook(
    playbook_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pb = db.query(Playbook).filter(Playbook.id == playbook_id).first()
    if not pb:
        raise HTTPException(404, "Không tìm thấy playbook")
    return _full(pb, _steps(db, pb.id))


# Tạo playbook — chỉ Analyst
@router.post("/", response_model=PlaybookOut)
def create_playbook(
    payload: PlaybookCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc)),
):
    if _name_taken(db, payload.name):
        raise HTTPException(400, "Đã có playbook trùng tên")
    pb = Playbook(
        name=payload.name.strip(), incident_type=payload.incident_type,
        description=payload.description, source=payload.source,
        is_active=True, created_by=current_user.id,
    )
    db.add(pb)
    db.flush()
    _add_steps(db, pb.id, payload.steps)
    db.commit()
    db.refresh(pb)
    return _full(pb, _steps(db, pb.id))


# Sửa playbook (thay toàn bộ các bước) hoặc ngừng dùng — chỉ Analyst.
# Công việc đã tạo cho các incident trước đó là bản sao nên không bị ảnh hưởng.
@router.put("/{playbook_id}", response_model=PlaybookOut)
def update_playbook(
    playbook_id: int,
    payload: PlaybookUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc)),
):
    pb = db.query(Playbook).filter(Playbook.id == playbook_id).first()
    if not pb:
        raise HTTPException(404, "Không tìm thấy playbook")
    if _name_taken(db, payload.name, except_id=pb.id):
        raise HTTPException(400, "Đã có playbook trùng tên")

    db.query(PlaybookStep).filter(PlaybookStep.playbook_id == pb.id).delete()
    _add_steps(db, pb.id, payload.steps)

    pb.name = payload.name.strip()
    pb.incident_type = payload.incident_type
    pb.description = payload.description
    pb.source = payload.source
    pb.is_active = payload.is_active
    db.info["audit_note"] = f"Cập nhật playbook, {len(payload.steps)} bước"
    db.commit()
    db.refresh(pb)
    return _full(pb, _steps(db, pb.id))
