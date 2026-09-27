from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.containment import ContainmentAction, ContainmentStatus

class ContainmentCreate(BaseModel):
    action_type: ContainmentAction
    target: str
    reason: str
    risk_level: str = "medium"

class ContainmentReview(BaseModel):
    approved: bool
    review_note: Optional[str] = None

class ContainmentExecute(BaseModel):
    execution_note: str

class ContainmentOut(BaseModel):
    id: int
    incident_id: int
    action_type: ContainmentAction
    target: str
    reason: str
    risk_level: str
    status: ContainmentStatus
    proposed_by: int
    proposed_at: datetime
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    review_note: Optional[str]
    executed_by: Optional[int]
    executed_at: Optional[datetime]
    execution_note: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}