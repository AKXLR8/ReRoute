"""Endpoint tests for /auth/* and /admin/users — real guard, scripted DB."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from reroute.api.auth import _ip_hits
from reroute.app import create_app
from reroute.auth.auth import create_access_token
from reroute.config import get_settings
from reroute.database import get_db
from reroute.models.user import RefreshToken, User
from tests.conftest import FakeDb, FakeResult, make_user


def _client(db: FakeDb) -> AsyncClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def clean_ip_window():
    _ip_hits.clear()
    yield
    _ip_hits.clear()


_KEY = get_settings().admin_api_key


# --- setup ---


@pytest.mark.asyncio
async def test_setup_requires_valid_key():
    db = FakeDb()
    async with _client(db) as client:
        resp = await client.post(
            "/auth/setup", json={"email": "a@example.com", "password": "long-enough-password"},
            headers={"X-API-Key": "wrong-key"},
        )
    assert resp.status_code == 401
    assert db.execute_impl is None  # rejected before touching the DB


@pytest.mark.asyncio
async def test_setup_blocked_once_users_exist():
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(scalar=1)
    async with _client(db) as client:
        resp = await client.post(
            "/auth/setup", json={"email": "a@example.com", "password": "long-enough-password"},
            headers={"X-API-Key": _KEY},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_setup_status_flags_first_run():
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(scalar=0)
    async with _client(db) as client:
        assert (await client.get("/auth/setup")).json() == {"needs_setup": True}
    db.execute_impl = lambda stmt: FakeResult(scalar=1)
    async with _client(db) as client:
        assert (await client.get("/auth/setup")).json() == {"needs_setup": False}


@pytest.mark.asyncio
async def test_setup_creates_first_admin_and_session():
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(scalar=0)
    async with _client(db) as client:
        resp = await client.post(
            "/auth/setup", json={"email": "Boss@Example.com", "password": "long-enough-password"},
            headers={"X-API-Key": _KEY},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["role"] == "admin"
    assert body["user"]["email"] == "boss@example.com"  # normalized
    assert body["access_token"] and body["refresh_token"]
    kinds = [type(o).__name__ for o in db.added]
    assert kinds == ["User", "RefreshToken"]


@pytest.mark.asyncio
async def test_setup_rejects_short_password():
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(scalar=0)
    async with _client(db) as client:
        resp = await client.post(
            "/auth/setup", json={"email": "a@example.com", "password": "short"},
            headers={"X-API-Key": _KEY},
        )
    assert resp.status_code == 400


# --- login ---


@pytest.mark.asyncio
async def test_login_wrong_password_counts_attempt():
    user = make_user()
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=user)
    async with _client(db) as client:
        resp = await client.post(
            "/auth/login", json={"email": user.email, "password": "wrong-password-xx"}
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"
    assert user.failed_logins == 1
    assert db.commits == 1


@pytest.mark.asyncio
async def test_login_locked_account_429():
    s = get_settings()
    user = make_user(
        failed_logins=s.login_max_attempts,
        locked_until=datetime.now(UTC) + timedelta(minutes=10),
    )
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=user)
    async with _client(db) as client:
        resp = await client.post(
            "/auth/login", json={"email": user.email, "password": "correct-horse-battery"}
        )
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_login_success_then_me_then_refresh():
    user = make_user(role="admin")
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=user)
    db.get_impl = lambda model, pk: user

    async with _client(db) as client:
        login = await client.post(
            "/auth/login", json={"email": user.email, "password": "correct-horse-battery"}
        )
        assert login.status_code == 200
        tokens = login.json()
        assert tokens["user"]["id"] == str(user.id)
        assert tokens["token_type"] == "bearer"

        auth = {"Authorization": f"Bearer {tokens['access_token']}"}
        me = await client.get("/auth/me", headers=auth)
        assert me.status_code == 200
        assert me.json() == {"id": str(user.id), "email": user.email, "role": "admin"}

        # rotation: select row (unrevoked) + claim update + get user
        raw_row = RefreshToken(
            user_id=user.id, token_hash="", expires_at=datetime.now(UTC) + timedelta(days=14)
        )
        import hashlib

        raw_row.token_hash = hashlib.sha256(tokens["refresh_token"].encode()).hexdigest()

        def execute(stmt):
            from sqlalchemy import Update

            if isinstance(stmt, Update):
                return FakeResult(rowcount=1)
            return FakeResult(first=raw_row)

        db.execute_impl = execute
        refreshed = await client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert refreshed.status_code == 200
        assert refreshed.json()["refresh_token"] != tokens["refresh_token"]


@pytest.mark.asyncio
async def test_me_unauthenticated_401():
    db = FakeDb()
    async with _client(db) as client:
        resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_bad_token_401():
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=None)
    async with _client(db) as client:
        resp = await client.post("/auth/refresh", json={"refresh_token": "nope"})
    assert resp.status_code == 401


# --- user management ---


def _bearer(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest.mark.asyncio
async def test_users_member_forbidden():
    member = make_user(role="member")
    db = FakeDb()
    db.get_impl = lambda model, pk: member
    async with _client(db) as client:
        resp = await client.get("/admin/users", headers=_bearer(member))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_users_list_admin_ok():
    admin = make_user(role="admin")
    other = make_user(email="b@example.com", role="member")
    db = FakeDb()
    db.get_impl = lambda model, pk: admin
    db.execute_impl = lambda stmt: FakeResult(rows=[admin, other])
    async with _client(db) as client:
        resp = await client.get("/admin/users", headers=_bearer(admin))
    assert resp.status_code == 200
    assert [u["email"] for u in resp.json()] == [admin.email, other.email]


@pytest.mark.asyncio
async def test_create_user_duplicate_email_409():
    admin = make_user(role="admin")
    db = FakeDb()
    db.get_impl = lambda model, pk: admin
    db.execute_impl = lambda stmt: FakeResult(first=admin)  # email already taken
    async with _client(db) as client:
        resp = await client.post(
            "/admin/users",
            json={"email": admin.email, "password": "long-enough-password", "role": "member"},
            headers=_bearer(admin),
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_user_ok():
    admin = make_user(role="admin")
    db = FakeDb()
    db.get_impl = lambda model, pk: admin
    db.execute_impl = lambda stmt: FakeResult(first=None)  # email free
    async with _client(db) as client:
        resp = await client.post(
            "/admin/users",
            json={"email": "new@example.com", "password": "long-enough-password", "role": "member"},
            headers=_bearer(admin),
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com" and body["role"] == "member"
    assert any(isinstance(o, User) for o in db.added)


@pytest.mark.asyncio
async def test_cannot_demote_last_admin():
    admin = make_user(role="admin")
    db = FakeDb()
    db.get_impl = lambda model, pk: admin
    db.execute_impl = lambda stmt: FakeResult(scalar=0)  # no other admins
    async with _client(db) as client:
        resp = await client.patch(
            f"/admin/users/{admin.id}", json={"role": "member"}, headers=_bearer(admin)
        )
    assert resp.status_code == 400
    assert "last admin" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_change_password_wrong_current_400():
    admin = make_user(role="admin")
    db = FakeDb()
    db.get_impl = lambda model, pk: admin
    async with _client(db) as client:
        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "wrong-password-xx", "new_password": "another-long-password"},
            headers=_bearer(admin),
        )
    assert resp.status_code == 400


# --- register (self-service sign-up) ---


@pytest.mark.asyncio
async def test_register_first_user_is_admin():
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=None, scalar=0)
    async with _client(db) as client:
        resp = await client.post(
            "/auth/register", json={"email": "New@Example.com", "password": "abc1234"}
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["role"] == "admin"
    assert body["user"]["email"] == "new@example.com"
    assert body["access_token"] and body["refresh_token"]
    assert [type(o).__name__ for o in db.added] == ["User", "RefreshToken"]


@pytest.mark.asyncio
async def test_register_member_when_users_exist():
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=None, scalar=1)
    async with _client(db) as client:
        resp = await client.post(
            "/auth/register", json={"email": "second@example.com", "password": "abc1234"}
        )
    assert resp.status_code == 201
    assert resp.json()["user"]["role"] == "member"


@pytest.mark.asyncio
async def test_register_duplicate_email_409():
    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=make_user(), scalar=1)
    async with _client(db) as client:
        resp = await client.post(
            "/auth/register", json={"email": "admin@example.com", "password": "abc1234"}
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password_400_before_db():
    db = FakeDb()  # execute_impl unset — any DB query would fail the test
    async with _client(db) as client:
        resp = await client.post(
            "/auth/register", json={"email": "a@example.com", "password": "short"}
        )
    assert resp.status_code == 400
    assert db.added == []


# --- GitHub OAuth ---


def test_oauth_state_roundtrip_and_tamper():
    from reroute.api.auth import _sign_state, _verify_state

    s = get_settings()
    state = _sign_state(s)
    assert _verify_state(s, state)
    assert not _verify_state(s, state[:-1] + ("x" if state[-1] != "x" else "y"))  # bad sig
    assert not _verify_state(s, None)
    assert not _verify_state(s, "garbage")


def test_oauth_state_expires(monkeypatch):
    from reroute.api import auth as auth_mod

    s = get_settings()
    state = auth_mod._sign_state(s)
    now = auth_mod.time.time()
    monkeypatch.setattr(auth_mod.time, "time", lambda: now + auth_mod._STATE_TTL + 1)
    assert not auth_mod._verify_state(s, state)


@pytest.mark.asyncio
async def test_github_authorize_unconfigured_501():
    db = FakeDb()
    async with _client(db) as client:
        resp = await client.get("/auth/github/authorize")
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_github_callback_creates_admin_and_stashes_session(monkeypatch):
    import httpx

    from reroute.api import auth as auth_mod

    s = get_settings()
    state = auth_mod._sign_state(s)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "github.com":
            return httpx.Response(200, json={"access_token": "gho_x"})
        if request.url.path == "/user":
            return httpx.Response(200, json={"id": 42, "email": None})
        return httpx.Response(200, json=[
            {"email": "gh@example.com", "primary": True, "verified": True}
        ])

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        auth_mod,
        "_github_client",
        lambda: httpx.AsyncClient(transport=transport, follow_redirects=True, timeout=15),
    )

    db = FakeDb()
    db.execute_impl = lambda stmt: FakeResult(first=None, scalar=0)
    async with _client(db) as client:
        resp = await client.get(f"/auth/github/callback?code=abc&state={state}")
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "gh_code=" in location and "localhost:5173/dashboard" in location

    users = [o for o in db.added if isinstance(o, User)]
    assert len(users) == 1
    assert users[0].email == "gh@example.com" and users[0].role == "admin"
    assert users[0].oauth_provider == "github" and users[0].oauth_id == "42"


@pytest.mark.asyncio
async def test_github_callback_bad_state_400():
    db = FakeDb()
    async with _client(db) as client:
        resp = await client.get("/auth/github/callback?code=abc&state=forged")
    assert resp.status_code == 400
    assert db.execute_impl is None  # rejected before touching the DB


@pytest.mark.asyncio
async def test_github_exchange_returns_session_once():
    import time as _time

    from reroute.api.auth import _pending_gh
    from reroute.schemas.auth import SessionUser, TokenResponse

    user = make_user(role="admin")
    payload = TokenResponse(
        access_token=create_access_token(user),
        refresh_token="raw-refresh",
        expires_in=900,
        user=SessionUser(id=str(user.id), email=user.email, role=user.role),
    ).model_dump_json()
    _pending_gh["code-once"] = (payload, _time.time() + 100)

    db = FakeDb()
    async with _client(db) as client:
        first = await client.post("/auth/github/exchange", json={"code": "code-once"})
        second = await client.post("/auth/github/exchange", json={"code": "code-once"})
    assert first.status_code == 200
    assert first.json()["user"]["email"] == user.email
    assert second.status_code == 400  # one-time
