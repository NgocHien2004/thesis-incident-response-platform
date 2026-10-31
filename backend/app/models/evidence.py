from sqlalchemy import Column, Integer, BigInteger, Enum, DateTime, ForeignKey, Boolean, Unicode, UnicodeText
from app.core.timeutils import utcnow
from database import Base
import enum

class EvidenceType(str, enum.Enum):
    log         = "log"
    email       = "email"
    file        = "file"
    screenshot  = "screenshot"
    hash        = "hash"
    network     = "network"
    other       = "other"

class Evidence(Base):
    __tablename__ = "evidences"

    id              = Column(Integer, primary_key=True, index=True)
    incident_id     = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    title           = Column(Unicode(200), nullable=False)
    evidence_type   = Column(Enum(EvidenceType), nullable=False)
    description     = Column(UnicodeText, nullable=True)
    source          = Column(Unicode(200), nullable=True)   # nguồn thu thập (server, email...)
    file_hash       = Column(Unicode(128), nullable=True)   # SHA-256
    file_path       = Column(Unicode(500), nullable=True)   # đường dẫn gốc trên máy nguồn, chỉ để ghi nhận
    original_filename = Column(Unicode(255), nullable=True)  # tên tệp khi thu thập (chỉ để hiển thị)
    content_type    = Column(Unicode(100), nullable=True)    # do bên tải lên khai báo, không đáng tin
    size_bytes      = Column(BigInteger, nullable=True)
    storage_key     = Column(Unicode(300), nullable=True)    # khóa tệp trong kho, do server sinh
    content         = Column(UnicodeText, nullable=True)          # nội dung text (log, email...)
    is_locked       = Column(Boolean, default=False)       # không sửa được sau khi lock
    collected_by    = Column(Integer, ForeignKey("users.id"), nullable=False)
    collected_at    = Column(DateTime, default=utcnow)
    created_at      = Column(DateTime, default=utcnow)

    @property
    def has_file(self) -> bool:
        return bool(self.storage_key)

class ChainOfCustody(Base):
    __tablename__ = "chain_of_custody"

    id              = Column(Integer, primary_key=True, index=True)
    evidence_id     = Column(Integer, ForeignKey("evidences.id"), nullable=False)
    action          = Column(Unicode(100), nullable=False)  # collected, verified, locked, accessed
    performed_by    = Column(Integer, ForeignKey("users.id"), nullable=False)
    note            = Column(UnicodeText, nullable=True)
    performed_at    = Column(DateTime, default=utcnow)