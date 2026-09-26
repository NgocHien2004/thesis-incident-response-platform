from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.sql import func
from database import Base
import enum

class RoleEnum(str, enum.Enum):
    it_helpdesk  = "it_helpdesk"
    analyst_soc  = "analyst_soc"
    stakeholder  = "stakeholder"

class User(Base):
    __tablename__ = "users"

    id                  = Column(Integer, primary_key=True, index=True)
    username            = Column(String(50), unique=True, nullable=False)
    email               = Column(String(100), unique=True, nullable=False)
    hashed_password     = Column(String(255), nullable=False)
    role                = Column(Enum(RoleEnum), nullable=False)
    is_active           = Column(Boolean, default=True)
    login_attempts      = Column(Integer, default=0)
    locked_until        = Column(DateTime, nullable=True)
    created_at          = Column(DateTime, server_default=func.now())
    updated_at          = Column(DateTime, server_default=func.now(), onupdate=func.now())