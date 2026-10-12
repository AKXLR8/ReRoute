"""Per-provider circuit breaker — closed → open → half-open → closed.

Multi-worker: state lives in Redis so all workers share the same circuit status.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any

from redis.asyncio import Redis

from ..config import get_settings


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


_CB_PREFIX = "cb:"


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    """Redis-backed circuit breaker for a single provider."""

    def __init__(self, provider_name: str, redis: Redis) -> None:
        s = get_settings()
        self.provider = provider_name
        self.redis = redis
        self.failure_threshold = s.circuit_breaker_failure_threshold
        self.recovery_seconds = s.circuit_breaker_recovery_seconds
        self._key = f"{_CB_PREFIX}{provider_name}"

    async def _get_state(self) -> tuple[str, int, float]:
        """Get (state, failure_count, opened_at) from Redis."""
        data = await self.redis.hmget(
            self._key, "state", "failure_count", "opened_at"
        )
        state = data[0] or CircuitState.CLOSED.value
        # Redis returns bytes, decode to string
        if isinstance(state, bytes):
            state = state.decode()
        failure_count = int(data[1] or 0)
        opened_at = float(data[2] or 0.0)
        return state, failure_count, opened_at

    async def _set_state(
        self, state: CircuitState, failure_count: int, opened_at: float
    ) -> None:
        await self.redis.hmset(
            self._key,
            {
                "state": state.value,
                "failure_count": str(failure_count),
                "opened_at": str(opened_at),
            },
        )
        # Keep key alive for a while after last activity
        await self.redis.expire(self._key, 3600)

    @property
    async def is_available(self) -> bool:
        state, _, opened_at = await self._get_state()
        if state == CircuitState.CLOSED.value:
            return True
        if state == CircuitState.OPEN.value:
            if time.time() - opened_at >= self.recovery_seconds:
                # Transition to half-open atomically
                await self._set_state(CircuitState.HALF_OPEN, 0, 0.0)
                return True
            return False
        return True  # half_open

    async def record_success(self) -> None:
        await self._set_state(CircuitState.CLOSED, 0, 0.0)

    async def record_failure(self) -> None:
        state, failure_count, opened_at = await self._get_state()
        failure_count += 1
        if failure_count >= self.failure_threshold:
            await self._set_state(CircuitState.OPEN, failure_count, time.time())
        else:
            await self._set_state(CircuitState.CLOSED, failure_count, 0.0)

    async def __aenter__(self) -> CircuitBreaker:
        if not await self.is_available:
            raise CircuitOpenError(f"Circuit open for provider '{self.provider}'")
        return self

    async def __aexit__(self, exc_type: type | None, exc: Any, tb: Any) -> None:
        if exc is None:
            await self.record_success()
        elif isinstance(exc, CircuitOpenError):
            pass  # don't count the gate raise
        else:
            await self.record_failure()

    async def get_status(self) -> dict[str, Any]:
        state, failure_count, _ = await self._get_state()
        return {
            "state": state,
            "failure_count": failure_count,
            "is_available": await self.is_available,
        }


class CircuitBreakerRegistry:
    """Singleton mapping provider_name → CircuitBreaker (shared via Redis)."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(self, provider_name: str) -> CircuitBreaker:
        if provider_name not in self._breakers:
            self._breakers[provider_name] = CircuitBreaker(provider_name, self.redis)
        return self._breakers[provider_name]

    async def all_status(self) -> dict[str, dict[str, Any]]:
        # Get all circuit breaker keys from Redis
        keys = await self.redis.keys(f"{_CB_PREFIX}*")
        status: dict[str, dict[str, Any]] = {}
        for key in keys:
            if isinstance(key, bytes):
                provider_name = key.decode().replace(_CB_PREFIX, "")
            else:
                provider_name = key.replace(_CB_PREFIX, "")
            cb = self.get(provider_name)
            status[provider_name] = await cb.get_status()
        return status