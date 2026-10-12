"""Tests for authentication — guard, account JWTs, passwords, lockout, refresh rotation."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import Update

from reroute.auth import accounts, passwords
from reroute.auth.auth import (
    create_access_token,
    create_admin_token,
    decode_token,
    get_current_user,
)
from reroute.config import get_settings
from tests.conftest import FakeDb, FakeResult, make_user

# --- legacy primitives (API key / break-glass token) ---


def test_jwt_roundtrip():
    token = create_admin_token()
    payload = decode_token(token)
    assert payload["is_admin"] is True
    assert payload["sub"] == "admin"


@pytest.mark.asyncio
async def test_admin_api_key_accepted():
    ctx = await get_current_user(None, get_settings().admin_api_key)
    assert ctx.is_admin


@pytest.mark.asyncio
async def test_wrong_api_key_rejected():
    with pytest.raises(HTTPException) as exc:
        await get_current_user(None, "wrong-key")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_bad_bearer_token_rejected():
    with pytest.raises(HTTPException) as exc:
        await get_current_user("Bearer not-a-token", None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_missing_auth_rejected():
    with pytest.raises(HTTPException) as exc:
        await get_current_user(None, None)
    assert exc.value.status_code == 401


# --- passwords ---


def test_password_hash_roundtrip():
    stored = passwords.hash_password("correct-horse-battery")
    assert stored.startswith("pbkdf2_sha256$600000$")
    assert passwords.verify_password("correct-horse-battery", stored)
    assert not passwords.verify_password("wrong-password-xx", stored)


def test_password_verify_rejects_garbage():
    assert not passwords.verify_password("anything", "not-a-hash")
    assert not passwords.verify_password("anything", "md5$1$abc$def")


def test_password_policy():
    assert passwords.check_policy("short") is not None
    assert passwords.check_policy("x" * 12) is None
    assert passwords.check_policy("x" * 129) is not None


def test_norm_email():
    assert accounts.norm_email("  Admin@Example.COM ") == "admin@example.com"
    for bad in ("nope", "a@b", "@x.com", "a b@x.com"):
        with pytest.raises(ValueError):
            accounts.norm_email(bad)


# --- lockout ---


def test_lockout_after_max_attempts():
    s = get_settings()
    now = datetime.now(UTC)
    user = make_user(failed_logins=0)
    for _ in range(s.login_max_attempts - 1):
        accounts.register_failure(user, s, now)
        assert not accounts.is_locked(user, now)
    accounts.register_failure(user, s, now)
    assert accounts.is_locked(user, now)
    assert accounts.is_locked(user, now + timedelta(seconds=5))
    assert not accounts.is_locked(user, now + timedelta(minutes=s.login_lockout_minutes + 1))
    accounts.reset_failures(user, now)
    assert user.failed_logins == 0 and user.locked_until is None


# --- account JWT guard ---


def _bearer(user) -> str:
    return f"Bearer {create_access_token(user)}"


@pytest.mark.asyncio
async def test_member_jwt_accepted():
    user = make_user(role="member")
    db = FakeDb()
    db.get_impl = lambda model, pk: user
    ctx = await get_current_user(_bearer(user), None, db)
    assert not ctx.is_admin
    assert ctx.role == "member"
    assert ctx.email == user.email
    assert ctx.user_id == str(user.id)


@pytest.mark.asyncio
async def test_admin_jwt_accepted():
    user = make_user(role="admin")
    db = FakeDb()
    db.get_impl = lambda model, pk: user
    ctx = await get_current_user(_bearer(user), None, db)
    assert ctx.is_admin


@pytest.mark.asyncio
async def test_stale_token_version_rejected():
    user = make_user(token_version=2)
    stale = make_user(token_version=1, email=user.email)
    stale.id = user.id  # same account, old tv claim
    db = FakeDb()
    db.get_impl = lambda model, pk: user
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_bearer(stale), None, db)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_rejected():
    user = make_user(is_active=False)
    db = FakeDb()
    db.get_impl = lambda model, pk: user
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_bearer(user), None, db)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_unknown_user_rejected():
    db = FakeDb()
    db.get_impl = lambda model, pk: None
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_bearer(make_user()), None, db)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_legacy_admin_token_needs_no_user_row():
    ctx = await get_current_user(f"Bearer {create_admin_token()}", None)
    assert ctx.is_admin


# --- authenticate (login) ---


@pytest.mark.asyncio
async def test_authenticate_success_resets_failures():
    s = get_settings()
    user = make_user(failed_logins=3)
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=user)
    got = await accounts.authenticate(db, user.email, "correct-horse-battery", s)
    assert got is user
    assert user.failed_logins == 0 and user.locked_until is None
    assert db.commits == 0  # route commits together with the fresh session row


@pytest.mark.asyncio
async def test_authenticate_wrong_password_counts_attempt():
    s = get_settings()
    user = make_user(failed_logins=0)
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=user)
    with pytest.raises(HTTPException) as exc:
        await accounts.authenticate(db, user.email, "wrong-password-xx", s)
    assert exc.value.status_code == 401
    assert user.failed_logins == 1
    assert db.commits == 1  # failed attempt must survive the request


@pytest.mark.asyncio
async def test_authenticate_locked_account_429():
    s = get_settings()
    user = make_user(
        failed_logins=s.login_max_attempts,
        locked_until=datetime.now(UTC) + timedelta(minutes=10),
    )
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=user)
    with pytest.raises(HTTPException) as exc:
        await accounts.authenticate(db, user.email, "correct-horse-battery", s)
    assert exc.value.status_code == 429
    assert int(exc.value.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_authenticate_unknown_email_401_generic():
    s = get_settings()
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=None)
    with pytest.raises(HTTPException) as exc:
        await accounts.authenticate(db, "ghost@example.com", "whatever-password", s)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid email or password"


@pytest.mark.asyncio
async def test_authenticate_disabled_account_403():
    s = get_settings()
    user = make_user(is_active=False)
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=user)
    with pytest.raises(HTTPException) as exc:
        await accounts.authenticate(db, user.email, "correct-horse-battery", s)
    assert exc.value.status_code == 403


# --- refresh rotation ---


def _rotate_setup(user, row):
    db = FakeDb()

    def execute(stmt):
        if isinstance(stmt, Update):
            return FakeResult(rowcount=1)
        return FakeResult(first=row)

    db.execute_impl = execute
    db.get_impl = lambda model, pk: user
    return db


@pytest.mark.asyncio
async def test_rotate_refresh_issues_fresh_token():
    s = get_settings()
    user = make_user()
    raw, row = accounts.new_refresh_row(user.id, s, datetime.now(UTC))
    db = _rotate_setup(user, row)
    returned_user, new_raw = await accounts.rotate_refresh(db, raw, s)
    assert returned_user is user
    assert new_raw != raw
    assert any(getattr(a, "token_hash", None) == accounts.hash_token(new_raw) for a in db.added)
    assert db.commits == 1  # claim + new row committed atomically


@pytest.mark.asyncio
async def test_rotate_refresh_reuse_revokes_everything():
    s = get_settings()
    user = make_user()
    raw, row = accounts.new_refresh_row(user.id, s, datetime.now(UTC))
    row.revoked_at = datetime.now(UTC)  # already rotated → reuse
    db = _rotate_setup(user, row)
    with pytest.raises(HTTPException) as exc:
        await accounts.rotate_refresh(db, raw, s)
    assert exc.value.status_code == 401
    assert db.commits == 1  # revocation persisted before rejecting


@pytest.mark.asyncio
async def test_rotate_refresh_unknown_token_401():
    s = get_settings()
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=None)
    with pytest.raises(HTTPException) as exc:
        await accounts.rotate_refresh(db, "not-a-real-token", s)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_rotate_refresh_expired_401():
    s = get_settings()
    user = make_user()
    raw, row = accounts.new_refresh_row(user.id, s, datetime.now(UTC))
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db = _rotate_setup(user, row)
    with pytest.raises(HTTPException) as exc:
        await accounts.rotate_refresh(db, raw, s)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_idempotently():
    db = FakeDb()
    seen = []

    def execute(stmt):
        seen.append(stmt)
        return FakeResult()

    db.execute_impl = execute
    await accounts.logout(db, "some-token")
    await accounts.logout(db, "some-token")
    assert len(seen) == 2
    assert db.commits == 2
