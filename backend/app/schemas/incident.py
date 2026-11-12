from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = None
    attack_type: str
    severity: str
    occurred_at: datetime
    source: str

class IncidentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    description: Optional[str] = None
    attack_type: Optional[str] = None
    severity: Optional[str] = None
    occurred_at: Optional[datetime] = None
    source: Optional[str] = None

class StatusChange(BaseModel):
    new_status: str
    note: Optional[str] = None

class IncidentOut(BaseModel):
    id: int
    code: str
    title: str
    description: Optional[str] = None
    attack_type: str
    attack_type_name: Optional[str] = None
    severity: str
    occurred_at: datetime
    source: str
    status: str
    created_by: int
    created_by_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    alert_count: int = 0
    upload_count: int = 0

class IncidentDetail(IncidentOut):
    unverified_alerts: int = 0
    verified_alerts: int = 0
    dismissed_alerts: int = 0
    processing_uploads: int = 0
    allowed_transitions: List[str] = []
    can_delete: bool = False

class HistoryOut(BaseModel):
    id: int
    incident_id: int
    old_status: Optional[str] = None
    new_status: str
    changed_by: int
    changed_by_name: Optional[str] = None
    changed_at: datetime
    note: Optional[str] = None

class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    pages: int
