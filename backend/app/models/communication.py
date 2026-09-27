from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.sql import func
from database import Base
import enum

class CommType(str, enum.Enum):
    internal_update   = "internal_update"
    stakeholder_notify = "stakeholder_notify"
    escalation        = "escalation"
    external          = "external"
    other             = "other"

class CommStatus(str, enum.Enum):
    draft     = "draft"
    sent      = "sent"
    acknowledged = "acknowledged"

class Communication(Base):
    __tablename__ = "communications"

    id              = Column(Integer, primary_key=True, index=True)
    incident_id     = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    comm_type       = Column(Enum(CommType), nullable=False)
    subject         = Column(String(200), nullable=False)
    content         = Column(Text, nullable=False)
    recipients      = Column(Text, nullable=False)   # JSON: ["email1", "role1"]
    status          = Column(Enum(CommStatus), nullable=False, default=CommStatus.draft)

    # Người gửi
    sent_by         = Column(Integer, ForeignKey("users.id"), nullable=False)
    sent_at         = Column(DateTime, nullable=True)

    # Người xác nhận đã đọc
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)

    is_approved     = Column(Boolean, default=False)  # nội dung đã được duyệt
    approved_by     = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at      = Column(DateTime, server_default=func.now())
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())