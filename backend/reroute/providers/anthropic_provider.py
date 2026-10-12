"""Anthropic (Claude) provider."""

from __future__ import annotations

import json
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

_ANTHROPIC_MODELS = {
    "claude-sonnet-4-20250514",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-3-haiku-20240307",
}

_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-3-opus-20240229": (15.00, 75.00),
    "claude-3-haiku-20240307": (0.25, 1.25),
}


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, api_key: str = "", base_url: str = "https://api.anthropic.com/v1") -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client

    def _extract_system(self, messages: list[ChatMessage]) -> tuple[str | None, list[dict]]:
        systems = []
        out: list[dict] = []
        for m in messages:
            text = m.content if isinstance(m.content, str) else str(m.content or "")
            if m.role == "system":
                systems.append(text)
            elif out and out[-1]["role"] == m.role:
                # Anthropic rejects consecutive same-role messages — merge them
                out[-1]["content"] += "\n\n" + text
            else:
                out.append({"role": m.role, "content": text})
        if not out:
            raise ValueError("Anthropic requires at least one user/assistant message")
        return ("\n\n".join(systems) or None), out

    async def chat(self, request: ChatRequest) -> ChatResponse:
        client = await self._get_client()
        system_prompt, messages = self._extract_system(request.messages)
        body: dict = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
        }
        if system_prompt:
            body["system"] = system_prompt
        if request.temperature is not None:
            body["temperature"] = request.temperature

        t0 = time.monotonic()
        resp = await client.post("/messages", json=body)
        latency = (time.monotonic() - t0) * 1000
        resp.raise_for_status()
        data = resp.json()

        self.health.latency_ms = latency
        self.health.successes += 1
        self.health.last_check = time.time()

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")

        usage_data = data.get("usage", {})
        return ChatResponse(
            id=data.get("id", ""),
            created=int(time.time()),
            model=data.get("model", request.model),
            choices=[Choice(message=ChatMessage(role="assistant", content=text))],
            usage=Usage(
                prompt_tokens=usage_data.get("input_tokens", 0),
                completion_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
            ),
            provider=self.name,
            latency_ms=latency,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamingChunk]:
        client = await self._get_client()
        system_prompt, messages = self._extract_system(request.messages)
        body: dict = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 4096,
            "stream": True,
        }
        if system_prompt:
            body["system"] = system_prompt

        # Usage arrives split across events: input tokens on message_start,
        # cumulative output tokens on message_delta (Anthropic streaming docs)
        usage = Usage()
        async with client.stream("POST", "/messages", json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = json.loads(line[6:])
                event_type = data.get("type", "")
                if event_type == "message_start":
                    u = data.get("message", {}).get("usage", {})
                    usage.prompt_tokens = u.get("input_tokens", 0)
                    usage.completion_tokens = u.get("output_tokens", 0)
                    usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
                elif event_type == "message_delta":
                    u = data.get("usage", {})
                    usage.completion_tokens = u.get(
                        "output_tokens", usage.completion_tokens
                    )
                    usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
                elif event_type == "content_block_delta":
                    text = data.get("delta", {}).get("text", "")
                    if text:
                        yield StreamingChunk(
                            id=data.get("message_id", ""),
                            model=request.model,
                            choices=[StreamingChoice(delta={"content": text})],
                        )
                elif event_type == "message_stop":
                    yield StreamingChunk(
                        model=request.model,
                        choices=[StreamingChoice(finish_reason="stop", delta={})],
                        usage=usage if usage.total_tokens else None,
                    )
                    break

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            # GET /v1/models validates the key for free — health checks run every
            # 30s, never spend tokens on them
            resp = await client.get("/models", params={"limit": 1})
            if resp.status_code in (404, 405):
                # legacy proxy without /models: fall back to a 1-token call
                resp = await client.post(
                    "/messages",
                    json={
                        "model": "claude-3-haiku-20240307",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )
            ok = resp.status_code == 200
            self.health.available = ok
            self.health.last_check = time.time()
            return ok
        except Exception:
            self.health.available = False
            self.health.failures += 1
            return False

    def models(self) -> list[str]:
        return sorted(_ANTHROPIC_MODELS)

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = "") -> float:
        prices = _PRICING.get(model, (3.00, 15.00))
        return (input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000
