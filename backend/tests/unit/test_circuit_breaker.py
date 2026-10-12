"""Tests for circuit breaker."""

import pytest
from fakeredis.aioredis import FakeRedis

from reroute.circuit_breaker.circuit_breaker import CircuitBreaker, CircuitState


@pytest.fixture
async def redis():
    r = FakeRedis()
    try:
        yield r
    finally:
        await r.aclose()


@pytest.mark.asyncio
async def test_starts_closed(redis):
    cb = CircuitBreaker("test", redis)
    state, _, _ = await cb._get_state()
    assert state == CircuitState.CLOSED.value
    assert await cb.is_available is True


@pytest.mark.asyncio
async def test_opens_after_threshold(redis):
    cb = CircuitBreaker("test", redis)
    # Default threshold is 5
    for _ in range(5):
        await cb.record_failure()
    state, _, _ = await cb._get_state()
    assert state == CircuitState.OPEN.value
    assert await cb.is_available is False


@pytest.mark.asyncio
async def test_recovers_after_timeout(redis):
    cb = CircuitBreaker("test", redis)
    cb.recovery_seconds = 0  # instant recovery for test
    # Default threshold is 5, use 5 failures
    for _ in range(5):
        await cb.record_failure()
    state, _, _ = await cb._get_state()
    assert state == CircuitState.OPEN.value
    assert await cb.is_available is True  # triggers half_open → closed path
    state, _, _ = await cb._get_state()
    assert state == CircuitState.HALF_OPEN.value


@pytest.mark.asyncio
async def test_success_resets(redis):
    cb = CircuitBreaker("test", redis)
    await cb.record_failure()
    await cb.record_success()
    state, fc, _ = await cb._get_state()
    assert state == CircuitState.CLOSED.value
    assert fc == 0