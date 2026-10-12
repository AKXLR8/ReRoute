"""BYOK — key encryption, per-user resolution, connect() validation."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from fakeredis.aioredis import FakeRedis
from fastapi import HTTPException

from reroute.providers import byok
from reroute.providers.base import Provider, ProviderRegistry
from reroute.router.router import Router


class StubProvider(Provider):
    def __init__(self, name: str, models: list[str], *, api_key: str = "", healthy: bool = True):
        super().__init__(api_key=api_key)
        self.name = name
        self._models = models
        self.health.available = healthy
        self._healthy = healthy

    async def chat(self, request):
        raise NotImplementedError

    async def stream(self, request):
        raise NotImplementedError

    async def health_check(self):
        return self._healthy

    def models(self):
        return self._models


# --- encryption ---

def test_encrypt_roundtrip():
    token = byok.encrypt_key("sk-super-secret")
    assert token != "sk-super-secret"
    assert byok.decrypt_key(token) == "sk-super-secret"


def test_empty_key_stays_empty():
    assert byok.encrypt_key("") == ""
    assert byok.decrypt_key("") == ""


def test_mask_hides_key():
    token = byok.encrypt_key("sk-abcdefghijklmnop")
    masked = byok.mask_key(token)
    assert masked == "sk-...mnop"
    assert "efghij" not in masked
    assert byok.mask_key("") == ""


def test_mask_shows_broken_for_corrupt_token():
    assert byok.mask_key("garbage-not-a-fernet-token") == "***broken***"


def test_clone_does_not_share_health_or_client():
    shared = StubProvider("groq", ["m1"], api_key="sk-gw")
    clone = byok.clone_with_key(shared, "sk-team", None)
    clone.health.available = False
    assert shared.health.available is True
    assert clone.api_key == "sk-team"


def test_gateway_keyed_shared_provider_still_routes():
    shared = StubProvider("openai", ["m1"], api_key="sk-gateway")
    reg = ProviderRegistry()
    reg.register(shared)
    assert reg.for_model("m1") == [shared]


# --- per-user resolution: own keys + ollama, cached in Redis ---

def _key_row(provider: str, encrypted: str | None = None):
    row = MagicMock()
    row.provider = provider
    row.api_key_encrypted = encrypted if encrypted is not None else byok.encrypt_key("sk-user-key")
    row.base_url = None
    return row


def _db_with_rows(*rows):
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(rows)
    result.scalar_one_or_none.return_value = rows[0] if rows else None
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def redis():
    return FakeRedis()


@pytest.mark.asyncio
async def test_resolve_user_returns_own_clones_plus_ollama(redis):
    reg = ProviderRegistry()
    shared = StubProvider("groq", ["m1"], api_key="", healthy=False)
    reg.register(shared)
    reg.register(StubProvider("ollama", ["lm"]))
    uid = str(uuid.uuid4())
    db = _db_with_rows(_key_row("groq"))

    got = await byok.resolve_user(redis, uid, reg, db)
    assert [p.name for p in got] == ["groq", "ollama"]
    inst = got[0]
    assert inst is not shared
    assert inst.api_key == "sk-user-key"
    assert inst.health.available is True  # fresh health, not the shared one


@pytest.mark.asyncio
async def test_resolve_user_cached_until_invalidated(redis):
    reg = ProviderRegistry()
    reg.register(StubProvider("groq", ["m1"]))
    uid = str(uuid.uuid4())
    db = _db_with_rows(_key_row("groq"))

    first = (await byok.resolve_user(redis, uid, reg, db))[0]
    second = (await byok.resolve_user(redis, uid, reg, db))[0]
    # Cache hit returns equal data, not same object (rebuilt from JSON)
    assert first.api_key == second.api_key
    assert first.name == second.name

    # Invalidate by directly deleting cache key
    await redis.delete(f"byok:instances:{uid}")
    third = (await byok.resolve_user(redis, uid, reg, db))[0]
    assert third is not first


@pytest.mark.asyncio
async def test_resolve_user_skips_unreadable_key(redis):
    reg = ProviderRegistry()
    reg.register(StubProvider("groq", ["m1"]))
    reg.register(StubProvider("ollama", ["lm"]))
    uid = str(uuid.uuid4())
    db = _db_with_rows(_key_row("groq", encrypted="garbage-not-a-fernet-token"))

    got = await byok.resolve_user(redis, uid, reg, db)
    assert [p.name for p in got] == ["ollama"]  # broken key skipped, not crashed


@pytest.mark.asyncio
async def test_resolve_user_without_keys_is_ollama_only(redis):
    reg = ProviderRegistry()
    reg.register(StubProvider("groq", ["m1"]))
    reg.register(StubProvider("ollama", ["lm"]))
    uid = str(uuid.uuid4())

    got = await byok.resolve_user(redis, uid, reg, _db_with_rows())
    assert [p.name for p in got] == ["ollama"]


@pytest.mark.asyncio
async def test_resolve_user_no_keys_no_ollama_is_empty(redis):
    reg = ProviderRegistry()
    reg.register(StubProvider("groq", ["m1"]))
    uid = str(uuid.uuid4())

    assert await byok.resolve_user(redis, uid, reg, _db_with_rows()) == []


@pytest.mark.asyncio
async def test_router_admits_user_provider_candidate():
    reg = ProviderRegistry()
    shared = StubProvider("groq", ["m1"], api_key="", healthy=False)
    reg.register(shared)

    # Mock circuit breaker with async is_available property
    class MockCB:
        @property
        async def is_available(self):
            return True

    breakers = MagicMock()
    breakers.get.return_value = MockCB()
    router = Router(reg, breakers, MagicMock())

    clone = byok.clone_with_key(shared, "gsk_team", None)
    candidates = await router._candidates("m1", [clone])
    assert [p.name for p in candidates] == ["groq"]
    # an unhealthy instance is not a candidate (fresh clones start healthy)
    candidates = await router._candidates("m1", [shared])
    assert candidates == []


# --- connect() validation + upsert (per user) ---

def _db_no_existing_row():
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=Mock(return_value=None)))
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_connect_upserts_encrypted_key_and_invalidates_cache(redis):
    reg = ProviderRegistry()
    reg.register(StubProvider("groq", ["m1"], api_key=""))
    db = _db_no_existing_row()
    uid = str(uuid.uuid4())
    # stale cache entry
    await redis.set(f"byok:instances:{uid}", '{"stale": true}')

    row = await byok.connect(db, uid, "groq", "gsk_secret", None, reg, redis)
    assert row.provider == "groq"
    assert byok.decrypt_key(row.api_key_encrypted) == "gsk_secret"
    db.add.assert_called_once()
    # cache invalidated
    cached = await redis.get(f"byok:instances:{uid}")
    assert cached is None  # invalidated on connect


@pytest.mark.asyncio
async def test_connect_unknown_provider_404(redis):
    reg = ProviderRegistry()
    db = _db_no_existing_row()
    with pytest.raises(HTTPException) as exc:
        await byok.connect(db, str(uuid.uuid4()), "nope", "key", None, reg, redis)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_connect_rejected_key_422(redis):
    reg = ProviderRegistry()
    reg.register(StubProvider("groq", ["m1"], api_key="", healthy=False))
    db = _db_no_existing_row()
    with pytest.raises(HTTPException) as exc:
        await byok.connect(db, str(uuid.uuid4()), "groq", "bad_key", None, reg, redis)
    assert exc.value.status_code == 422
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_connect_requires_key_or_base_url(redis):
    reg = ProviderRegistry()
    reg.register(StubProvider("groq", ["m1"]))
    db = _db_no_existing_row()
    with pytest.raises(HTTPException) as exc:
        await byok.connect(db, str(uuid.uuid4()), "groq", "", None, reg, redis)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_disconnect_removes_only_own_row_and_invalidates(redis):
    uid = str(uuid.uuid4())
    db = _db_with_rows(_key_row("groq"))
    # prime cache
    await redis.set(f"byok:instances:{uid}", '{"primed": true}')

    await byok.disconnect(db, uid, "groq", redis)
    cached = await redis.get(f"byok:instances:{uid}")
    assert cached is None


@pytest.mark.asyncio
async def test_disconnect_missing_row_404(redis):
    uid = str(uuid.uuid4())
    db = _db_with_rows()  # no rows for this user
    with pytest.raises(HTTPException) as exc:
        await byok.disconnect(db, uid, "groq", redis)
    assert exc.value.status_code == 404