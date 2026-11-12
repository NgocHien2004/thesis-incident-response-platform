from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class LabelUpdate(BaseModel):
    is_dangerous: Optional[bool] = None
    is_active: Optional[bool] = None
    name_vi: Optional[str] = None

class SettingUpdate(BaseModel):
    value: str
