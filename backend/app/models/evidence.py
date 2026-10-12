from sqlalchemy import Column, Integer, Enum, DateTime, ForeignKey, Boolean, Unicode, UnicodeText
from sqlalchemy.sql import func
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
    file_path       = Column(Unicode(500), nullable=True)
    content         = Column(UnicodeText, nullable=True)          # nội dung text (log, email...)
    is_locked       = Column(Boolean, default=False)       # không sửa được sau khi lock
    collected_by    = Column(Integer, ForeignKey("users.id"), nullable=False)
    collected_at    = Column(DateTime, server_default=func.now())
    created_at      = Column(DateTime, server_default=func.now())

class ChainOfCustody(Base):
    __tablename__ = "chain_of_custody"

    id              = Column(Integer, primary_key=True, index=True)
    evidence_id     = Column(Integer, ForeignKey("evidences.id"), nullable=False)
    action          = Column(Unicode(100), nullable=False)  # collected, verified, locked, accessed
    performed_by    = Column(Integer, ForeignKey("users.id"), nullable=False)
    note            = Column(UnicodeText, nullable=True)
    performed_at    = Column(DateTime, server_default=func.now())