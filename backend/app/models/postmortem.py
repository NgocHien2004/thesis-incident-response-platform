from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.sql import func
from database import Base

class Postmortem(Base):
    __tablename__ = "postmortems"

    id                  = Column(Integer, primary_key=True, index=True)
    incident_id         = Column(Integer, ForeignKey("incidents.id"), nullable=False, unique=True)

    # Nội dung báo cáo
    root_cause          = Column(Text, nullable=False)
    timeline            = Column(Text, nullable=False)   # JSON: [{time, event, actor}]
    impact              = Column(Text, nullable=False)
    lessons_learned     = Column(Text, nullable=True)

    # Hành động phòng ngừa
    action_items        = Column(Text, nullable=True)    # JSON: [{task, owner, deadline, done}]

    # Người chịu trách nhiệm
    responsible_party   = Column(String(200), nullable=True)

    # Trạng thái
    is_finalized        = Column(Boolean, default=False)
    finalized_by        = Column(Integer, ForeignKey("users.id"), nullable=True)
    finalized_at        = Column(DateTime, nullable=True)

    created_by          = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at          = Column(DateTime, server_default=func.now())
    updated_at          = Column(DateTime, server_default=func.now(), onupdate=func.now())