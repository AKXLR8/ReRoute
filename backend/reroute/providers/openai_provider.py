"""OpenAI provider — chat, streaming, and cost estimation."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import httpx

from ..schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    Choice,
    StreamingChoice,
    StreamingChunk,
    Usage,
)
from .base import Provider

_OPENAI_MODELS = {
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
    "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
    "o1", "o1-mini", "o1-pro", "o3-mini",
}

# USD per 1M tokens
_PRICING: dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o3-mini": (1.10, 4.40),
}


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self, api_key: str = "", base_url: str = "https://api.openai.com/v1") -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client

    def _to_openai_messages(self, messages: list[ChatMessage]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    async def chat(self, request: ChatRequest) -> ChatResponse:
        client = await self._get_client()
        body: dict = {
            "model": request.model,
            "messages": self._to_openai_messages(request.messages),
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens

        t0 = time.monotonic()
        resp = await client.post("/chat/completions", json=body)
        latency = (time.monotonic() - t0) * 1000

        resp.raise_for_status()
        data = resp.json()

        self.health.latency_ms = latency
        self.health.successes += 1
        self.health.last_check = time.time()

        usage_data = data.get("usage", {})
        return ChatResponse(
            id=data.get("id", ""),
            created=data.get("created", 0),
            model=data.get("model", request.model),
            choices=[
                Choice(
                    index=c.get("index", 0),
                    message=ChatMessage(**c["message"]),
                    finish_reason=c.get("finish_reason"),
                )
                for c in data.get("choices", [])
            ],
            usage=Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            ),
            provider=self.name,
            latency_ms=latency,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamingChunk]:
        client = await self._get_client()
        body: dict = {
            "model": request.model,
            "messages": self._to_openai_messages(request.messages),
            "stream": True,
            # Provider-reported usage on the final chunk — the only accurate
            # token count for streams (per OpenAI + OTel GenAI guidance)
            "stream_options": {"include_usage": True},
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens

        async with client.stream("POST", "/chat/completions", json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    break
                import json
                chunk = json.loads(payload)
                choices = []
                for c in chunk.get("choices", []):
                    choices.append(
                        StreamingChoice(
                            index=c.get("index", 0),
                            delta=c.get("delta", {}),
                            finish_reason=c.get("finish_reason"),
                        )
                    )
                usage_data = chunk.get("usage")
                yield StreamingChunk(
                    id=chunk.get("id", ""),
                    created=chunk.get("created", 0),
                    model=chunk.get("model", request.model),
                    choices=choices,
                    usage=Usage(
                        prompt_tokens=usage_data.get("prompt_tokens", 0),
                        completion_tokens=usage_data.get("completion_tokens", 0),
                        total_tokens=usage_data.get("total_tokens", 0),
                    )
                    if usage_data
                    else None,
                )

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get("/models")
            ok = resp.status_code == 200
            self.health.available = ok
            self.health.last_check = time.time()
            return ok
        except Exception:
            self.health.available = False
            self.health.failures += 1
            return False

    def models(self) -> list[str]:
        return sorted(_OPENAI_MODELS)

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = "") -> float:
        prices = _PRICING.get(model, _PRICING["gpt-4o"])
        return (input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000
