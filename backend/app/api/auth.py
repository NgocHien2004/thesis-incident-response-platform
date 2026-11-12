from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, TokenOut, LoginRequest
from app.core.security import (hash_password, verify_password, create_access_token,
                               create_refresh_token, decode_token)
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])
optional_bearer = HTTPBearer(auto_error=False)

@router.post("/register", response_model=UserOut)
def register(payload: UserCreate, db: Session = Depends(get_db),
             credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer)):
    # Tài khoản đầu tiên tạo tự do (khởi tạo hệ thống); sau đó phải đăng nhập mới cấp được tài khoản
    if db.query(User).count() > 0:
        data = decode_token(credentials.credentials) if credentials else None
        if not data or data.get("type") != "access":
            raise HTTPException(401, "Cần đăng nhập để tạo tài khoản mới")
        creator = db.query(User).filter(User.id == int(data["sub"])).first()
        if not creator or not creator.is_active:
            raise HTTPException(401, "Người dùng không tồn tại")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(400, "Username đã tồn tại")
    user = User(username=payload.username, password_hash=hash_password(payload.password),
                full_name=payload.full_name, role="analyst")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Sai username hoặc password")
    if not user.is_active:
        raise HTTPException(403, "Tài khoản đã bị vô hiệu hóa")
    data = {"sub": str(user.id), "role": user.role}
    return TokenOut(access_token=create_access_token(data), refresh_token=create_refresh_token(data))

@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
