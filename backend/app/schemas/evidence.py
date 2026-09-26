from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.evidence import EvidenceType

class EvidenceCreate(BaseModel):
    title: str
    evidence_type: EvidenceType
    description: Optional[str] = None
    source: Optional[str] = None
    file_hash: Optional[str] = None
    file_path: Optional[str] = None
    content: Optional[str] = None

class EvidenceOut(BaseModel):
    id: int
    incident_id: int
    title: str
    evidence_type: EvidenceType
    description: Optional[str]
    source: Optional[str]
    file_hash: Optional[str]
    file_path: Optional[str]
    content: Optional[str]
    is_locked: bool
    collected_by: int
    collected_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}

class CustodyLogOut(BaseModel):
    id: int
    evidence_id: int
    action: str
    performed_by: int
    note: Optional[str]
    performed_at: datetime

    model_config = {"from_attributes": True}