from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.communication import CommType, CommStatus

class CommunicationCreate(BaseModel):
    comm_type: CommType
    subject: str
    content: str
    recipients: List[str]   # ["stakeholder01", "legal@company.com"]

class CommunicationOut(BaseModel):
    id: int
    incident_id: int
    comm_type: CommType
    subject: str
    content: str
    recipients: str
    status: CommStatus
    sent_by: int
    sent_at: Optional[datetime]
    acknowledged_by: Optional[int]
    acknowledged_at: Optional[datetime]
    is_approved: bool
    approved_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}