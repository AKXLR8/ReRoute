"""User management — admin-only account CRUD (roles, suspend, reset, delete)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.accounts import revoke_all_sessions
from ..auth.auth import AuthContext, get_current_user, require_admin
from ..auth.passwords import check_policy, hash_password
from ..database import get_db
from ..models.user import User
from ..providers.byok import _publish_invalidate
from ..schemas.auth import UserCreate, UserRead, UserResetPassword, UserUpdate

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin-users"])


def _read(u: User) -> UserRead:
    return UserRead(
        id=str(u.id),
        email=u.email,
        role=u.role,
        is_active=u.is_active,
        last_login_at=u.last_login_at,
        created_at=u.created_at,
    )


async def _get(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _guard_last_admin(db: AsyncSession, target: User, *, removing: bool) -> None:
    """Refuse changes that would leave the system with zero active admins."""
    if not removing:
        return
    others = (
        await db.execute(
            select(func.count(User.id)).where(
                User.role == "admin", User.is_active.is_(True), User.id != target.id
            )
        )
    ).scalar_one()
    if not others:
        raise HTTPException(status_code=400, detail="Cannot remove the last admin account")


@router.get("/users", response_model=list[UserRead])
async def list_users(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_admin(auth)
    rows = (await db.execute(select(User).order_by(User.created_at))).scalars().all()
    return [_read(u) for u in rows]


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserRead)
async def create_user(
    body: UserCreate,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_admin(auth)
    if err := check_policy(body.password):
        raise HTTPException(status_code=400, detail=err)
    exists = (await db.execute(select(User).where(User.email == body.email))).scalars().first()
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=body.email, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    log.info("user created email=%s role=%s by=%s", user.email, user.role, auth.email)
    return _read(user)


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_admin(auth)
    target = await _get(db, user_id)
    losing_admin = target.role == "admin" and (
        body.role == "member" or body.is_active is False
    )
    await _guard_last_admin(db, target, removing=losing_admin)

    if body.role is not None:
        target.role = body.role
    if body.is_active is not None:
        target.is_active = body.is_active
    if body.is_active is False:
        # suspend: kill every live session immediately (access tokens die via
        # is_active check on the next request; refresh dies here)
        target.token_version += 1
        await revoke_all_sessions(db, target.id, datetime.now(UTC))
    await db.commit()
    log.info(
        "user updated email=%s role=%s active=%s by=%s",
        target.email, target.role, target.is_active, auth.email,
    )
    return _read(target)


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    user_id: uuid.UUID,
    body: UserResetPassword,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    require_admin(auth)
    if err := check_policy(body.new_password):
        raise HTTPException(status_code=400, detail=err)
    target = await _get(db, user_id)
    target.password_hash = hash_password(body.new_password)
    target.token_version += 1  # kick the user out of every session
    target.failed_logins = 0
    target.locked_until = None
    await revoke_all_sessions(db, target.id, datetime.now(UTC))
    await db.commit()
    log.info("password reset email=%s by=%s", target.email, auth.email)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    http_request: Request = None,
):
    require_admin(auth)
    target = await _get(db, user_id)
    await _guard_last_admin(db, target, removing=target.role == "admin")
    # explicit revoke before delete (row cascade would cover it, but keep the
    # revocation visible in the same transaction as any future audit hook)
    await revoke_all_sessions(db, target.id, datetime.now(UTC))
    await db.delete(target)
    await db.commit()
    redis = http_request.app.state.redis
    await _publish_invalidate(redis, str(target.id))  # drop cached BYOK instances
    log.info("user deleted email=%s by=%s", target.email, auth.email)
