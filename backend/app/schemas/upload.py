from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel

class UploadOut(BaseModel):
    id: int
    incident_id: int
    original_filename: str
    data_type: str
    file_hash: str
    file_size_bytes: int
    row_count: Optional[int] = None
    processed_rows: int = 0
    status: str
    error_message: Optional[str] = None
    model_id: Optional[int] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    threshold_used: Optional[float] = None
    dangerous_labels_used: List[str] = []
    alert_count: int = 0
    avg_confidence: Optional[float] = None
    label_distribution: Dict[str, int] = {}
    uploaded_by: int
    uploaded_by_name: Optional[str] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    warnings: List[str] = []
