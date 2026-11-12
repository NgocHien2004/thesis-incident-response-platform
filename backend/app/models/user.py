from sqlalchemy import Column, Integer, Boolean, DateTime, Unicode
from app.core.timeutils import utcnow
from database import Base

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(Unicode(50), unique=True, nullable=False)
    password_hash   = Column(Unicode(255), nullable=False)
    full_name       = Column(Unicode(100), nullable=False)
    role            = Column(Unicode(30), nullable=False, default="analyst")
    is_active       = Column(Boolean, nullable=False, default=True)
    created_at      = Column(DateTime, nullable=False, default=utcnow)
