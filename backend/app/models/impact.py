from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from database import Base

class ImpactAnalysis(Base):
    __tablename__ = "impact_analyses"

    id              = Column(Integer, primary_key=True, index=True)
    incident_id     = Column(Integer, ForeignKey("incidents.id"), nullable=False)

    # Liên kết IOC
    ioc_list        = Column(Text, nullable=True)   # JSON: ["1.2.3.4", "evil.com"]

    # Tài sản và tài khoản bị ảnh hưởng
    affected_assets    = Column(Text, nullable=True)  # JSON: [1, 2, 3] — asset ids
    affected_accounts  = Column(Text, nullable=True)  # JSON: ["admin", "user01"]

    # MITRE ATT&CK
    attck_techniques   = Column(Text, nullable=True)  # JSON: ["T1566", "T1078"]
    attck_version      = Column(String(20), nullable=True)  # "14.1"

    # Các sự kiện liên quan
    related_events     = Column(Text, nullable=True)  # mô tả tự do

    # Tóm tắt phân tích
    summary            = Column(Text, nullable=True)
    ai_suggested       = Column(Text, nullable=True)  # đề xuất từ AI (đánh dấu rõ)

    analyzed_by     = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at      = Column(DateTime, server_default=func.now())
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())