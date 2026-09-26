from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.asset import AssetType, CriticalityLevel

class AssetCreate(BaseModel):
    name: str
    asset_type: AssetType
    criticality: CriticalityLevel
    owner: Optional[str] = None
    description: Optional[str] = None
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    data_processed: Optional[str] = None
    dependencies: Optional[str] = None

class AssetUpdate(AssetCreate):
    pass

class AssetOut(AssetCreate):
    id: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}