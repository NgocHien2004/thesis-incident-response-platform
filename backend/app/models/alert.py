from sqlalchemy import Column, Integer, String, Enum, DateTime, Text, Float, ForeignKey
from sqlalchemy.sql import func
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
    title           = Column(String(200), nullable=False)
    description     = Column(Text, nullable=True)
    source          = Column(Enum(AlertSource), nullable=False)
    severity        = Column(Enum(AlertSeverity), nullable=False, default=AlertSeverity.medium)
    status          = Column(Enum(AlertStatus), nullable=False, default=AlertStatus.new)
    source_ref      = Column(String(200), nullable=True)   # ID gốc từ hệ thống nguồn
    ioc             = Column(Text, nullable=True)           # IP, domain, hash liên quan
    affected_asset  = Column(Integer, ForeignKey("assets.id"), nullable=True)
    raw_data        = Column(Text, nullable=True)           # Dữ liệu gốc giữ nguyên
    created_by      = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at      = Column(DateTime, server_default=func.now())
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())
    group_id = Column(Integer, ForeignKey("alert_groups.id"), nullable=True)