"""Request deduplication — coalesce identical concurrent requests."""

from __future__ import annotations

import asyncio
import contextlib
import copy
import hashlib
import json
from typing import Any

from ..schemas.chat import ChatRequest


class _LeaderCancelled(Exception):
    """The in-flight leader vanished — a waiter should try again."""


class RequestDeduplicator:
    """If N identical requests arrive simultaneously, only one hits the provider.

    The others wait and share the response. Uses asyncio futures keyed by
    scope (tenant) + content hash — never coalesce across teams, and never
    across differing sampling params.
    """

    def __init__(self) -> None:
        self._in_flight: dict[str, asyncio.Future] = {}

    def _hash(self, scope: str, request: ChatRequest) -> str:
        raw = json.dumps(
            {
                "scope": scope,
                "params": request.model_dump(exclude={"messages"}),
                "messages": [m.model_dump() for m in request.messages],
            },
            sort_keys=True,
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def execute(
        self,
        scope: str,
        request: ChatRequest,
        func,
        *args,
        on_coalesced=None,
        **kwargs,
    ) -> Any:
        """Execute func(request) — deduplicating concurrent identical calls.

        `scope` isolates tenants: identical requests from different scopes
        never share a response. `on_coalesced(result)` runs for waiters so they
        still get their own audit/metrics row.
        """
        key = self._hash(scope, request)

        if key in self._in_flight:
            # Another request is already in flight — wait for it
            try:
                result = await self._in_flight[key]
            except _LeaderCancelled:
                # The leader was cancelled (client disconnect). Become the
                # leader instead of hanging forever on a future nobody fills.
                return await self.execute(
                    scope, request, func, *args, on_coalesced=on_coalesced, **kwargs
                )
            with contextlib.suppress(Exception):
                result = copy.deepcopy(result)
            if on_coalesced is not None:
                await on_coalesced(result)
            return result

        # We are the first — create the future
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._in_flight[key] = future

        try:
            result = await func(request, *args, **kwargs)
            if not future.done():
                future.set_result(result)
            return result
        except BaseException as exc:
            if not future.done():
                # CancelledError is BaseException and must not be set on the
                # future (it would look like every waiter was cancelled).
                future.set_exception(
                    _LeaderCancelled() if isinstance(exc, asyncio.CancelledError) else exc
                )
                future.add_done_callback(
                    lambda f: None if f.cancelled() else f.exception()
                )
            raise
        finally:
            self._in_flight.pop(key, None)
