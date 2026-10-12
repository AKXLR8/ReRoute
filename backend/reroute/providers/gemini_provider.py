"""Google Gemini provider."""

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

_GEMINI_MODELS = {"gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash"}

# USD per 1M tokens
_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
}


class GeminiProvider(Provider):
    name = "gemini"

    def __init__(
        self, api_key: str = "", base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # Key goes in a header, never the URL — query strings leak into
            # httpx logs, audit rows, and APM traces
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(60.0, connect=10.0),
                headers={"x-goog-api-key": self.api_key},
            )
        return self._client

    def _convert_messages(self, messages: list[ChatMessage]) -> dict:
        contents = []
        system_instruction = None
        for m in messages:
            if m.role == "system":
                system_instruction = {"parts": [{"text": m.content or ""}]}
            else:
                role = "user" if m.role == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m.content or ""}]})
        if not contents:
            raise ValueError("Gemini requires at least one user/assistant message")
        result: dict = {"contents": contents}
        if system_instruction:
            result["system_instruction"] = system_instruction
        return result

    async def chat(self, request: ChatRequest) -> ChatResponse:
        client = await self._get_client()
        msg_body = self._convert_messages(request.messages)
        body = {
            **msg_body,
            "generationConfig": {},
        }
        if request.temperature is not None:
            body["generationConfig"]["temperature"] = request.temperature
        if request.max_tokens is not None:
            body["generationConfig"]["maxOutputTokens"] = request.max_tokens

        t0 = time.monotonic()
        resp = await client.post(
            f"/models/{request.model}:generateContent",
            json=body,
        )
        latency = (time.monotonic() - t0) * 1000
        resp.raise_for_status()
        data = resp.json()

        self.health.latency_ms = latency
        self.health.successes += 1
        self.health.last_check = time.time()

        text = ""
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                text += part.get("text", "")

        usage_data = data.get("usageMetadata", {})
        return ChatResponse(
            id="gemini-" + str(int(time.time())),
            created=int(time.time()),
            model=request.model,
            choices=[Choice(message=ChatMessage(role="assistant", content=text))],
            usage=Usage(
                prompt_tokens=usage_data.get("promptTokenCount", 0),
                completion_tokens=usage_data.get("candidatesTokenCount", 0),
                total_tokens=usage_data.get("totalTokenCount", 0),
            ),
            provider=self.name,
            latency_ms=latency,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamingChunk]:
        client = await self._get_client()
        msg_body = self._convert_messages(request.messages)
        body = {**msg_body, "generationConfig": {}}

        async with client.stream(
            "POST",
            f"/models/{request.model}:streamGenerateContent?alt=sse",
            json=body,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = json.loads(line[6:])
                usage = None
                if (u := data.get("usageMetadata")) is not None:
                    usage = Usage(
                        prompt_tokens=u.get("promptTokenCount", 0),
                        completion_tokens=u.get("candidatesTokenCount", 0),
                        total_tokens=u.get("totalTokenCount", 0),
                    )
                yielded = False
                for candidate in data.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        text = part.get("text", "")
                        if text:
                            yielded = True
                            yield StreamingChunk(
                                model=request.model,
                                choices=[StreamingChoice(delta={"content": text})],
                                usage=usage,
                            )
                if not yielded and usage is not None:
                    # final chunk can carry usageMetadata with no content
                    yield StreamingChunk(model=request.model, choices=[], usage=usage)

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
        return sorted(_GEMINI_MODELS)

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = "") -> float:
        prices = _PRICING.get(model, _PRICING["gemini-2.0-flash"])
        return (input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000
