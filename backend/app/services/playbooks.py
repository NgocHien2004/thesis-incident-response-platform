from datetime import timedelta
from sqlalchemy.orm import Session

from app.core.timeutils import utcnow
from app.models.incident import Incident
from app.models.playbook import Playbook, PlaybookStep
from app.models.task import Task, TaskStatus


def instantiate_playbook(db: Session, incident: Incident, playbook: Playbook, created_by: int):
    """Tạo công việc cho incident từ các bước của playbook.

    Bước nào đã có công việc cùng playbook và cùng tiêu đề trong incident thì bỏ qua,
    nên áp dụng lại cùng playbook không tạo trùng. Trả về (danh sách task mới, số bước đã có).
    """
    steps = db.query(PlaybookStep).filter(
        PlaybookStep.playbook_id == playbook.id
    ).order_by(PlaybookStep.step_order.asc()).all()

    existing = {
        t.title for t in db.query(Task).filter(
            Task.incident_id == incident.id, Task.playbook_id == playbook.id
        ).all()
    }
    base = incident.detected_at or incident.created_at or utcnow()
    base = base.replace(tzinfo=None)
    offset = db.query(Task).filter(Task.incident_id == incident.id).count()

    created, skipped = [], 0
    for step in steps:
        if step.title in existing:
            skipped += 1
            continue
        task = Task(
            incident_id=incident.id,
            playbook_id=playbook.id,
            sort_order=offset + step.step_order,
            title=step.title,
            description=step.description,
            phase=step.phase,
            owner_role=step.owner_role,
            status=TaskStatus.todo,
            is_required=bool(step.is_required),
            due_at=base + timedelta(hours=step.due_hours) if step.due_hours is not None else None,
            created_by=created_by,
        )
        db.add(task)
        created.append(task)
    return created, skipped
