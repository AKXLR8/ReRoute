"""BYOK — bring-your-own-key: each account connects its own provider credentials.

Keys are encrypted at rest with Fernet. Uses FERNET_KEY env var if set;
otherwise derives from JWT_SECRET (legacy). Rotating FERNET_KEY requires
re-encrypting all stored keys — provide a migration script.
Resolution is strictly per-user: a request routes only over the caller's own
connected keys (+ ollama, which needs none). No global/gateway fallback.

Multi-worker: instance cache lives in Redis + pub/sub invalidation so all
workers see key changes instantly.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import logging
import uuid
from datetime import datetime
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models.provider_key import ProviderKey
from .base import Provider, ProviderHealth

log = logging.getLogger(__name__)

# Redis keys/prefixes
_INST_PREFIX = "byok:instances:"
_INVAL_CHANNEL = "byok:invalidate"


def _fernet() -> Fernet:
    s = get_settings()
    secret = s.fernet_key or s.jwt_secret
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_key(raw: str) -> str:
    if not raw:
        return ""
    return _fernet().encrypt(raw.encode()).decode()


def decrypt_key(token: str) -> str:
    if not token:
        return ""
    return _fernet().decrypt(token.encode()).decode()


def mask_key(token: str) -> str:
    """Safe-to-display form — never return the raw key after creation."""
    try:
        plain = decrypt_key(token)
    except Exception:
        return "***broken***"  # secret rotated/corrupt — visible in account UI
    if not plain:
        return ""
    if len(plain) <= 8:
        return "***"
    return f"{plain[:3]}...{plain[-4:]}"


def clone_with_key(shared: Provider, api_key: str, base_url: str | None) -> Provider:
    """Instance of a provider with connected credentials: own client, own health."""
    p = copy.copy(shared)
    p.api_key = api_key
    if base_url:
        p.base_url = base_url
    p._client = None  # rebuilt with this instance's key/base_url on first use
    p.health = ProviderHealth()  # a bad key must not poison shared health
    return p


def _check_base_url(url: str) -> None:
    """SSRF guard for supplied base URLs.

    Blocks scheme tricks + cloud metadata / link-local targets.
    If ALLOW_PRIVATE_BASE_URLS=false (default), also blocks RFC1918 private ranges.
    Full SSRF protection needs egress policy + DNS pinning at the proxy layer.
    """
    from ..config import get_settings
    s = get_settings()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(status_code=422, detail="base_url must be an http(s) URL")
    host = parsed.hostname.lower()

    # Always block metadata endpoints + link-local
    if (
        host == "metadata.google.internal"
        or host.startswith("169.254.")  # IPv4 link-local / AWS+GCP metadata
        or host.startswith("fe80:")     # IPv6 link-local
    ):
        raise HTTPException(status_code=422, detail="base_url host is not allowed")

    # Optionally block private RFC1918 ranges
    if not s.allow_private_base_urls:
        import ipaddress
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise HTTPException(
                    status_code=422,
                    detail="base_url host is not allowed (private/reserved IP blocked)",
                )
        except ValueError:
            # hostname, not IP — could DNS-resolve to private IP at runtime.
            # Full protection needs egress policy at network layer.
            pass


def _instance_key(user_id: str) -> str:
    return f"{_INST_PREFIX}{user_id}"


async def _publish_invalidate(redis: Redis, user_id: str) -> None:
    await redis.publish(_INVAL_CHANNEL, user_id)


async def _subscribe_invalidate(redis: Redis):
    pubsub = redis.pubsub()
    await pubsub.subscribe(_INVAL_CHANNEL)
    return pubsub


async def _warm_instance_cache(redis: Redis, user_id: str, registry, db: AsyncSession) -> None:
    """Build and cache provider instances for a user."""

    out: list[Provider] = []
    seen: set[str] = set()
    for row in await list_keys(db, user_id):
        shared = registry.get(row.provider)
        if shared is None:
            continue
        try:
            key = decrypt_key(row.api_key_encrypted)
        except Exception as exc:
            log.warning("Unreadable key for %s (rotate JWT_SECRET?): %s", row.provider, exc)
            continue
        out.append(clone_with_key(shared, key, row.base_url))
        seen.add(row.provider)

    ollama = registry.get("ollama")
    if ollama is not None and "ollama" not in seen:
        out.append(ollama)  # keyless: usable by every account

    data = json.dumps([
        {"provider": p.name, "api_key": p.api_key, "base_url": p.base_url}
        for p in out
    ])
    await redis.set(_instance_key(user_id), data)


async def _invalidate_handler(redis: Redis, registry, session_factory):
    """Background task: listen for invalidation events and refresh local cache."""
    pubsub = await _subscribe_invalidate(redis)
    async for msg in pubsub.listen():
        if msg["type"] != "message":
            continue
        user_id = msg["data"]
        # Rebuild from DB on next resolve_user call (lazy) or eagerly:
        async with session_factory() as db:
            await _warm_instance_cache(redis, user_id, registry, db)


async def start_invalidation_listener(redis: Redis, registry, session_factory):
    """Start the background invalidation listener. Call once at startup.

    Reconnects with backoff — cloud Redis drops idle pub/sub sockets.
    """
    import asyncio

    async def _loop():
        delay = 1.0
        while True:
            try:
                await _invalidate_handler(redis, registry, session_factory)
                delay = 1.0  # clean exit (shouldn't happen) — restart fast
            except asyncio.CancelledError:
                raise
            except Exception:
                log.warning("byok invalidation listener died, reconnecting", exc_info=True)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30.0)

    asyncio.create_task(_loop())


async def list_keys(db: AsyncSession, user_id: str) -> list[ProviderKey]:
    result = await db.execute(
        select(ProviderKey)
        .where(ProviderKey.user_id == uuid.UUID(user_id))
        .order_by(ProviderKey.provider)
    )
    return list(result.scalars().all())


async def resolve_user(redis: Redis, user_id: str, registry, db: AsyncSession) -> list[Provider]:
    """The instances this user's traffic may use: own connected keys + ollama.

    Cached in Redis; connect/disconnect/delete invalidate via pub/sub.
    Unreadable keys (rotated JWT_SECRET) are skipped with a warning, not a crash.
    """
    # Try Redis cache first
    cached = await redis.get(_instance_key(user_id))
    if cached:
        data = json.loads(cached)
        out: list[Provider] = []
        for item in data:
            shared = registry.get(item["provider"])
            if shared is None:
                continue
            p = copy.copy(shared)
            p.api_key = item["api_key"]
            p.base_url = item["base_url"] or ""
            p._client = None
            p.health = ProviderHealth()
            out.append(p)
        return out

    # Cache miss — build from DB
    out: list[Provider] = []
    seen: set[str] = set()
    for row in await list_keys(db, user_id):
        shared = registry.get(row.provider)
        if shared is None:
            continue
        try:
            key = decrypt_key(row.api_key_encrypted)
        except Exception as exc:
            log.warning("Unreadable key for %s (rotate JWT_SECRET?): %s", row.provider, exc)
            continue
        out.append(clone_with_key(shared, key, row.base_url))
        seen.add(row.provider)

    ollama = registry.get("ollama")
    if ollama is not None and "ollama" not in seen:
        out.append(ollama)

    # Cache for next time
    data = json.dumps([
        {"provider": p.name, "api_key": p.api_key, "base_url": p.base_url}
        for p in out
    ])
    await redis.set(_instance_key(user_id), data)
    return out


async def connect(
    db: AsyncSession,
    user_id: str,
    provider: str,
    api_key: str,
    base_url: str | None,
    registry,
    redis: Redis,
) -> ProviderKey:
    """Validate credentials against the provider, then upsert this user's row."""
    shared = registry.get(provider)
    if shared is None:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider}'")
    if not api_key and not base_url:
        raise HTTPException(status_code=422, detail="Provide an api_key and/or base_url")
    if base_url:
        _check_base_url(base_url)

    probe = clone_with_key(shared, api_key, base_url)
    try:
        ok = await probe.health_check()
    finally:
        await probe.aclose()
    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"Provider '{provider}' rejected these credentials (or is unreachable)",
        )

    uid = uuid.UUID(user_id)
    result = await db.execute(
        select(ProviderKey).where(ProviderKey.user_id == uid, ProviderKey.provider == provider)
    )
    row = result.scalar_one_or_none()
    enc = encrypt_key(api_key)
    if row:
        row.api_key_encrypted = enc
        row.base_url = base_url or None
    else:
        row = ProviderKey(
            user_id=uid, provider=provider, api_key_encrypted=enc, base_url=base_url or None
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)

    # Invalidate cache across all workers (pub/sub) + local immediate delete
    await redis.delete(_instance_key(user_id))
    await _publish_invalidate(redis, user_id)
    return row


async def disconnect(db: AsyncSession, user_id: str, provider: str, redis: Redis) -> None:
    result = await db.execute(
        select(ProviderKey).where(
            ProviderKey.user_id == uuid.UUID(user_id), ProviderKey.provider == provider
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No connected provider '{provider}'")
    await db.delete(row)
    await db.commit()

    # Invalidate cache across all workers (pub/sub) + local immediate delete
    await redis.delete(_instance_key(user_id))
    await _publish_invalidate(redis, user_id)


def serialize(row: ProviderKey) -> dict:
    created = row.created_at
    return {
        "provider": row.provider,
        "base_url": row.base_url,
        "key_masked": mask_key(row.api_key_encrypted),
        "created_at": created.isoformat() if isinstance(created, datetime) else created,
    }