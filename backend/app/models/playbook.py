from sqlalchemy import Column, Integer, Enum, DateTime, ForeignKey, Boolean, Unicode, UnicodeText
from app.core.timeutils import utcnow
from app.models.user import RoleEnum
from database import Base
import enum


class PlaybookType(str, enum.Enum):
    phishing              = "phishing"
    credential_compromise = "credential_compromise"
    malware               = "malware"
    web_attack            = "web_attack"
    other                 = "other"


class TaskPhase(str, enum.Enum):
    analysis      = "analysis"       # xác nhận và phân tích phạm vi
    evidence      = "evidence"       # thu thập bằng chứng
    containment   = "containment"    # ngăn chặn
    recovery      = "recovery"       # loại bỏ nguyên nhân và khôi phục
    communication = "communication"  # thông báo và phối hợp
    closure       = "closure"        # đóng vụ và postmortem


class Playbook(Base):
    __tablename__ = "playbooks"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(Unicode(150), nullable=False)
    incident_type = Column(Enum(PlaybookType), nullable=False)
    description   = Column(UnicodeText, nullable=True)
    source        = Column(Unicode(300), nullable=True)   # tài liệu tham chiếu
    is_active     = Column(Boolean, default=True)
    created_by    = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at    = Column(DateTime, default=utcnow)
    updated_at    = Column(DateTime, default=utcnow, onupdate=utcnow)


class PlaybookStep(Base):
    __tablename__ = "playbook_steps"

    id          = Column(Integer, primary_key=True, index=True)
    playbook_id = Column(Integer, ForeignKey("playbooks.id"), nullable=False)
    step_order  = Column(Integer, nullable=False)
    title       = Column(Unicode(200), nullable=False)
    description = Column(UnicodeText, nullable=True)
    phase       = Column(Enum(TaskPhase), nullable=False)
    owner_role  = Column(Enum(RoleEnum), nullable=True)   # vai trò thường đảm nhiệm
    due_hours   = Column(Integer, nullable=True)           # hạn: số giờ kể từ lúc tạo vụ
    is_required = Column(Boolean, default=True)            # bắt buộc xong (hoặc bỏ qua có lý do) mới đóng được vụ
