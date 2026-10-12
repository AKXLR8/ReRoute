"""Abstract provider interface.

Every LLM backend implements this. The rest of the gateway never imports
provider-specific code — only this ABC.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from ..schemas.chat import ChatRequest, ChatResponse, StreamingChunk

log = logging.getLogger(__name__)


class ProviderHealth:
    __slots__ = ("latency_ms", "available", "last_check", "successes", "failures")

    def __init__(self) -> None:
        self.latency_ms: float = 0.0
        self.available: bool = True
        self.last_check: float = 0.0
        self.successes: int = 0
        self.failures: int = 0

    @property
    def success_rate(self) -> float:
        total = self.successes + self.failures
        return self.successes / total if total else 1.0


class Provider(ABC):
    """Base class for all LLM providers."""

    name: str = "base"

    def __init__(self, api_key: str = "", base_url: str = "") -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.health = ProviderHealth()

    async def aclose(self) -> None:
        """Close the httpx client, if one was created. Called on shutdown."""
        client = getattr(self, "_client", None)
        if client is not None and not client.is_closed:
            await client.aclose()

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        ...

    @abstractmethod
    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamingChunk]:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...

    @abstractmethod
    def models(self) -> list[str]:
        ...

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = "") -> float:
        """Return estimated USD cost for the *requested* model. Unknown models
        fall back to each provider's default price."""
        return 0.0

    def supports_model(self, model: str) -> bool:
        return model in self.models()

    async def __aenter__(self) -> Provider:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()


class ProviderRegistry:
    """Central registry — providers register themselves, router picks by name.

    Per-user BYOK: the registry holds only shared templates; live traffic runs
    on per-user clones built in byok.resolve_user().
    """

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, provider: Provider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> Provider | None:
        return self._providers.get(name)

    def all(self) -> dict[str, Provider]:
        return dict(self._providers)

    def available(self) -> dict[str, Provider]:
        return {k: v for k, v in self._providers.items() if v.health.available}

    async def aclose_all(self) -> None:
        """Close shared instances (per-user clones close with their requests)."""
        for p in self._providers.values():
            await p.aclose()

    def for_model(self, model: str) -> list[Provider]:
        """Shared providers supporting `model`, ordered by health."""
        return sorted(
            (p for p in self._providers.values() if p.supports_model(model) and p.health.available),
            key=lambda p: p.health.latency_ms,
        )
