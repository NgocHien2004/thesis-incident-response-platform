from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field

class AlertOut(BaseModel):
    id: int
    incident_id: Optional[int] = None
    incident_code: Optional[str] = None
    upload_id: int
    upload_filename: Optional[str] = None
    row_index: int
    predicted_label: str
    confidence: float
    source_type: str
    auto_linked: bool
    linked_at: Optional[datetime] = None
    verification_status: str
    verified_by: Optional[int] = None
    verified_by_name: Optional[str] = None
    verified_at: Optional[datetime] = None
    note: Optional[str] = None
    created_at: datetime

class AlertDetail(AlertOut):
    row_data: Optional[Any] = None

class VerifyRequest(BaseModel):
    status: str
    note: Optional[str] = None

class BulkVerifyRequest(BaseModel):
    alert_ids: List[int] = Field(min_length=1, max_length=10000)
    status: str
    note: Optional[str] = None

class MoveRequest(BaseModel):
    alert_ids: List[int] = Field(min_length=1, max_length=10000)
    to_incident_id: Optional[int] = None     # rỗng: gỡ khỏi sự cố
    reason: Optional[str] = None

class MoveOut(BaseModel):
    id: int
    alert_id: int
    from_incident_id: Optional[int] = None
    to_incident_id: Optional[int] = None
    moved_by: int
    moved_by_name: Optional[str] = None
    moved_at: datetime
    reason: Optional[str] = None
