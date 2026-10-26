"""Gateway API keys - minting, revocation, and auth acceptance.

Security invariants under test:
- the raw key is returned once and only its sha256 is stored
- revocation and user deactivation kill a key immediately
- a gateway key cannot manage keys (no escalation from a leaked credential)
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from reroute.app import create_app
from reroute.auth.accounts import hash_token
from reroute.auth.auth import API_KEY_PREFIX, AuthContext, get_current_user
from reroute.database import get_db
from reroute.models.api_key import ApiKey
from reroute.models.user import User
from tests.conftest import FakeDb, FakeResult, make_user


def _client(db: FakeDb, user: User) -> AsyncClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    # bypass JWT parsing: the route tests are about key management, not tokens
    app.dependency_overrides[get_current_user] = lambda: AuthContext(
        is_admin=user.role == "admin", user_id=str(user.id), email=user.email, role=user.role
    )
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _key_row(user: User, *, revoked: bool = False, last_used=None) -> ApiKey:
    return ApiKey(
        id=uuid.uuid4(),
        user_id=user.id,
        name="laptop",
        key_hash=hash_token("rr_live_secret"),
        key_prefix="rr_live_secre",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        last_used_at=last_used,
        revoked_at=datetime.now(UTC) if revoked else None,
    )


@pytest.mark.asyncio
async def test_create_returns_raw_key_once_and_stores_only_hash():
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(rows=[])
    user = make_user()
    async with _client(db, user) as client:
        resp = await client.post("/auth/api-keys", json={"name": " laptop "})

    assert resp.status_code == 201
    body = resp.json()
    raw = body["key"]
    assert raw.startswith(API_KEY_PREFIX)
    assert body["key_prefix"] == raw[: len(API_KEY_PREFIX) + 4]
    assert body["name"] == "laptop"

    stored = db.added[-1]
    assert isinstance(stored, ApiKey)
    assert stored.key_hash == hash_token(raw)
    assert raw not in stored.key_hash
    assert stored.user_id == user.id


@pytest.mark.asyncio
async def test_list_never_returns_raw_keys():
    db = FakeDb()
    user = make_user()
    row = _key_row(user)
    db.execute_impl = lambda stmt: FakeResult(rows=[row])
    async with _client(db, user) as client:
        resp = await client.get("/auth/api-keys")

    assert resp.status_code == 200
    assert resp.json()[0]["key_prefix"] == "rr_live_secre"
    assert "key" not in resp.json()[0]


@pytest.mark.asyncio
async def test_revoke_sets_revoked_at_once():
    db = FakeDb()
    user = make_user()
    row = _key_row(user)
    db.execute_impl = lambda stmt: FakeResult(first=row)
    async with _client(db, user) as client:
        resp = await client.delete(f"/auth/api-keys/{row.id}")

    assert resp.status_code == 204
    assert row.revoked_at is not None
    assert db.commits == 1


@pytest.mark.asyncio
async def test_revoke_unknown_or_foreign_key_is_404():
    db = FakeDb()
    user = make_user()
    db.execute_impl = lambda stmt: FakeResult(first=None)
    async with _client(db, user) as client:
        resp = await client.delete("/auth/api-keys/00000000-0000-0000-0000-000000000000")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_gateway_key_authenticates_as_its_user():
    db = FakeDb()
    user = make_user(role="member")
    row = _key_row(user)
    db.execute_impl = lambda stmt: FakeResult(first=row)
    db.get_impl = lambda model, pk: user

    auth = await get_current_user(authorization=f"Bearer {row.key_prefix}xyz", db=db)
    assert auth.user_id == str(user.id)
    assert auth.api_key_id == str(row.id)
    assert auth.role == "member"
    assert row.last_used_at is not None


@pytest.mark.asyncio
async def test_revoked_key_is_rejected():
    db = FakeDb()
    user = make_user()
    row = _key_row(user, revoked=True)
    db.execute_impl = lambda stmt: FakeResult(first=row)

    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization="Bearer rr_live_secret", db=db)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_key_is_rejected():
    db = FakeDb()
    user = make_user(is_active=False)
    row = _key_row(user)
    db.execute_impl = lambda stmt: FakeResult(first=row)
    db.get_impl = lambda model, pk: user

    with pytest.raises(HTTPException) as exc:
        await get_current_user(authorization="Bearer rr_live_secret", db=db)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_last_used_write_is_throttled():
    db = FakeDb()
    user = make_user()
    row = _key_row(user, last_used=datetime.now(UTC) - timedelta(seconds=5))
    db.execute_impl = lambda stmt: FakeResult(first=row)
    db.get_impl = lambda model, pk: user

    await get_current_user(authorization="Bearer rr_live_secret", db=db)
    assert db.commits == 0


@pytest.mark.asyncio
async def test_gateway_key_cannot_manage_keys():
    db = FakeDb()
    user = make_user()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db

    app.dependency_overrides[get_current_user] = lambda: AuthContext(
        user_id=str(user.id),
        email=user.email,
        role=user.role,
        api_key_id="some-key-id",
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/auth/api-keys")

    assert resp.status_code == 403
    assert db.execute_impl is None
