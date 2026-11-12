from sqlalchemy import Column, Integer, DateTime, Unicode, ForeignKey
from app.core.timeutils import utcnow
from database import Base

class Setting(Base):
    __tablename__ = "settings"

    key         = Column(Unicode(100), primary_key=True)
    value       = Column(Unicode(500), nullable=False)
    description = Column(Unicode(300), nullable=True)
    updated_at  = Column(DateTime, nullable=False, default=utcnow)
    updated_by  = Column(Integer, ForeignKey("users.id"), nullable=True)
