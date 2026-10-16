from sqlalchemy import Column, Integer, Enum, DateTime, ForeignKey, Unicode, UnicodeText
from app.core.timeutils import utcnow
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
    target          = Column(Unicode(200), nullable=False)  # IP, account, machine...
    reason          = Column(UnicodeText, nullable=False)
    risk_level      = Column(Unicode(20), nullable=False, default="medium")  # low/medium/high
    status          = Column(Enum(ContainmentStatus), nullable=False, default=ContainmentStatus.proposed)

    # Người đề xuất
    proposed_by     = Column(Integer, ForeignKey("users.id"), nullable=False)
    proposed_at     = Column(DateTime, default=utcnow)

    # Người phê duyệt
    reviewed_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at     = Column(DateTime, nullable=True)
    review_note     = Column(UnicodeText, nullable=True)

    # Thực hiện
    executed_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    executed_at     = Column(DateTime, nullable=True)
    execution_note  = Column(UnicodeText, nullable=True)  # ghi chú thực hiện (mô phỏng)

    # Xác minh sau khi thực hiện (người xác minh khác người thực hiện)
    verified_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at     = Column(DateTime, nullable=True)
    verify_note     = Column(UnicodeText, nullable=True)

    created_at      = Column(DateTime, default=utcnow)
    updated_at      = Column(DateTime, default=utcnow, onupdate=utcnow)