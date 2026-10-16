from fastapi import HTTPException
from app.models.incident import IncidentStatus


def require_not_closed(incident):
    if incident.status == IncidentStatus.closed:
        raise HTTPException(409, "Incident đã đóng — hãy mở lại incident nếu cần thay đổi")
    return incident


def require_status(incident, allowed, message):
    if incident.status not in allowed:
        raise HTTPException(409, message)
    return incident
