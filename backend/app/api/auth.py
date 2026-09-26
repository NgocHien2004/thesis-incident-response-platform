from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from database import get_db
from app.models.user import User, RoleEnum
from app.schemas.user import UserCreate, UserOut, TokenOut, LoginRequest
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token
)
from dotenv import load_dotenv
import os

load_dotenv()
MAX_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", 5))

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=UserOut)
def register(payload: UserCreate, db: Session = Depends(get_db)):
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
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()

    # Brute-force protection
    if user and user.locked_until:
        if datetime.now(timezone.utc) < user.locked_until.replace(tzinfo=timezone.utc):
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
            db.commit()
        raise HTTPException(401, "Sai username hoặc password")

    if not user.is_active:
        raise HTTPException(403, "Tài khoản đã bị vô hiệu hóa")

    user.login_attempts = 0
    user.locked_until = None
    db.commit()

    token_data = {"sub": str(user.id), "role": user.role.value}
    return TokenOut(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )