from sqlalchemy import Column, Integer, DateTime, Unicode, UnicodeText
from database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id           = Column(Integer, primary_key=True, index=True)
    at           = Column(DateTime, nullable=False, index=True)
    user_id      = Column(Integer, nullable=True)
    username     = Column(Unicode(50), nullable=True)
    role         = Column(Unicode(30), nullable=True)
    action       = Column(Unicode(60), nullable=False, index=True)
    entity_type  = Column(Unicode(40), nullable=False)
    entity_id    = Column(Integer, nullable=True)
    incident_id  = Column(Integer, nullable=True, index=True)
    detail       = Column(UnicodeText, nullable=True)
    prev_hash    = Column(Unicode(64), nullable=False)
    row_hash     = Column(Unicode(64), nullable=False)
