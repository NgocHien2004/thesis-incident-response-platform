from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class TimelineEvent(BaseModel):
    time: str
    event: str
    actor: Optional[str] = None

class ActionItem(BaseModel):
    task: str
    owner: str
    deadline: str
    done: bool = False

class PostmortemCreate(BaseModel):
    root_cause: str
    timeline: List[TimelineEvent]
    impact: str
    lessons_learned: Optional[str] = None
    action_items: Optional[List[ActionItem]] = []
    responsible_party: Optional[str] = None

class PostmortemUpdate(PostmortemCreate):
    pass

class PostmortemOut(BaseModel):
    id: int
    incident_id: int
    root_cause: str
    timeline: str
    impact: str
    lessons_learned: Optional[str]
    action_items: Optional[str]
    responsible_party: Optional[str]
    is_finalized: bool
    finalized_by: Optional[int]
    finalized_at: Optional[datetime]
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}