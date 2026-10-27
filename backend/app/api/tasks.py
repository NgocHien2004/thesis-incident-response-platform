from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import timedelta
from database import get_db
from app.models.incident import Incident
from app.models.playbook import Playbook
from app.models.task import Task, TaskStatus
from app.schemas.task import TaskCreate, TaskUpdate, TaskOut, ApplyPlaybook
from app.core.dependencies import get_current_user, require_roles
from app.core.rules import require_not_closed
from app.core.timeutils import utcnow
from app.services.playbooks import instantiate_playbook
from app.models.user import RoleEnum, User

router = APIRouter(prefix="/incidents/{incident_id}/tasks", tags=["Tasks"])

OPEN = (TaskStatus.todo, TaskStatus.in_progress)

# Bảng chuyển trạng thái hợp lệ của một công việc
ALLOWED = {
    TaskStatus.todo:        {TaskStatus.in_progress, TaskStatus.done, TaskStatus.skipped},
    TaskStatus.in_progress: {TaskStatus.todo, TaskStatus.done, TaskStatus.skipped},
    TaskStatus.done:        {TaskStatus.in_progress},
    TaskStatus.skipped:     {TaskStatus.todo},
}


def _get_incident(incident_id: int, db: Session) -> Incident:
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(404, "Không tìm thấy incident")
    return incident


def _get_task(incident_id: int, task_id: int, db: Session) -> Task:
    task = db.query(Task).filter(Task.id == task_id, Task.incident_id == incident_id).first()
    if not task:
        raise HTTPException(404, "Không tìm thấy công việc")
    return task


def _out(task: Task) -> TaskOut:
    out = TaskOut.model_validate(task)
    out.is_overdue = bool(task.due_at and task.status in OPEN and task.due_at < utcnow())
    return out


def _check_assignee(db: Session, user_id: int):
    u = db.query(User).filter(User.id == user_id).first()
    if not u or not u.is_active or u.role not in (RoleEnum.it_helpdesk, RoleEnum.analyst_soc):
        raise HTTPException(400, "Người được giao phải là tài khoản IT/Helpdesk hoặc Analyst/SOC đang hoạt động")


@router.get("/", response_model=List[TaskOut])
def list_tasks(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_incident(incident_id, db)
    tasks = db.query(Task).filter(Task.incident_id == incident_id).order_by(
        Task.sort_order.asc(), Task.id.asc()
    ).all()
    return [_out(t) for t in tasks]


# Danh sách tài khoản có thể được giao việc — chỉ Analyst (dùng cho ô chọn người làm)
@router.get("/assignees")
def list_assignees(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc)),
):
    _get_incident(incident_id, db)
    users = db.query(User).filter(
        User.is_active == True,  # noqa: E712
        User.role.in_([RoleEnum.it_helpdesk, RoleEnum.analyst_soc]),
    ).order_by(User.username.asc()).all()
    return [{"id": x.id, "username": x.username, "role": x.role.value} for x in users]


@router.get("/summary")
def task_summary(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_incident(incident_id, db)
    tasks = db.query(Task).filter(Task.incident_id == incident_id).all()
    now = utcnow()
    finished = [t for t in tasks if t.status in (TaskStatus.done, TaskStatus.skipped)]
    return {
        "total": len(tasks),
        "required": sum(1 for t in tasks if t.is_required),
        "open_required": sum(1 for t in tasks if t.is_required and t.status in OPEN),
        "done": sum(1 for t in tasks if t.status == TaskStatus.done),
        "skipped": sum(1 for t in tasks if t.status == TaskStatus.skipped),
        "overdue": sum(1 for t in tasks if t.due_at and t.status in OPEN and t.due_at < now),
        "completion_pct": round(100 * len(finished) / len(tasks), 1) if tasks else None,
    }


# Áp dụng playbook cho incident — chỉ Analyst
@router.post("/apply-playbook")
def apply_playbook(
    incident_id: int,
    payload: ApplyPlaybook,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc)),
):
    incident = require_not_closed(_get_incident(incident_id, db))
    pb = db.query(Playbook).filter(Playbook.id == payload.playbook_id).first()
    if not pb:
        raise HTTPException(404, "Không tìm thấy playbook")
    if not pb.is_active:
        raise HTTPException(400, "Playbook này đã ngừng sử dụng")
    created, skipped = instantiate_playbook(db, incident, pb, current_user.id)
    db.info["audit_note"] = f"Áp dụng playbook '{pb.name}': {len(created)} công việc mới"
    db.commit()
    for t in created:
        db.refresh(t)
    return {"created": len(created), "already_present": skipped, "tasks": [_out(t) for t in created]}


