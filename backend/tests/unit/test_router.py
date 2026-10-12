"""Tests for the intelligent router."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fakeredis.aioredis import FakeRedis

from reroute.circuit_breaker.circuit_breaker import CircuitBreakerRegistry, CircuitState
from reroute.providers.base import Provider, ProviderHealth, ProviderRegistry
from reroute.retry.retry import RetryEngine
from reroute.router.router import Router
from reroute.schemas.chat import ChatMessage, ChatRequest, ChatResponse, Choice


def _make_provider(name: str) -> MagicMock:
    p = MagicMock(spec=Provider)
    p.name = name
    p.health = ProviderHealth()
    p.health.available = True
    p.health.latency_ms = 100
    p.supports_model.return_value = True
    p.chat = AsyncMock(return_value=ChatResponse(
        model="gpt-4o",
        choices=[Choice(message=ChatMessage(role="assistant", content="hi"))],
    ))
    return p


def _make_request(model: str = "gpt-4o") -> ChatRequest:
    return ChatRequest(model=model, messages=[ChatMessage(role="user", content="hello")])


@pytest.fixture
def redis():
    return FakeRedis()


@pytest.fixture
def router(redis):
    reg = ProviderRegistry()
    cb = CircuitBreakerRegistry(redis)
    retry = RetryEngine()
    retry.max_attempts = 1
    return Router(reg, cb, retry), reg


@pytest.mark.asyncio
async def test_route_picks_provider(router):
    engine, reg = router
    p = _make_provider("openai")
    reg.register(p)

    provider, response, fallback = await engine.route(_make_request(), [p])
    assert provider.name == "openai"
    assert fallback is None
    # route() must hand back the response it computed (it used to discard it,
    # forcing the handler to call the provider a second time)
    assert response.choices[0].message.content == "hi"


@pytest.mark.asyncio
async def test_route_fallback_on_failure(router):
    engine, reg = router
    p1 = _make_provider("openai")
    p1.chat = AsyncMock(side_effect=Exception("API down"))
    reg.register(p1)

    p2 = _make_provider("anthropic")
    reg.register(p2)

    provider, _response, fallback = await engine.route(_make_request(), [p1, p2])
    assert provider.name == "anthropic"
    assert fallback == "openai"


@pytest.mark.asyncio
async def test_route_raises_when_all_fail(router):
    engine, reg = router
    p1 = _make_provider("openai")
    p1.chat = AsyncMock(side_effect=Exception("fail"))
    reg.register(p1)

    with pytest.raises(Exception, match="fail"):
        await engine.route(_make_request(), [p1])


@pytest.mark.asyncio
async def test_route_filters_by_preferred_provider(router):
    engine, reg = router
    p1 = _make_provider("openai")
    reg.register(p1)
    p2 = _make_provider("anthropic")
    reg.register(p2)

    req = ChatRequest(
        model="gpt-4o",
        messages=[ChatMessage(role="user", content="hello")],
        provider="anthropic",
    )
    provider, _, _ = await engine.route(req, [p1, p2])
    assert provider.name == "anthropic"


@pytest.mark.asyncio
async def test_route_filters_by_circuit_breaker(router):
    engine, reg = router
    p1 = _make_provider("openai")
    reg.register(p1)
    p2 = _make_provider("anthropic")
    reg.register(p2)

    # Open the circuit for openai via Redis - set opened_at to now so it won't recover
    cb = engine.circuit_breakers.get("openai")
    import time
    await cb._set_state(CircuitState.OPEN, cb.failure_threshold, time.time())

    provider, _response, fallback = await engine.route(_make_request(), [p1, p2])
    # Should skip openai, pick anthropic
    assert provider.name == "anthropic"
