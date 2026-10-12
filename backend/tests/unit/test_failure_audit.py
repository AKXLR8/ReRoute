"""Tests that failed requests leave audit rows (mocked collaborators)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4 as _uuid4

import pytest

from reroute.auth.auth import AuthContext
from reroute.cache.dedup import RequestDeduplicator
from reroute.gateway.handler import GatewayHandler
from reroute.rate_limit.rate_limiter import RateLimitExceeded
from reroute.schemas.chat import ChatRequest

_AUTH = AuthContext(user_id=str(_uuid4()), email="t@example.com", role="member", is_admin=False)
_PROVIDERS: list = []


def _request():
    return ChatRequest(model="m", messages=[{"role": "user", "content": "hi"}])


def _make_handler(router=None, rate_limiter=None):
    return GatewayHandler(
        router=router or MagicMock(),
        rate_limiter=rate_limiter or AsyncMock(),
        cache=AsyncMock(**{"get.return_value": None}),
        circuit_breakers=MagicMock(),
        deduplicator=RequestDeduplicator(),
    )


@pytest.mark.asyncio
async def test_provider_failure_writes_500_audit_row():
    router = MagicMock()
    router.route = AsyncMock(side_effect=RuntimeError("boom"))
    handler = _make_handler(router=router)
    db = AsyncMock()

    with pytest.raises(RuntimeError):
        await handler.handle_chat(_request(), db, _AUTH, _PROVIDERS)

    row = db.add.call_args[0][0]
    assert row.status_code == 500
    assert "boom" in row.error_message
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_no_provider_writes_503_audit_row():
    router = MagicMock()
    router.route = AsyncMock(side_effect=ValueError("no provider"))
    handler = _make_handler(router=router)
    db = AsyncMock()

    with pytest.raises(ValueError):
        await handler.handle_chat(_request(), db, _AUTH, _PROVIDERS)

    row = db.add.call_args[0][0]
    assert row.status_code == 503
    assert "no provider" in row.error_message


@pytest.mark.asyncio
async def test_rate_limit_writes_429_audit_row():
    rate_limiter = AsyncMock()
    rate_limiter.check_rpm = AsyncMock(side_effect=RateLimitExceeded("rpm", 1.0))
    handler = _make_handler(rate_limiter=rate_limiter)
    db = AsyncMock()

    with pytest.raises(RateLimitExceeded):
        await handler.handle_chat(_request(), db, _AUTH, _PROVIDERS)

    row = db.add.call_args[0][0]
    assert row.status_code == 429
