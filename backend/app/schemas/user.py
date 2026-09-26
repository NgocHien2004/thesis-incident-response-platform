from pydantic import BaseModel, EmailStr
from app.models.user import RoleEnum

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: RoleEnum

class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: RoleEnum
    is_active: bool

    model_config = {"from_attributes": True}

class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class LoginRequest(BaseModel):
    username: str
    password: str