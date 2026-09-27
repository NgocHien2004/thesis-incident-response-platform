from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ImpactAnalysisCreate(BaseModel):
    ioc_list: Optional[List[str]] = []
    affected_assets: Optional[List[int]] = []
    affected_accounts: Optional[List[str]] = []
    attck_techniques: Optional[List[str]] = []
    attck_version: Optional[str] = "14.1"
    related_events: Optional[str] = None
    summary: str

class ImpactAnalysisOut(BaseModel):
    id: int
    incident_id: int
    ioc_list: Optional[str]
    affected_assets: Optional[str]
    affected_accounts: Optional[str]
    attck_techniques: Optional[str]
    attck_version: Optional[str]
    related_events: Optional[str]
    summary: Optional[str]
    ai_suggested: Optional[str]
    analyzed_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}