from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from app.models.user import RoleEnum
from app.models.playbook import TaskPhase
from app.models.task import TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    phase: TaskPhase = TaskPhase.analysis
    owner_role: Optional[RoleEnum] = None
    assignee_id: Optional[int] = None
    due_hours: Optional[int] = Field(default=None, ge=0, le=24 * 90)
    is_required: bool = False


class TaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    assignee_id: Optional[int] = None
    due_at: Optional[datetime] = None
    note: Optional[str] = None


class ApplyPlaybook(BaseModel):
    playbook_id: int


class TaskOut(BaseModel):
    id: int
    incident_id: int
    playbook_id: Optional[int]
    sort_order: int
    title: str
    description: Optional[str]
    phase: TaskPhase
    owner_role: Optional[RoleEnum]
    status: TaskStatus
    is_required: bool
    assignee_id: Optional[int]
    due_at: Optional[datetime]
    note: Optional[str]
    completed_by: Optional[int]
    completed_at: Optional[datetime]
    created_by: int
    created_at: datetime
    updated_at: datetime
    is_overdue: bool = False

    model_config = {"from_attributes": True}
