"""Request deduplication — coalesce identical concurrent requests."""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from ..schemas.chat import ChatRequest


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
        **kwargs,
    ) -> Any:
        """Execute func(request) — deduplicating concurrent identical calls.

        `scope` isolates tenants: identical requests from different scopes
        never share a response.
        """
        key = self._hash(scope, request)

        if key in self._in_flight:
            # Another request is already in flight — wait for it
            return await self._in_flight[key]

        # We are the first — create the future
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._in_flight[key] = future

        try:
            result = await func(request, *args, **kwargs)
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            # nobody may ever await this future — mark retrieved so GC doesn't
            # log "Future exception was never retrieved"; real waiters still get it
            future.add_done_callback(lambda f: f.exception())
            raise
        finally:
            self._in_flight.pop(key, None)
