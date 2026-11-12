from sqlalchemy import Column, Integer, Boolean, DateTime, Unicode, UnicodeText, ForeignKey, Index
from app.core.timeutils import utcnow
from database import Base

class AttackType(Base):
    __tablename__ = "attack_types"

    code      = Column(Unicode(50), primary_key=True)
    name_vi   = Column(Unicode(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

class Incident(Base):
    __tablename__ = "incidents"

    id          = Column(Integer, primary_key=True, index=True)
    code        = Column(Unicode(30), unique=True, nullable=False)
    title       = Column(Unicode(200), nullable=False)
    description = Column(UnicodeText, nullable=True)
    attack_type = Column(Unicode(50), ForeignKey("attack_types.code"), nullable=False)
    severity    = Column(Unicode(20), nullable=False)
    occurred_at = Column(DateTime, nullable=False)
    source      = Column(Unicode(30), nullable=False)
    status      = Column(Unicode(20), nullable=False, default="new")
    created_by  = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at  = Column(DateTime, nullable=False, default=utcnow)
    updated_at  = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    resolved_at = Column(DateTime, nullable=True)
    closed_at   = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_incidents_status", "status"),
        Index("ix_incidents_attack_type", "attack_type"),
        Index("ix_incidents_occurred_at", "occurred_at"),
    )

class IncidentStatusHistory(Base):
    __tablename__ = "incident_status_history"

    id          = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False, index=True)
    old_status  = Column(Unicode(20), nullable=True)
    new_status  = Column(Unicode(20), nullable=False)
    changed_by  = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at  = Column(DateTime, nullable=False, default=utcnow)
    note        = Column(UnicodeText, nullable=True)
