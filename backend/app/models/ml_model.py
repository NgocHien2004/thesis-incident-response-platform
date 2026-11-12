from sqlalchemy import Column, Integer, Boolean, DateTime, Unicode, UnicodeText, UniqueConstraint, Index
from app.core.timeutils import utcnow
from database import Base

class MLModel(Base):
    __tablename__ = "models"

    id                = Column(Integer, primary_key=True, index=True)
    name              = Column(Unicode(100), nullable=False)
    version           = Column(Unicode(50), nullable=False)
    task_type         = Column(Unicode(20), nullable=False)    # network / email
    file_path         = Column(Unicode(500), nullable=True)
    preprocessor_path = Column(Unicode(500), nullable=True)
    metrics_json      = Column(UnicodeText, nullable=True)
    feature_names     = Column(UnicodeText, nullable=True)     # JSON: danh sách cột đầu vào bắt buộc (luồng mạng)
    trained_at        = Column(DateTime, nullable=True)
    is_active         = Column(Boolean, nullable=False, default=False)
    created_at        = Column(DateTime, nullable=False, default=utcnow)

    __table_args__ = (UniqueConstraint("task_type", "version", name="uq_models_task_version"),)

class Label(Base):
    __tablename__ = "labels"

    id           = Column(Integer, primary_key=True, index=True)
    data_type    = Column(Unicode(20), nullable=False)
    code         = Column(Unicode(100), nullable=False)
    name_vi      = Column(Unicode(150), nullable=False)
    is_dangerous = Column(Boolean, nullable=False, default=True)
    is_active    = Column(Boolean, nullable=False, default=True)

    __table_args__ = (UniqueConstraint("data_type", "code", name="uq_labels_type_code"),)
