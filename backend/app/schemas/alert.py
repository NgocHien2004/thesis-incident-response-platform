from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.alert import AlertSource, AlertStatus, AlertSeverity
from typing import Optional
from datetime import datetime

class AlertCreate(BaseModel):
    title: str
    description: Optional[str] = None
    source: AlertSource
    severity: AlertSeverity = AlertSeverity.medium
    source_ref: Optional[str] = None
    ioc: Optional[str] = None
    affected_asset: Optional[int] = None
    raw_data: Optional[str] = None

class AlertOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    source: AlertSource
    severity: AlertSeverity
    status: AlertStatus
    source_ref: Optional[str]
    ioc: Optional[str]
    affected_asset: Optional[int]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class TriageRequest(BaseModel):
    triage_type: str
    triage_severity: AlertSeverity
    triage_confidence: int          # 1-100
    triage_assignee: Optional[int] = None
    triage_sla_hours: int           # 4, 8, 24, 48, 72...
    triage_note: Optional[str] = None

class AlertTriaged(AlertOut):
    triage_type: Optional[str]
    triage_severity: Optional[AlertSeverity]
    triage_confidence: Optional[int]
    triage_assignee: Optional[int]
    triage_sla_hours: Optional[int]
    triage_sla_deadline: Optional[datetime]
    triage_note: Optional[str]
    triaged_by: Optional[int]
    triaged_at: Optional[datetime]

    model_config = {"from_attributes": True}