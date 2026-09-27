from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.common import StrictModel


class RegisterRequest(StrictModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(StrictModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class UserResponse(StrictModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: str
    created_at: datetime


class TokenResponse(StrictModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
