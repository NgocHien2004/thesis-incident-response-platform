from sqlalchemy import (Column, Integer, Float, Boolean, DateTime, Unicode, UnicodeText,
                        ForeignKey, Index, UniqueConstraint)
from app.core.timeutils import utcnow
from database import Base

class Alert(Base):
    __tablename__ = "alerts"

    id                  = Column(Integer, primary_key=True, index=True)
    incident_id         = Column(Integer, ForeignKey("incidents.id"), nullable=True)   # rỗng khi đã gỡ khỏi sự cố
    upload_id           = Column(Integer, ForeignKey("uploads.id"), nullable=False)
    row_index           = Column(Integer, nullable=False)       # số thứ tự dòng dữ liệu trong file gốc, tính từ 1
    predicted_label     = Column(Unicode(100), nullable=False)
    confidence          = Column(Float, nullable=False)
    source_type         = Column(Unicode(20), nullable=False)   # network / email
    row_data            = Column(UnicodeText, nullable=True)    # JSON: nội dung dòng gốc để xem không cần mở file
    auto_linked         = Column(Boolean, nullable=False, default=True)
    linked_at           = Column(DateTime, nullable=True)
    verification_status = Column(Unicode(20), nullable=False, default="unverified")
    verified_by         = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at         = Column(DateTime, nullable=True)
    note                = Column(UnicodeText, nullable=True)
    created_at          = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        UniqueConstraint("upload_id", "row_index", name="uq_alerts_upload_row"),
        Index("ix_alerts_incident", "incident_id"),
        Index("ix_alerts_label", "predicted_label"),
        Index("ix_alerts_verification", "verification_status"),
    )

class AlertMoveHistory(Base):
    __tablename__ = "alert_move_history"

    id               = Column(Integer, primary_key=True, index=True)
    alert_id         = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    from_incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    to_incident_id   = Column(Integer, ForeignKey("incidents.id"), nullable=True)   # rỗng nghĩa là gỡ khỏi sự cố
    moved_by         = Column(Integer, ForeignKey("users.id"), nullable=False)
    moved_at         = Column(DateTime, nullable=False, default=utcnow)
    reason           = Column(UnicodeText, nullable=True)
