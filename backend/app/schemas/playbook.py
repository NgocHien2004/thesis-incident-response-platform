from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.models.user import RoleEnum
from app.models.playbook import PlaybookType, TaskPhase


class PlaybookStepIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    phase: TaskPhase
    owner_role: Optional[RoleEnum] = None
    due_hours: Optional[int] = Field(default=None, ge=0, le=24 * 90)
    is_required: bool = True
    reference: Optional[str] = Field(default=None, max_length=100)

    @field_validator("owner_role")
    @classmethod
    def owner_must_work_tasks(cls, v):
        if v == RoleEnum.stakeholder:
            raise ValueError("Công việc trong playbook chỉ giao cho IT/Helpdesk hoặc Analyst/SOC")
        return v


class PlaybookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    incident_type: PlaybookType
    description: Optional[str] = None
    source: Optional[str] = Field(default=None, max_length=300)
    steps: List[PlaybookStepIn] = Field(min_length=1, max_length=40)


class PlaybookUpdate(PlaybookCreate):
    is_active: bool = True


class PlaybookStepOut(BaseModel):
    id: int
    step_order: int
    title: str
    description: Optional[str]
    phase: TaskPhase
    owner_role: Optional[RoleEnum]
    due_hours: Optional[int]
    is_required: bool
    reference: Optional[str] = None

    model_config = {"from_attributes": True}


class PlaybookSummary(BaseModel):
    id: int
    name: str
    incident_type: PlaybookType
    description: Optional[str]
    source: Optional[str]
    is_active: bool
    step_count: int
    required_count: int
    created_at: datetime
    updated_at: datetime


class PlaybookOut(PlaybookSummary):
    steps: List[PlaybookStepOut]
