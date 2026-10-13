from sqlalchemy import Column, Integer, Enum, DateTime, Float, ForeignKey, Unicode, UnicodeText
from app.core.timeutils import utcnow
from database import Base
import enum

class AlertSource(str, enum.Enum):
    ids_ips   = "ids_ips"
    email     = "email"
    endpoint  = "endpoint"
    manual    = "manual"
    webhook   = "webhook"
    csv_upload = "csv_upload"

class AlertStatus(str, enum.Enum):
    new         = "new"
    reviewing   = "reviewing"
    triaged     = "triaged"
    escalated   = "escalated"
    false_positive = "false_positive"
    closed      = "closed"

class AlertSeverity(str, enum.Enum):
    critical = "critical"
    high     = "high"
    medium   = "medium"
    low      = "low"
    info     = "info"

class Alert(Base):
    __tablename__ = "alerts"

    id              = Column(Integer, primary_key=True, index=True)
    title           = Column(Unicode(200), nullable=False)
    description     = Column(UnicodeText, nullable=True)
    source          = Column(Enum(AlertSource), nullable=False)
    severity        = Column(Enum(AlertSeverity), nullable=False, default=AlertSeverity.medium)
    status          = Column(Enum(AlertStatus), nullable=False, default=AlertStatus.new)
    source_ref      = Column(Unicode(200), nullable=True)   # ID gốc từ hệ thống nguồn
    ioc             = Column(UnicodeText, nullable=True)           # IP, domain, hash liên quan
    affected_asset  = Column(Integer, ForeignKey("assets.id"), nullable=True)
    raw_data        = Column(UnicodeText, nullable=True)           # Dữ liệu gốc giữ nguyên
    created_by      = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at      = Column(DateTime, default=utcnow)
    updated_at      = Column(DateTime, default=utcnow, onupdate=utcnow)
    group_id = Column(Integer, ForeignKey("alert_groups.id"), nullable=True)
    
    # Triage fields
    triage_type         = Column(Unicode(100), nullable=True)   # loại: malware, phishing, intrusion...
    triage_severity     = Column(Enum(AlertSeverity), nullable=True)
    triage_confidence   = Column(Integer, nullable=True)        # độ tin cậy 1-100
    triage_assignee     = Column(Integer, ForeignKey("users.id"), nullable=True)
    triage_sla_hours    = Column(Integer, nullable=True)        # SLA tính bằng giờ
    triage_sla_deadline = Column(DateTime, nullable=True)
    triage_note         = Column(UnicodeText, nullable=True)
    triaged_by          = Column(Integer, ForeignKey("users.id"), nullable=True)
    triaged_at          = Column(DateTime, nullable=True)

    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True)