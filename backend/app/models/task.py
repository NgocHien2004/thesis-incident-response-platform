from sqlalchemy import Column, Integer, Enum, DateTime, ForeignKey, Boolean, Unicode, UnicodeText
from app.core.timeutils import utcnow
from app.models.user import RoleEnum
from app.models.playbook import TaskPhase
from database import Base
import enum


class TaskStatus(str, enum.Enum):
    todo        = "todo"
    in_progress = "in_progress"
    done        = "done"
    skipped     = "skipped"


class Task(Base):
    __tablename__ = "tasks"

    id           = Column(Integer, primary_key=True, index=True)
    incident_id  = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    playbook_id  = Column(Integer, ForeignKey("playbooks.id"), nullable=True)   # rỗng nếu tạo tay
    sort_order   = Column(Integer, nullable=False, default=0)
    title        = Column(Unicode(200), nullable=False)
    description  = Column(UnicodeText, nullable=True)
    phase        = Column(Enum(TaskPhase), nullable=False, default=TaskPhase.analysis)
    owner_role   = Column(Enum(RoleEnum), nullable=True)
    status       = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.todo)
    is_required  = Column(Boolean, default=False)

    assignee_id  = Column(Integer, ForeignKey("users.id"), nullable=True)
    due_at       = Column(DateTime, nullable=True)
    note         = Column(UnicodeText, nullable=True)

    completed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    completed_at = Column(DateTime, nullable=True)

    created_by   = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at   = Column(DateTime, default=utcnow)
    updated_at   = Column(DateTime, default=utcnow, onupdate=utcnow)
