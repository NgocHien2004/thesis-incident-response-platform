from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.recovery import RecoveryActionType, RecoveryStatus

class RecoveryActionCreate(BaseModel):
    action_type: RecoveryActionType
    description: str
    assigned_to: Optional[int] = None

class RecoveryActionUpdate(BaseModel):
    status: RecoveryStatus
    note: Optional[str] = None

class RecoveryConfirm(BaseModel):
    confirm_note: Optional[str] = None

class RecoveryActionOut(BaseModel):
    id: int
    incident_id: int
    action_type: RecoveryActionType
    description: str
    status: RecoveryStatus
    note: Optional[str]
    assigned_to: Optional[int]
    executed_by: Optional[int]
    executed_at: Optional[datetime]
    confirmed_by: Optional[int]
    confirmed_at: Optional[datetime]
    confirm_note: Optional[str]
    is_confirmed: bool
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}