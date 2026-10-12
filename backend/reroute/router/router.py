"""Intelligent router — picks the best provider for a given model."""

from __future__ import annotations

import logging

from opentelemetry import trace

from ..circuit_breaker.circuit_breaker import CircuitBreakerRegistry, CircuitOpenError
from ..providers.base import Provider, ProviderRegistry
from ..retry.retry import RetryEngine
from ..schemas.chat import ChatRequest, ChatResponse

log = logging.getLogger(__name__)
tracer = trace.get_tracer("rerouteai.router")


class Router:
    """Stateless — all state lives in provider.health and circuit_breakers."""

    def __init__(
        self,
        registry: ProviderRegistry,
        circuit_breakers: CircuitBreakerRegistry,
        retry_engine: RetryEngine,
    ) -> None:
        self.registry = registry
        self.circuit_breakers = circuit_breakers
        self.retry = retry_engine

    async def _candidates(
        self, model: str, providers: list[Provider], preferred: str | None = None
    ) -> list[Provider]:
        """Filter the caller's (per-user) providers by model support, explicit
        preference, circuit breaker. `providers` is already BYOK-resolved —
        the router never sees keys it wasn't handed."""
        candidates = [p for p in providers if p.supports_model(model) and p.health.available]
        if preferred:
            candidates = [p for p in candidates if p.name == preferred]
        # Filter out providers with open circuits
        filtered = []
        for p in candidates:
            cb = self.circuit_breakers.get(p.name)
            if await cb.is_available:
                filtered.append(p)
        return sorted(filtered, key=lambda p: p.health.latency_ms)

    async def route(
        self, request: ChatRequest, providers: list[Provider]
    ) -> tuple[Provider, ChatResponse, str | None]:
        """Return (provider, response, fallback_from_provider_name_or_None).

        Calls the provider itself (retry + circuit breaker applied) — the caller
        must use the returned response rather than calling again.

        Tries each candidate in order (sorted by latency). Returns the first
        that succeeds. Raises the last exception if all fail.
        """
        candidates = await self._candidates(request.model, providers, request.provider)
        if not candidates:
            raise ValueError(
                f"No available provider for model '{request.model}' — "
                "connect a provider API key in Settings or pick another model"
            )

        last_exc: Exception | None = None
        fallback_from: str | None = None

        for provider in candidates:
            try:
                async with self.circuit_breakers.get(provider.name):
                    with tracer.start_as_current_span("llm.chat") as span:
                        span.set_attribute("gen_ai.operation.name", "chat")
                        span.set_attribute("gen_ai.provider.name", provider.name)
                        span.set_attribute("gen_ai.request.model", request.model)
                        if fallback_from:
                            span.set_attribute("reroute.fallback_from", fallback_from)
                        response = await self.retry.execute(
                            provider.chat, request, labels=(provider.name, request.model)
                        )
                        span.set_attribute("gen_ai.response.model", response.model)
                        if response.usage:
                            span.set_attribute(
                                "gen_ai.usage.input_tokens", response.usage.prompt_tokens
                            )
                            span.set_attribute(
                                "gen_ai.usage.output_tokens", response.usage.completion_tokens
                            )
                    return provider, response, fallback_from
            except (CircuitOpenError, ValueError):
                continue
            except Exception as exc:
                last_exc = exc
                fallback_from = provider.name
                log.warning(
                    "Provider %s failed for model %s: %s — trying next",
                    provider.name,
                    request.model,
                    exc,
                )
                continue

        raise last_exc or ValueError("All providers failed")

    async def route_stream(
        self, request: ChatRequest, providers: list[Provider]
    ) -> tuple[Provider, str | None]:
        """Same as route() but for streaming — skips retry (streaming retry is complex).
        Does still apply circuit-breaker health via candidates ordering."""
        candidates = await self._candidates(request.model, providers, request.provider)
        if not candidates:
            raise ValueError(
                f"No available provider for model '{request.model}' — "
                "connect a provider API key in Settings or pick another model"
            )

        fallback_from: str | None = None
        for provider in candidates:
            cb = self.circuit_breakers.get(provider.name)
            if not await cb.is_available:
                continue
            try:
                # Quick connectivity check via health
                if not provider.health.available:
                    continue
                return provider, fallback_from
            except Exception:
                fallback_from = provider.name
                continue

        raise ValueError("No available provider for streaming")
