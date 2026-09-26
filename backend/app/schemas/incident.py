from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.incident import IncidentStatus, IncidentSeverity

class IncidentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: IncidentSeverity
    commander_id: Optional[int] = None
    alert_ids: List[int]           # danh sách alert gộp vào incident này
    checklist: Optional[List[str]] = None  # danh sách việc cần làm ban đầu

class IncidentOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: IncidentStatus
    severity: IncidentSeverity
    commander_id: Optional[int]
    created_by: int
    checklist: Optional[str]
    root_cause: Optional[str]
    detected_at: Optional[datetime]
    contained_at: Optional[datetime]
    resolved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus
    note: Optional[str] = None