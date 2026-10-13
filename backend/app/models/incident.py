from sqlalchemy import Column, Integer, Enum, DateTime, ForeignKey, Unicode, UnicodeText
from app.core.timeutils import utcnow
from database import Base
import enum

class IncidentStatus(str, enum.Enum):
    open         = "open"
    investigating = "investigating"
    contained    = "contained"
    recovering   = "recovering"
    closed       = "closed"

class IncidentSeverity(str, enum.Enum):
    critical = "critical"
    high     = "high"
    medium   = "medium"
    low      = "low"

class Incident(Base):
    __tablename__ = "incidents"

    id              = Column(Integer, primary_key=True, index=True)
    title           = Column(Unicode(200), nullable=False)
    description     = Column(UnicodeText, nullable=True)
    status          = Column(Enum(IncidentStatus), nullable=False, default=IncidentStatus.open)
    severity        = Column(Enum(IncidentSeverity), nullable=False)
    commander_id    = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by      = Column(Integer, ForeignKey("users.id"), nullable=False)
    checklist       = Column(UnicodeText, nullable=True)   # JSON string
    root_cause      = Column(UnicodeText, nullable=True)
    detected_at     = Column(DateTime, nullable=True)
    contained_at    = Column(DateTime, nullable=True)
    resolved_at     = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=utcnow)
    updated_at      = Column(DateTime, default=utcnow, onupdate=utcnow)