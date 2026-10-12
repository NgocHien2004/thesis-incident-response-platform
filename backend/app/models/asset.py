from sqlalchemy import Column, Integer, Enum, DateTime, ForeignKey, Unicode, UnicodeText
from sqlalchemy.sql import func
from database import Base
import enum

class AssetType(str, enum.Enum):
    server      = "server"
    application = "application"
    account     = "account"
    network     = "network"
    other       = "other"

class CriticalityLevel(str, enum.Enum):
    critical = "critical"
    high     = "high"
    medium   = "medium"
    low      = "low"

class Asset(Base):
    __tablename__ = "assets"

    id               = Column(Integer, primary_key=True, index=True)
    name             = Column(Unicode(100), nullable=False)
    asset_type       = Column(Enum(AssetType), nullable=False)
    criticality      = Column(Enum(CriticalityLevel), nullable=False)
    owner            = Column(Unicode(100), nullable=True)
    description      = Column(UnicodeText, nullable=True)
    ip_address       = Column(Unicode(50), nullable=True)
    hostname         = Column(Unicode(100), nullable=True)
    data_processed   = Column(UnicodeText, nullable=True)
    dependencies     = Column(UnicodeText, nullable=True)
    created_by       = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at       = Column(DateTime, server_default=func.now())
    updated_at       = Column(DateTime, server_default=func.now(), onupdate=func.now())