from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from app.models.user import User, RoleEnum
from app.core.security import decode_token

bearer = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token không hợp lệ")
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Người dùng không tồn tại")
    db.info["actor"] = {"id": user.id, "username": user.username, "role": user.role.value}
    return user

def require_roles(*roles: RoleEnum):
    def checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Không có quyền truy cập")
        return current_user
    return checker

# ── Shorthand dependencies ──────────────────────────────────────

# Analyst/SOC only — triage, incident, analysis, postmortem, communication
def require_analyst(user: User = Depends(
    require_roles(RoleEnum.analyst_soc)
)):
    return user

# IT/Helpdesk only
def require_it(user: User = Depends(
    require_roles(RoleEnum.it_helpdesk)
)):
    return user

# Stakeholder only
def require_stakeholder(user: User = Depends(
    require_roles(RoleEnum.stakeholder)
)):
    return user

# IT + Analyst — upload alert, tạo asset, thu thập bằng chứng,
# đề xuất/thực hiện containment, recovery action
def require_it_or_analyst(user: User = Depends(
    require_roles(RoleEnum.it_helpdesk, RoleEnum.analyst_soc)
)):
    return user

# Analyst + Auditor — xem nhật ký kiểm toán
def require_analyst_or_auditor(user: User = Depends(
    require_roles(RoleEnum.analyst_soc, RoleEnum.auditor)
)):
    return user