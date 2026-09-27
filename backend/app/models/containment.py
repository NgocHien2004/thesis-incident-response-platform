from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base
import enum

class ContainmentAction(str, enum.Enum):
    block_ip        = "block_ip"
    lock_account    = "lock_account"
    isolate_machine = "isolate_machine"
    block_domain    = "block_domain"
    disable_service = "disable_service"
    other           = "other"

class ContainmentStatus(str, enum.Enum):
    proposed  = "proposed"
    approved  = "approved"
    rejected  = "rejected"
    executed  = "executed"
    verified  = "verified"

class Containment(Base):
    __tablename__ = "containments"

    id              = Column(Integer, primary_key=True, index=True)
    incident_id     = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    action_type     = Column(Enum(ContainmentAction), nullable=False)
    target          = Column(String(200), nullable=False)  # IP, account, machine...
    reason          = Column(Text, nullable=False)
    risk_level      = Column(String(20), nullable=False, default="medium")  # low/medium/high
    status          = Column(Enum(ContainmentStatus), nullable=False, default=ContainmentStatus.proposed)

    # Người đề xuất
    proposed_by     = Column(Integer, ForeignKey("users.id"), nullable=False)
    proposed_at     = Column(DateTime, server_default=func.now())

    # Người phê duyệt
    reviewed_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at     = Column(DateTime, nullable=True)
    review_note     = Column(Text, nullable=True)

    # Thực hiện
    executed_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    executed_at     = Column(DateTime, nullable=True)
    execution_note  = Column(Text, nullable=True)  # ghi chú thực hiện (mô phỏng)

    created_at      = Column(DateTime, server_default=func.now())
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())