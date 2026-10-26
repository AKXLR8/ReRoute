"""Account endpoints — first-run setup, login, token rotation, self-service.

Security posture:
- login is generic-401 (no user enumeration) + per-account lockout + per-IP throttle
- setup requires the env ADMIN_API_KEY and only works while zero users exist
- refresh tokens rotate; reuse revokes every session for that user
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode

import bcrypt
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.accounts import (
    authenticate,
    hash_token,
    new_refresh_row,
    revoke_all_sessions,
    rotate_refresh,
)
from ..auth.accounts import (
    logout as logout_token,
)
from ..auth.auth import API_KEY_PREFIX, AuthContext, create_access_token, get_current_user
from ..auth.passwords import check_policy, hash_password, verify_password
from ..config import Settings, get_settings
from ..database import get_db
from ..models.api_key import ApiKey
from ..models.user import User
from ..providers import byok
from ..schemas.auth import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyRead,
    ChangePasswordRequest,
    GithubExchangeRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    SessionUser,
    SetupRequest,
    TokenResponse,
)
from ..schemas.provider import ProviderConnect, ProviderRead

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# Redis-backed per-IP login throttle — works across multiple workers.
# Key: login:throttle:{ip} -> sorted set of timestamps (score = timestamp, member = uuid)
# Falls back to in-memory if Redis unavailable (tests).

# Module-level fallback for tests without Redis
_ip_hits: dict[str, list[float]] = {}


async def _throttle(request: Request, limit: int | None = None, window: float = 60.0) -> None:
    s = get_settings()
    effective_limit = limit if limit is not None else s.login_rate_limit_per_ip
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    key = f"login:throttle:{ip}"

    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        try:
            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zcard(key)
            pipe.zadd(key, {f"{now}:{uuid.uuid4().hex[:8]}": now})
            pipe.expire(key, int(window) + 1)
            results = await pipe.execute()
            if results[1] >= effective_limit:
                ttl = await redis.ttl(key)
                raise HTTPException(
                    status_code=429,
                    detail="Too many attempts. Try again later.",
                    headers={"Retry-After": str(max(ttl, 1))},
                )
            return
        except HTTPException:
            raise
        except Exception:
            # Redis down → degrade to in-memory throttle; login must not 500 on a cache blip
            log.warning("redis throttle failed, falling back to in-memory", exc_info=True)

    hits = [t for t in _ip_hits.get(ip, []) if now - t < window]
    hits.append(now)
    _ip_hits[ip] = hits
    if len(hits) > effective_limit:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(int(window))},
        )


async def _user_count(db: AsyncSession) -> int:
    return int((await db.execute(select(func.count(User.id)))).scalar_one())


async def _issue_session(db: AsyncSession, user: User) -> TokenResponse:
    s = get_settings()
    access = create_access_token(user)
    raw, row = new_refresh_row(user.id, s, datetime.now(UTC))
    db.add(row)
    await db.commit()
    return TokenResponse(
        access_token=access,
        refresh_token=raw,
        expires_in=s.access_expire_minutes * 60,
        user=SessionUser(id=str(user.id), email=user.email, role=user.role),
    )


@router.get("/setup")
async def setup_status(db: AsyncSession = Depends(get_db)):
    return {"needs_setup": await _user_count(db) == 0}


@router.post("/setup", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
async def setup(
    body: SetupRequest,
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Create the first admin account — one-shot, gated by the env ADMIN_API_KEY."""
    await _throttle(request)
    s = get_settings()
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Invalid setup key")
    if s.admin_api_key_hash:
        valid = bcrypt.checkpw(x_api_key.encode(), s.admin_api_key_hash.encode())
    else:
        valid = hmac.compare_digest(x_api_key, s.admin_api_key)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid setup key")
    if await _user_count(db) > 0:
        raise HTTPException(status_code=403, detail="Setup already completed")
    if err := check_policy(body.password):
        raise HTTPException(status_code=400, detail=err)

    user = User(email=body.email, password_hash=hash_password(body.password), role="admin")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    log.info("setup: first admin created email=%s ip=%s", user.email, request.client.host)
    return await _issue_session(db, user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    await _throttle(request)
    s = get_settings()
    user = await authenticate(db, body.email, body.password, s)  # email normalized by schema
    tokens = await _issue_session(db, user)  # commits lockout resets + refresh row
    log.info("login ok email=%s ip=%s", user.email, request.client.host)
    return tokens


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Self-service sign-up — first account becomes admin, everyone else a member."""
    s = get_settings()
    await _throttle(request, limit=s.register_rate_limit_per_hour, window=3600.0)
    if not s.allow_registration:
        raise HTTPException(status_code=403, detail="Registration is disabled")
    if err := check_policy(body.password):
        raise HTTPException(status_code=400, detail=err)
    if (await db.execute(select(User).where(User.email == body.email))).scalars().first():
        raise HTTPException(status_code=409, detail="Email already registered")

    role = "admin" if await _user_count(db) == 0 else "member"
    user = User(email=body.email, password_hash=hash_password(body.password), role=role)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    log.info("register: %s created email=%s ip=%s", role, user.email, request.client.host)
    return await _issue_session(db, user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    s = get_settings()
    user, raw = await rotate_refresh(db, body.refresh_token, s)
    access = create_access_token(user)
    return TokenResponse(
        access_token=access,
        refresh_token=raw,
        expires_in=s.access_expire_minutes * 60,
        user=SessionUser(id=str(user.id), email=user.email, role=user.role),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest, db: AsyncSession = Depends(get_db)):
    await logout_token(db, body.refresh_token)


@router.get("/me", response_model=SessionUser)
async def me(auth: AuthContext = Depends(get_current_user)):
    return SessionUser(id=auth.user_id, email=auth.email, role=auth.role or "admin")


# --- gateway API keys: the credential apps use to call /v1 ---
#
# Session-only by design: a leaked gateway key must not be able to mint more
# keys or read the list, otherwise revoking it would be pointless.


def _require_session(auth: AuthContext) -> uuid.UUID:
    if not auth.user_id:
        raise HTTPException(status_code=403, detail="Requires a signed-in account")
    if auth.api_key_id:
        raise HTTPException(
            status_code=403,
            detail="Manage API keys from a signed-in session, not with an API key",
        )
    return uuid.UUID(auth.user_id)


def _api_key_read(row: ApiKey) -> ApiKeyRead:
    return ApiKeyRead(
        id=str(row.id),
        name=row.name,
        key_prefix=row.key_prefix,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
    )


@router.get("/api-keys", response_model=list[ApiKeyRead])
async def list_api_keys(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = _require_session(auth)
    rows = (
        await db.execute(
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at.desc())
        )
    ).scalars().all()
    return [_api_key_read(r) for r in rows]


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreate,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mint a key. The raw value is returned exactly once."""
    user_id = _require_session(auth)
    raw = API_KEY_PREFIX + secrets.token_urlsafe(32)
    row = ApiKey(
        user_id=user_id,
        name=body.name.strip(),
        key_hash=hash_token(raw),
        key_prefix=raw[: len(API_KEY_PREFIX) + 4],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    log.info("api key created user=%s key=%s", auth.email, row.id)
    return ApiKeyCreated(key=raw, **_api_key_read(row).model_dump())


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = _require_session(auth)
    row = (
        await db.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
        )
    ).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        await db.commit()
        log.info("api key revoked user=%s key=%s", auth.email, row.id)
    return None


# --- per-user BYOK: every signed-in account manages its own provider keys ---


def _require_account(auth: AuthContext) -> str:
    if not auth.user_id:
        raise HTTPException(status_code=403, detail="Requires a signed-in account")
    return auth.user_id


@router.get("/providers", response_model=list[ProviderRead])
async def list_my_providers(
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connected keys for the calling account (masked, write-only)."""
    return [byok.serialize(r) for r in await byok.list_keys(db, _require_account(auth))]


@router.put("/providers/{provider}", response_model=ProviderRead)
async def connect_my_provider(
    provider: str,
    body: ProviderConnect,
    request: Request,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect (or replace) one of this account's provider keys. Validated against the provider."""
    row = await byok.connect(
        db, _require_account(auth), provider, body.api_key, body.base_url,
        request.app.state.registry, request.app.state.redis,
    )
    return byok.serialize(row)


@router.delete("/providers/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_my_provider(
    provider: str,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    http_request: Request = None,
):
    await byok.disconnect(db, _require_account(auth), provider, http_request.app.state.redis)


@router.post("/change-password", response_model=TokenResponse)
async def change_password(
    body: ChangePasswordRequest,
    auth: AuthContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Prove current password, then rotate everything: hash, token_version
    (kills all access JWTs), refresh rows — and hand back a fresh session."""
    if not auth.user_id:
        raise HTTPException(status_code=400, detail="Password changes require a signed-in account")
    if err := check_policy(body.new_password):
        raise HTTPException(status_code=400, detail=err)
    user = await db.get(User, uuid.UUID(auth.user_id))
    if user is None or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    await revoke_all_sessions(db, user.id, datetime.now(UTC))
    log.info("password changed email=%s", user.email)
    return await _issue_session(db, user)


# --- GitHub OAuth: authorize -> GitHub -> callback -> session stashed for the SPA ---

# one-time exchange codes when Redis isn't wired (tests); TTL mirrors redis TTL
_pending_gh: dict[str, tuple[str, float]] = {}

_STATE_TTL = 600  # seconds between authorize and callback
_PENDING_TTL = 300  # seconds the SPA has to pick up the stashed session


def _sign_state(s: Settings) -> str:
    nonce = secrets.token_urlsafe(16)
    ts = str(int(time.time()))
    sig = hmac.new(s.jwt_secret.encode(), f"{nonce}:{ts}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{nonce}.{ts}.{sig}"


def _verify_state(s: Settings, state: str | None) -> bool:
    try:
        nonce, ts, sig = state.split(".")
        expected_ts = int(ts)
    except (AttributeError, ValueError):
        return False
    want = hmac.new(
        s.jwt_secret.encode(), f"{nonce}:{ts}".encode(), hashlib.sha256
    ).hexdigest()[:32]
    return hmac.compare_digest(sig, want) and time.time() - expected_ts < _STATE_TTL


def _github_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=15, follow_redirects=True)


def _pick_github_email(gh_user: dict, emails: object) -> str:
    """primary+verified > any verified > profile email > noreply fallback."""
    candidates = [e for e in (emails if isinstance(emails, list) else []) if isinstance(e, dict)]
    for want in ((True, True), (False, True)):
        for e in candidates:
            if bool(e.get("primary")) is want[0] and bool(e.get("verified")) is want[1]:
                return str(e.get("email", "")).strip().lower()
    if gh_user.get("email"):
        return str(gh_user["email"]).strip().lower()
    if gh_user.get("id"):
        return f"{gh_user['id']}@users.noreply.github.com"
    return ""


@router.get("/github/authorize")
async def github_authorize():
    """Send the browser to GitHub. Set GITHUB_CLIENT_ID/SECRET in .env first."""
    s = get_settings()
    if not s.github_client_id:
        raise HTTPException(status_code=501, detail="GitHub sign-in is not configured")
    qs = urlencode({
        "client_id": s.github_client_id,
        "redirect_uri": s.github_redirect_uri,
        "scope": "read:user user:email",
        "state": _sign_state(s),
    })
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{qs}")


@router.get("/github/callback")
async def github_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """GitHub landed here — exchange the code, find-or-create the account, stash the session."""
    s = get_settings()
    if error or not code or not _verify_state(s, state):
        raise HTTPException(status_code=400, detail="GitHub sign-in failed")
    async with _github_client() as client:
        tok_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": s.github_client_id,
                "client_secret": s.github_client_secret,
                "code": code,
                "redirect_uri": s.github_redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        gh_token = tok_resp.json().get("access_token") if tok_resp.status_code == 200 else None
        if not gh_token:
            raise HTTPException(status_code=400, detail="GitHub sign-in failed")
        hdr = {"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json"}
        gh_user = (await client.get("https://api.github.com/user", headers=hdr)).json()
        emails = (await client.get("https://api.github.com/user/emails", headers=hdr)).json()

    email = _pick_github_email(gh_user, emails)
    if not email:
        raise HTTPException(status_code=400, detail="GitHub account has no email")

    user = (await db.execute(select(User).where(User.email == email))).scalars().first()
    if user is None:
        # random unusable password: sign-in via GitHub (or a later admin reset) only
        user = User(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role="admin" if await _user_count(db) == 0 else "member",
        )
        db.add(user)
    if gh_user.get("id"):
        user.oauth_provider = "github"
        user.oauth_id = str(gh_user["id"])
    await db.commit()
    await db.refresh(user)
    log.info("github sign-in email=%s", user.email)

    tokens = await _issue_session(db, user)
    pending = secrets.token_urlsafe(24)
    payload = tokens.model_dump_json()
    redis = getattr(request.app.state, "redis", None)
    if redis is not None:
        await redis.setex(f"gh:pending:{pending}", _PENDING_TTL, payload)
    else:
        _pending_gh[pending] = (payload, time.time() + _PENDING_TTL)
    # tokens travel via one-time code, never in the URL (history/referrer leak)
    return RedirectResponse(f"{s.frontend_base_url}/dashboard?gh_code={pending}", status_code=302)


@router.post("/github/exchange", response_model=TokenResponse)
async def github_exchange(body: GithubExchangeRequest, request: Request):
    """Consume the one-time ?gh_code= into a normal session."""
    redis = getattr(request.app.state, "redis", None)
    payload: str | None = None
    if redis is not None:
        raw = await redis.get(f"gh:pending:{body.code}")
        if raw is not None:
            await redis.delete(f"gh:pending:{body.code}")
            payload = raw.decode() if isinstance(raw, bytes) else raw
    else:
        entry = _pending_gh.pop(body.code, None)
        if entry is not None and entry[1] > time.time():
            payload = entry[0]
    if payload is None:
        raise HTTPException(status_code=400, detail="Invalid or expired sign-in code")
    return TokenResponse.model_validate_json(payload)
