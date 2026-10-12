"""Authentication — admin API key (break-glass) or account JWT (DB-validated)."""

from __future__ import annotations

import hmac
import time
import uuid
from dataclasses import dataclass
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_db
from ..models.user import User


@dataclass
class AuthContext:
    is_admin: bool = False
    user_id: str | None = None
    email: str | None = None
    role: str | None = None


def create_admin_token() -> str:
    """Legacy break-glass JWT (sub="admin") — signed with JWT_SECRET, no user row."""
    s = get_settings()
    payload = {
        "sub": "admin",
        "is_admin": True,
        "exp": int(time.time()) + s.jwt_expire_minutes * 60,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def create_access_token(user: User) -> str:
    """Short-lived account JWT. `tv` = token_version: bumping it on the user
    row instantly invalidates every outstanding access token."""
    s = get_settings()
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "is_admin": user.role == "admin",
        "tv": user.token_version,
        "exp": int(time.time()) + s.access_expire_minutes * 60,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])


def require_admin(auth: AuthContext) -> None:
    if not auth.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")


async def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: Annotated[AsyncSession | None, Depends(get_db)] = None,
) -> AuthContext:
    """Bearer JWT (validated against the users table) or admin API key.

    Account tokens are checked live: user must exist, be active, and the
    token_version claim must match — so disabling a user or resetting a
    password kills their sessions immediately, not at expiry.
    """
    s = get_settings()

    # Bearer token (account JWT, or the legacy break-glass admin token)
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            payload = decode_token(token)
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token") from None
        if payload.get("sub") == "admin" and payload.get("is_admin"):
            return AuthContext(is_admin=True, role="admin")
        if not payload.get("sub") or db is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        try:
            user_id = uuid.UUID(str(payload["sub"]))
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid token") from None
        user = await db.get(User, user_id)
        if user is None or not user.is_active or user.token_version != payload.get("tv"):
            raise HTTPException(status_code=401, detail="Session expired")
        return AuthContext(
            is_admin=user.role == "admin",
            user_id=str(user.id),
            email=user.email,
            role=user.role,
        )

    # Admin API key — break-glass for API clients/setup
    if x_api_key:
        if s.admin_api_key_hash:
            # Verify against bcrypt hash (timing-safe)
            if bcrypt.checkpw(x_api_key.encode(), s.admin_api_key_hash.encode()):
                return AuthContext(is_admin=True, role="admin")
        else:
            # Fallback to plaintext compare (legacy)
            if hmac.compare_digest(x_api_key, s.admin_api_key):
                return AuthContext(is_admin=True, role="admin")
        raise HTTPException(status_code=401, detail="Invalid API key")

    raise HTTPException(
        status_code=401, detail="Missing authentication. Provide X-API-Key or Authorization header."
    )
