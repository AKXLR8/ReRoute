from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from ..auth.accounts import norm_email


class _EmailModel(BaseModel):
    @field_validator("email", check_fields=False)
    @classmethod
    def _normalize(cls, v: str) -> str:
        return norm_email(v)  # raises ValueError → 422 from pydantic


class LoginRequest(_EmailModel):
    email: str
    password: str


class SetupRequest(_EmailModel):
    email: str
    password: str


class RegisterRequest(_EmailModel):
    email: str
    password: str


class GithubExchangeRequest(BaseModel):
    code: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserCreate(_EmailModel):
    email: str
    password: str
    role: Literal["admin", "member"] = "member"


class UserUpdate(BaseModel):
    role: Literal["admin", "member"] | None = None
    is_active: bool | None = None


class UserResetPassword(BaseModel):
    new_password: str


class UserRead(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class SessionUser(BaseModel):
    id: str | None = None
    email: str | None = None
    role: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: SessionUser
