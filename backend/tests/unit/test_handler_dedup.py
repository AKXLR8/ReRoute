"""Regression: handle_chat must work through the real RequestDeduplicator.

A double-passed `request` arg once broke every non-streaming chat request
(TypeError inside dedup.execute) with zero test failures.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4 as _uuid4

from reroute.auth.auth import AuthContext
from reroute.cache.dedup import RequestDeduplicator
from reroute.gateway.handler import GatewayHandler
from reroute.schemas.chat import ChatRequest, ChatResponse

_AUTH = AuthContext(user_id=str(_uuid4()), email="t@example.com", role="member", is_admin=False)
_PROVIDERS: list = []


def _make_handler(provider_chat):
    router = MagicMock()
    provider = MagicMock()
    provider.name = "stub"
    provider.chat = provider_chat
    provider.estimate_cost.return_value = 0.0

    # route() owns the provider call in production — mirror that here so the
    # await_count assertions still prove exactly one upstream call happens.
    async def _route(request, _providers):
        return provider, await provider.chat(request), None

    router.route = AsyncMock(side_effect=_route)

    return GatewayHandler(
        router=router,
        rate_limiter=AsyncMock(),
        cache=AsyncMock(**{"get.return_value": None}),
        circuit_breakers=MagicMock(),
        deduplicator=RequestDeduplicator(),  # real one — that's the point
    )


def _request():
    return ChatRequest(model="stub-model", messages=[{"role": "user", "content": "hi"}])


def _response():
    return ChatResponse(
        id="x",
        model="stub-model",
        choices=[{
            "index": 0,
            "message": {"role": "assistant", "content": "hi"},
            "finish_reason": "stop",
        }],
        usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        provider="stub",
        latency_ms=1.0,
    )


async def test_handle_chat_flows_through_dedup():
    provider_chat = AsyncMock(return_value=_response())
    handler = _make_handler(provider_chat)

    resp = await handler.handle_chat(_request(), AsyncMock(), _AUTH, _PROVIDERS)

    assert resp.provider == "stub"
    assert provider_chat.await_count == 1


async def test_concurrent_duplicates_coalesce():
    async def slow_chat(request):
        await asyncio.sleep(0.05)
        return _response()

    provider_chat = AsyncMock(side_effect=slow_chat)
    handler = _make_handler(provider_chat)
    db = AsyncMock()

    r1, r2 = await asyncio.gather(
        handler.handle_chat(_request(), db, _AUTH, _PROVIDERS),
        handler.handle_chat(_request(), db, _AUTH, _PROVIDERS),
    )

    assert r1.id == r2.id
    assert provider_chat.await_count == 1


async def test_real_router_calls_provider_exactly_once():
    """Regression: route() already calls provider.chat; the handler used to call
    it a second time, doubling upstream cost and latency on every request."""
    from fakeredis.aioredis import FakeRedis

    from reroute.circuit_breaker.circuit_breaker import CircuitBreakerRegistry
    from reroute.providers.base import ProviderHealth, ProviderRegistry
    from reroute.retry.retry import RetryEngine
    from reroute.router.router import Router

    provider = MagicMock()
    provider.name = "stub"
    provider.health = ProviderHealth()
    provider.health.available = True
    provider.health.latency_ms = 10
    provider.supports_model.return_value = True
    provider.estimate_cost.return_value = 0.0
    provider.chat = AsyncMock(return_value=_response())

    handler = GatewayHandler(
        router=Router(ProviderRegistry(), CircuitBreakerRegistry(FakeRedis()), RetryEngine()),
        rate_limiter=AsyncMock(),
        cache=AsyncMock(**{"get.return_value": None}),
        circuit_breakers=MagicMock(),
        deduplicator=RequestDeduplicator(),
    )

    resp = await handler.handle_chat(_request(), AsyncMock(), _AUTH, [provider])

    assert resp.provider == "stub"
    assert provider.chat.await_count == 1
