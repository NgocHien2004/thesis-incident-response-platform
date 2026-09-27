from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.sql import func
from database import Base
import enum

class RecoveryActionType(str, enum.Enum):
    remove_malware      = "remove_malware"
    patch_vulnerability = "patch_vulnerability"
    restore_backup      = "restore_backup"
    reset_credentials   = "reset_credentials"
    rebuild_system      = "rebuild_system"
    re_enable_service   = "re_enable_service"
    other               = "other"

class RecoveryStatus(str, enum.Enum):
    pending   = "pending"
    in_progress = "in_progress"
    done      = "done"
    failed    = "failed"

class RecoveryAction(Base):
    __tablename__ = "recovery_actions"

    id              = Column(Integer, primary_key=True, index=True)
    incident_id     = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    action_type     = Column(Enum(RecoveryActionType), nullable=False)
    description     = Column(Text, nullable=False)
    status          = Column(Enum(RecoveryStatus), nullable=False, default=RecoveryStatus.pending)
    note            = Column(Text, nullable=True)

    # Thực hiện
    assigned_to     = Column(Integer, ForeignKey("users.id"), nullable=True)
    executed_by     = Column(Integer, ForeignKey("users.id"), nullable=True)
    executed_at     = Column(DateTime, nullable=True)

    # Stakeholder xác nhận
    confirmed_by    = Column(Integer, ForeignKey("users.id"), nullable=True)
    confirmed_at    = Column(DateTime, nullable=True)
    confirm_note    = Column(Text, nullable=True)
    is_confirmed    = Column(Boolean, default=False)

    created_by      = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at      = Column(DateTime, server_default=func.now())
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())