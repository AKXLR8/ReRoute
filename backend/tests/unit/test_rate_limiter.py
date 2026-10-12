"""Tests for rate limiter (unit — uses fakeredis)."""

import fakeredis.aioredis
import pytest

from reroute.rate_limit.rate_limiter import RateLimiter, RateLimitExceeded


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis()
    yield r
    await r.aclose()


@pytest.mark.asyncio
async def test_allows_under_limit(redis):
    limiter = RateLimiter(redis)
    await limiter.check_rpm("team:test", limit=5)
    # Second request should also pass
    await limiter.check_rpm("team:test", limit=5)


@pytest.mark.asyncio
async def test_blocks_over_limit(redis):
    limiter = RateLimiter(redis)
    for _ in range(3):
        await limiter.check_rpm("team:test", limit=3)
    with pytest.raises(RateLimitExceeded) as exc_info:
        await limiter.check_rpm("team:test", limit=3)
    assert exc_info.value.limit_type == "requests_per_minute"


@pytest.mark.asyncio
async def test_concurrent_limit(redis):
    limiter = RateLimiter(redis)
    await limiter.check_concurrent("team:test", limit=2)
    await limiter.check_concurrent("team:test", limit=2)
    with pytest.raises(RateLimitExceeded):
        await limiter.check_concurrent("team:test", limit=2)
    await limiter.release_concurrent("team:test")
    # Now should pass again
    await limiter.check_concurrent("team:test", limit=2)
