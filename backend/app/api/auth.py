from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from database import get_db
from app.models.user import User, RoleEnum
from app.schemas.user import UserCreate, UserOut, TokenOut, LoginRequest
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token
)
from app.core.security import decode_token
from app.core.audit import log_event
from dotenv import load_dotenv
import os

load_dotenv()
MAX_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", 5))

router = APIRouter(prefix="/auth", tags=["Auth"])
optional_bearer = HTTPBearer(auto_error=False)

@router.post("/register", response_model=UserOut)
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer),
):
    # Chỉ tài khoản đầu tiên được tạo tự do (khởi tạo hệ thống);
    # sau đó chỉ Analyst/SOC mới được cấp tài khoản và phân vai trò.
    creator = None
    if db.query(User).count() > 0:
        data = decode_token(credentials.credentials) if credentials else None
        if not data or data.get("type") != "access":
            raise HTTPException(401, "Cần đăng nhập bằng tài khoản Analyst để tạo tài khoản mới")
        creator = db.query(User).filter(User.id == int(data["sub"])).first()
        if not creator or not creator.is_active or creator.role != RoleEnum.analyst_soc:
            raise HTTPException(403, "Chỉ Analyst/SOC mới được tạo tài khoản")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(400, "Username đã tồn tại")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(400, "Email đã tồn tại")
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    log_event(db, "user.created", user=creator, username=None if creator else "bootstrap",
              entity_type="user", entity_id=user.id,
              detail={"username": user.username, "role": user.role.value})
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()

    # Brute-force protection
    if user and user.locked_until:
        if datetime.now(timezone.utc) < user.locked_until.replace(tzinfo=timezone.utc):
            log_event(db, "auth.login_blocked", user=user)
            db.commit()
            raise HTTPException(423, "Tài khoản tạm khóa do đăng nhập sai quá nhiều lần")
        else:
            user.login_attempts = 0
            user.locked_until = None

    if not user or not verify_password(payload.password, user.hashed_password):
        if user:
            user.login_attempts += 1
            if user.login_attempts >= MAX_ATTEMPTS:
                from datetime import timedelta
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        log_event(db, "auth.login_failed", user=user, username=payload.username,
                  detail={"attempts": user.login_attempts} if user else None)
        db.commit()
        raise HTTPException(401, "Sai username hoặc password")

    if not user.is_active:
        raise HTTPException(403, "Tài khoản đã bị vô hiệu hóa")

    user.login_attempts = 0
    user.locked_until = None
    log_event(db, "auth.login", user=user)
    db.commit()

    token_data = {"sub": str(user.id), "role": user.role.value}
    return TokenOut(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )