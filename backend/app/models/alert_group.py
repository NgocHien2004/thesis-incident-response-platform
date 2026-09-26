from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base

class AlertGroup(Base):
    __tablename__ = "alert_groups"

    id              = Column(Integer, primary_key=True, index=True)
    title           = Column(String(200), nullable=False)
    ioc             = Column(Text, nullable=True)
    affected_asset  = Column(Integer, ForeignKey("assets.id"), nullable=True)
    alert_count     = Column(Integer, default=1)
    first_seen      = Column(DateTime, server_default=func.now())
    last_seen       = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_at      = Column(DateTime, server_default=func.now())