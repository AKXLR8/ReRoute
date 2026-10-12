"""Redis-backed token bucket rate limiter.

Keys are scoped by team_id and/or api_key_id. Supports:
- requests per minute
- tokens per minute
- concurrent requests
"""

from __future__ import annotations

import time

from redis.asyncio import Redis


class RateLimitExceeded(Exception):
    def __init__(self, limit_type: str, retry_after: float) -> None:
        self.limit_type = limit_type
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded: {limit_type}, retry after {retry_after:.1f}s")


class RateLimiter:
    """Sliding window counters in Redis — simple, correct, fast enough."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    def _window_key(self, prefix: str, scope: str, window_seconds: int = 60) -> str:
        minute = int(time.time()) // window_seconds
        return f"rl:{prefix}:{scope}:{minute}"

    async def _ensure_ttl(self, key: str, count: int, window: int, first: bool) -> None:
        """EXPIRE runs only on first write; a crash between INCR and EXPIRE
        leaves a key that never expires (permanent lockout for the concurrent
        key). Sampled heal when TTL is missing — never extends a live window.
        """
        if first or count % 25 == 0 and await self.redis.ttl(key) < 0:
            await self.redis.expire(key, window)

    async def check_rpm(self, scope: str, limit: int) -> None:
        key = self._window_key("rpm", scope)
        count = await self.redis.incr(key)
        await self._ensure_ttl(key, count, 120, first=count == 1)
        if count > limit:
            ttl = await self.redis.ttl(key)
            raise RateLimitExceeded("requests_per_minute", max(ttl, 1))

    async def check_tpm(self, scope: str, limit: int, tokens: int) -> None:
        key = self._window_key("tpm", scope)
        count = await self.redis.incrby(key, tokens)
        await self._ensure_ttl(key, count, 120, first=count == tokens)
        if count > limit:
            ttl = await self.redis.ttl(key)
            raise RateLimitExceeded("tokens_per_minute", max(ttl, 1))

    async def check_concurrent(self, scope: str, limit: int) -> bool:
        """Returns True if allowed. Caller must call release() when done."""
        key = f"rl:concurrent:{scope}"
        count = await self.redis.incr(key)
        await self._ensure_ttl(key, count, 300, first=count == 1)
        if count > limit:
            await self.redis.decr(key)
            ttl = await self.redis.ttl(key)
            raise RateLimitExceeded("concurrent_requests", max(ttl, 1))
        return True

    async def release_concurrent(self, scope: str) -> None:
        key = f"rl:concurrent:{scope}"
        val = await self.redis.decr(key)
        if val < 0:
            await self.redis.set(key, 0)
