"""Redis-backed fixed-window rate limiter.

Keys are scoped by user/API key. Supports:
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


_ACQUIRE_CONCURRENT = """
local c = redis.call('INCR', KEYS[1])
if c == 1 then redis.call('EXPIRE', KEYS[1], ARGV[2]) end
if c > tonumber(ARGV[1]) then
  redis.call('DECR', KEYS[1])
  return {0, redis.call('TTL', KEYS[1])}
end
return {1, 0}
"""

_RELEASE_CONCURRENT = """
local v = redis.call('DECR', KEYS[1])
if v < 0 then redis.call('SET', KEYS[1], 0, 'EX', ARGV[1]) end
return v
"""


class RateLimiter:
    """Fixed-window counters in Redis - simple, correct, fast enough."""

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
        allowed, ttl = await self.redis.eval(
            _ACQUIRE_CONCURRENT, 1, key, limit, 300
        )
        if not allowed:
            raise RateLimitExceeded("concurrent_requests", max(float(ttl), 1.0))
        return True

    async def release_concurrent(self, scope: str) -> None:
        key = f"rl:concurrent:{scope}"
        # DECR then SET 0 is not atomic: a concurrent acquire between the two
        # could be silently erased. One Lua script keeps the counter correct.
        await self.redis.eval(_RELEASE_CONCURRENT, 1, key, 300)
