"""Account operations — login, lockout, refresh-token rotation (DB-backed).

All password/session rules live here so routes stay thin and tests can drive
these functions with a fake db. Failures raise HTTPException; the caller's
session commits state before the exception leaves the route.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import Settings
from ..models.user import RefreshToken, User
from .passwords import dummy_verify, verify_password

log = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
ROLES = ("admin", "member")


def norm_email(raw: str) -> str:
    """Lowercase + strip; raises ValueError when not a plausible address."""
    email = raw.strip().lower()
    if len(email) > 255 or not _EMAIL_RE.match(email):
        raise ValueError("Invalid email address")
    return email


def is_locked(user: User, now: datetime) -> bool:
    return user.locked_until is not None and user.locked_until > now


def register_failure(user: User, s: Settings, now: datetime) -> None:
    user.failed_logins += 1
    if user.failed_logins >= s.login_max_attempts:
        user.locked_until = now + timedelta(minutes=s.login_lockout_minutes)


def reset_failures(user: User, now: datetime) -> None:
    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_refresh_row(user_id: uuid.UUID, s: Settings, now: datetime) -> tuple[str, RefreshToken]:
    """Return (raw token, row to store). Raw is shown once, never persisted."""
    raw = secrets.token_urlsafe(48)
    row = RefreshToken(
        user_id=user_id,
        token_hash=hash_token(raw),
        expires_at=now + timedelta(days=s.refresh_expire_days),
    )
    return raw, row


async def revoke_all_sessions(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def authenticate(db: AsyncSession, email: str, password: str, s: Settings) -> User:
    """Verify credentials. Generic 401s (no user enumeration), 429 when locked."""
    now = datetime.now(UTC)
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if user is None:
        dummy_verify(password)  # timing equalizer
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if is_locked(user, now):
        retry = int((user.locked_until - now).total_seconds()) + 1  # type: ignore[operator]
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry)},
        )

    if not verify_password(password, user.password_hash):
        register_failure(user, s, now)
        await db.commit()
        log.warning("login failed email=%s attempts=%d", user.email, user.failed_logins)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    reset_failures(user, now)
    return user


async def rotate_refresh(db: AsyncSession, raw: str, s: Settings) -> tuple[User, str]:
    """Validate + consume a refresh token, issue a fresh one.

    Reuse of an already-rotated token is treated as theft: every session for
    that user is revoked before rejecting (OWASP refresh-token rotation).
    """
    now = datetime.now(UTC)
    row = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)))
    ).scalars().first()

    if row is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if row.revoked_at is not None:
        await revoke_all_sessions(db, row.user_id, now)
        await db.commit()
        log.warning("refresh-token reuse — all sessions revoked user_id=%s", row.user_id)
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if row.expires_at <= now:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    claimed = await db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == row.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    if claimed.rowcount == 0:  # lost a rotation race — treat as reuse
        await revoke_all_sessions(db, user.id, now)
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    new_raw, new_row = new_refresh_row(user.id, s, now)
    db.add(new_row)
    await db.commit()
    return user, new_raw


async def logout(db: AsyncSession, raw: str) -> None:
    """Idempotent: revoke the presented token if it exists."""
    now = datetime.now(UTC)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw), RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.commit()
