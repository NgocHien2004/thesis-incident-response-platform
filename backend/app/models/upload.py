from sqlalchemy import Column, Integer, BigInteger, Float, DateTime, Unicode, UnicodeText, String, ForeignKey, Index
from app.core.timeutils import utcnow
from database import Base

class Upload(Base):
    __tablename__ = "uploads"

    id                = Column(Integer, primary_key=True, index=True)
    incident_id       = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    original_filename = Column(Unicode(255), nullable=False)
    stored_path       = Column(Unicode(500), nullable=False)
    file_hash         = Column(String(64), nullable=False)
    data_type         = Column(Unicode(20), nullable=False)      # network / email
    file_size_bytes   = Column(BigInteger, nullable=False)
    row_count         = Column(Integer, nullable=True)
    processed_rows    = Column(Integer, nullable=False, default=0)
    status            = Column(Unicode(20), nullable=False, default="pending")
    error_message     = Column(UnicodeText, nullable=True)
    model_id          = Column(Integer, ForeignKey("models.id"), nullable=True)
    # Cấu hình tại thời điểm xử lý, để giải thích số cảnh báo về sau
    threshold_used    = Column(Float, nullable=True)
    dangerous_labels_used = Column(UnicodeText, nullable=True)   # JSON
    # Kết quả phân loại của cả file
    alert_count       = Column(Integer, nullable=False, default=0)
    avg_confidence    = Column(Float, nullable=True)
    label_distribution = Column(UnicodeText, nullable=True)      # JSON {nhãn: số mẫu}
    uploaded_by       = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at       = Column(DateTime, nullable=False, default=utcnow)
    processed_at      = Column(DateTime, nullable=True)

    __table_args__ = (Index("ix_uploads_incident_hash", "incident_id", "file_hash"),)
