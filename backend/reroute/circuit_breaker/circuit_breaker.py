"""Per-provider circuit breaker — closed → open → half-open → closed.

Multi-worker: state lives in Redis so all workers share the same circuit status.
"""

from __future__ import annotations

import asyncio
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
_PUBLIC_PREFIX = f"{_CB_PREFIX}p:"
_USER_PREFIX = f"{_CB_PREFIX}u:"


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    """Redis-backed circuit breaker for one provider *and* one user scope."""

    def __init__(self, provider_name: str, redis: Redis, key: str | None = None) -> None:
        s = get_settings()
        self.provider = provider_name
        self.redis = redis
        self.failure_threshold = s.circuit_breaker_failure_threshold
        self.recovery_seconds = s.circuit_breaker_recovery_seconds
        self._key = key or f"{_PUBLIC_PREFIX}{provider_name}"

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
        await self.redis.hset(
            self._key,
            mapping={
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
        state, failure_count, _ = await self._get_state()
        failure_count += 1
        # A failed half-open probe re-opens immediately; requiring another full
        # threshold lets a dead provider take the whole traffic burst again.
        if state == CircuitState.HALF_OPEN.value or failure_count >= self.failure_threshold:
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
        elif isinstance(exc, asyncio.CancelledError):
            pass  # client disconnect / shutdown is not a provider failure
        else:
            await self.record_failure()

    async def get_status(self) -> dict[str, Any]:
        """Read-only snapshot: never transitions state (public /status calls this)."""
        state, failure_count, opened_at = await self._get_state()
        if (
            state == CircuitState.OPEN.value
            and time.time() - opened_at >= self.recovery_seconds
        ):
            state = CircuitState.HALF_OPEN.value  # display only; do not mutate
        available = state in (CircuitState.CLOSED.value, CircuitState.HALF_OPEN.value)
        return {
            "state": state,
            "failure_count": failure_count,
            "is_available": available,
        }


class CircuitBreakerRegistry:
    """Provider-scoped by default; user-scoped when a request scope is passed.

    Public status only sees the shared/env-keyed provider circuits (`cb:p:*`),
    never per-user scope names (those contain user UUIDs).
    """

    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self._breakers: dict[str, CircuitBreaker] = {}

    def get(self, provider_name: str, scope: str | None = None) -> CircuitBreaker:
        key = (
            f"{_PUBLIC_PREFIX}{provider_name}"
            if scope is None
            else f"{_USER_PREFIX}{scope}:{provider_name}"
        )
        if key not in self._breakers:
            self._breakers[key] = CircuitBreaker(provider_name, self.redis, key=key)
        return self._breakers[key]

    async def all_status(self, include_users: bool = False) -> dict[str, dict[str, Any]]:
        """Public view is shared circuits only; admin view aggregates user
        circuits by provider so scope UUIDs never leak into /status."""
        status: dict[str, dict[str, Any]] = {}
        pattern = f"{_CB_PREFIX}*" if include_users else f"{_PUBLIC_PREFIX}*"
        rank = {CircuitState.CLOSED.value: 0, CircuitState.HALF_OPEN.value: 1,
                CircuitState.OPEN.value: 2}
        async for key in self.redis.scan_iter(match=pattern, count=100):
            name = key.decode() if isinstance(key, bytes) else key
            if name.startswith(_PUBLIC_PREFIX):
                provider_name = name[len(_PUBLIC_PREFIX):]
            elif include_users and name.startswith(_USER_PREFIX):
                provider_name = name.rsplit(":", 1)[-1]
            else:
                continue
            snapshot = await CircuitBreaker(
                provider_name, self.redis, key=name
            ).get_status()
            current = status.get(provider_name)
            if current is None:
                status[provider_name] = snapshot
                continue
            # worst state wins; availability requires every circuit available
            if rank.get(snapshot["state"], 0) > rank.get(current["state"], 0):
                current["state"] = snapshot["state"]
            current["failure_count"] += snapshot["failure_count"]
            current["is_available"] = current["is_available"] and snapshot["is_available"]
        return status
