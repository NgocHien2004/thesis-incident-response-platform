from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.alert import AlertSource, AlertStatus, AlertSeverity

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