"""Retry engine — exponential backoff with jitter for transient failures."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

import httpx

from ..config import get_settings
from ..observability.metrics import metrics_collector

T = TypeVar("T")

# Only retry on these conditions
_RETRYABLE_STATUS = {429, 503, 502, 504}


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
                return await func(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if not _is_retryable(exc) or attempt == self.max_attempts - 1:
                    raise
                if labels:
                    metrics_collector.record_retry(*labels)
                delay = self.base_delay * (2 ** attempt)
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
        raise last_exc  # type: ignore[misc]