# Tạo công việc thủ công — chỉ Analyst
@router.post("/", response_model=TaskOut)
def create_task(
    incident_id: int,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc)),
):
    incident = require_not_closed(_get_incident(incident_id, db))
    if payload.assignee_id:
        _check_assignee(db, payload.assignee_id)
    if payload.owner_role == RoleEnum.stakeholder:
        raise HTTPException(400, "Công việc chỉ giao cho IT/Helpdesk hoặc Analyst/SOC")
    last = db.query(Task).filter(Task.incident_id == incident_id).count()
    task = Task(
        incident_id=incident_id, playbook_id=None, sort_order=last + 1,
        title=payload.title.strip(), description=payload.description,
        phase=payload.phase, owner_role=payload.owner_role,
        status=TaskStatus.todo, is_required=payload.is_required,
        assignee_id=payload.assignee_id,
        due_at=utcnow() + timedelta(hours=payload.due_hours) if payload.due_hours is not None else None,
        created_by=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _out(task)


# Cập nhật công việc: IT và Analyst đổi trạng thái; chỉ Analyst giao việc, đặt hạn
@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    incident_id: int,
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc)),
):
    incident = require_not_closed(_get_incident(incident_id, db))
    task = _get_task(incident_id, task_id, db)
    sent = payload.model_fields_set
    is_analyst = current_user.role == RoleEnum.analyst_soc
    is_commander = incident.commander_id == current_user.id

    if ({"assignee_id", "due_at"} & sent) and not is_analyst:
        raise HTTPException(403, "Chỉ Analyst mới giao việc hoặc đặt hạn")

    if "assignee_id" in sent:
        if payload.assignee_id is not None:
            _check_assignee(db, payload.assignee_id)
        task.assignee_id = payload.assignee_id
    if "due_at" in sent:
        task.due_at = payload.due_at.replace(tzinfo=None) if payload.due_at else None

    new = payload.status
    note = (payload.note or "").strip()
    if new is not None:
        cur = task.status
        if new == cur:
            raise HTTPException(400, f"Công việc đã ở trạng thái '{cur.value}'")
        if new not in ALLOWED[cur]:
            raise HTTPException(400, f"Không thể chuyển công việc từ '{cur.value}' sang '{new.value}'")

        if not is_analyst:
            mine = task.assignee_id == current_user.id or (
                task.assignee_id is None and task.owner_role == RoleEnum.it_helpdesk
            )
            if not mine:
                raise HTTPException(403, "Chỉ làm được công việc được giao cho mình hoặc công việc chưa giao của IT")
            if new == TaskStatus.skipped or cur in (TaskStatus.done, TaskStatus.skipped):
                raise HTTPException(403, "Chỉ Analyst mới bỏ qua hoặc mở lại công việc")

        if new == TaskStatus.skipped:
            if not note:
                raise HTTPException(400, "Cần ghi lý do khi bỏ qua công việc")
            if task.is_required and not is_commander:
                raise HTTPException(403, "Chỉ commander của vụ mới được bỏ qua công việc bắt buộc")
        if cur == TaskStatus.done and not note:
            raise HTTPException(400, "Cần ghi lý do khi mở lại công việc đã hoàn thành")
        if cur == TaskStatus.skipped and task.is_required and not is_commander:
            raise HTTPException(403, "Chỉ commander của vụ mới được mở lại công việc bắt buộc đã bỏ qua")

        if new == TaskStatus.in_progress and task.assignee_id is None:
            task.assignee_id = current_user.id   # nhận việc
        if new in (TaskStatus.done, TaskStatus.skipped):
            task.completed_by = current_user.id
            task.completed_at = utcnow()
        else:
            task.completed_by = None
            task.completed_at = None
        task.status = new

    if "note" in sent and payload.note is not None:
        task.note = payload.note

    db.commit()
    db.refresh(task)
    return _out(task)


# Xóa công việc tạo tay chưa hoàn thành — chỉ Analyst
@router.delete("/{task_id}")
def delete_task(
    incident_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.analyst_soc)),
):
    require_not_closed(_get_incident(incident_id, db))
    task = _get_task(incident_id, task_id, db)
    if task.playbook_id is not None:
        raise HTTPException(400, "Công việc từ playbook không xóa được; hãy bỏ qua kèm lý do")
    if task.status == TaskStatus.done:
        raise HTTPException(400, "Không xóa công việc đã hoàn thành")
    db.delete(task)
    db.commit()
    return {"message": "Đã xóa công việc"}
