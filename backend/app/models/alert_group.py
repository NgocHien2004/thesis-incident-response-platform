from sqlalchemy import Column, Integer, DateTime, ForeignKey, Unicode, UnicodeText
from app.core.timeutils import utcnow
from database import Base

class AlertGroup(Base):
    __tablename__ = "alert_groups"

    id              = Column(Integer, primary_key=True, index=True)
    title           = Column(Unicode(200), nullable=False)
    ioc             = Column(UnicodeText, nullable=True)
    affected_asset  = Column(Integer, ForeignKey("assets.id"), nullable=True)
    alert_count     = Column(Integer, default=1)
    first_seen      = Column(DateTime, default=utcnow)
    last_seen       = Column(DateTime, default=utcnow, onupdate=utcnow)
    created_at      = Column(DateTime, default=utcnow)