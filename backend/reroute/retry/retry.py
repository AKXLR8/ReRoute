"""Retry engine — exponential backoff with jitter for transient failures."""

from __future__ import annotations

import asyncio
import contextlib
import random
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

import httpx

from ..config import get_settings
from ..observability.metrics import metrics_collector

T = TypeVar("T")

# Only retry on these conditions
_RETRYABLE_STATUS = {429, 500, 502, 503, 504, 529}


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException | httpx.ConnectError | httpx.RemoteProtocolError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return False


class RetryEngine:
    def __init__(self) -> None:
        s = get_settings()
        self.max_attempts = s.retry_max_attempts
        self.base_delay = s.retry_base_delay
        self.max_delay = s.retry_max_delay

    @staticmethod
    def _retry_after(exc: Exception) -> float:
        """Honor a provider's Retry-After instead of hammering a 429."""
        if isinstance(exc, httpx.HTTPStatusError):
            raw = exc.response.headers.get("Retry-After", "")
            try:
                return max(0.0, float(raw))
            except ValueError:
                pass
        return 0.0

    @staticmethod
    def _mark_retry_count(func, attempt: int) -> None:
        # Bound provider methods expose the instance; the handler reads this
        # to fill audit_logs.retry_count without threading a new return type.
        owner = getattr(func, "__self__", None)
        if owner is not None:
            with contextlib.suppress(Exception):
                owner._retry_count = attempt

    async def execute(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        labels: tuple[str, str] | None = None,
        **kwargs: Any,
    ) -> T:
        """labels=(provider, model) enables the forge_retries_total metric."""
        last_exc: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                result = await func(*args, **kwargs)
                self._mark_retry_count(func, attempt)
                return result
            except Exception as exc:
                last_exc = exc
                self._mark_retry_count(func, attempt + 1)
                if not _is_retryable(exc) or attempt == self.max_attempts - 1:
                    raise
                if labels:
                    metrics_collector.record_retry(*labels)
                delay = self.base_delay * (2 ** attempt)
                delay = max(delay, self._retry_after(exc))
                delay = min(delay, self.max_delay)
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
        raise last_exc  # type: ignore[misc]
