"""Ollama provider — local inference, no API key required."""

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

_OLLAMA_MODELS = {"llama3.1", "llama3.2", "mistral", "codellama", "phi3", "gemma2", "qwen2.5"}


class OllamaProvider(Provider):
    name = "ollama"

    def __init__(self, api_key: str = "", base_url: str = "http://localhost:11434") -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        self._client: httpx.AsyncClient | None = None
        self._tags: list[str] = []
        self._tags_at: float = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(120.0, connect=5.0),
            )
        return self._client

    async def _resolve_model(self, model: str) -> str:
        """Map friendly names (llama3.1) to installed tags (llama3.1:8b)."""
        now = time.monotonic()
        if now - self._tags_at > 60:
            try:
                client = await self._get_client()
                resp = await client.get("/api/tags")
                if resp.status_code == 200:
                    self._tags = [m.get("name", "") for m in resp.json().get("models", [])]
                    self._tags_at = now
            except Exception:
                pass
        if model in self._tags:
            return model
        if f"{model}:latest" in self._tags:
            return f"{model}:latest"
        prefixed = [t for t in self._tags if t.startswith(f"{model}:")]
        if len(prefixed) == 1:
            return prefixed[0]
        return model

    async def chat(self, request: ChatRequest) -> ChatResponse:
        client = await self._get_client()
        body: dict = {
            "model": await self._resolve_model(request.model),
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": False,
        }
        if request.temperature is not None:
            body["options"] = {"temperature": request.temperature}
        if request.max_tokens is not None:
            body.setdefault("options", {})["num_predict"] = request.max_tokens

        t0 = time.monotonic()
        resp = await client.post("/api/chat", json=body)
        latency = (time.monotonic() - t0) * 1000
        resp.raise_for_status()
        data = resp.json()

        self.health.latency_ms = latency
        self.health.successes += 1

        msg = data.get("message", {})
        prompt_eval = data.get("prompt_eval_count", 0)
        eval_count = data.get("eval_count", 0)
        return ChatResponse(
            id="ollama-" + str(int(time.time())),
            model=data.get("model", request.model),
            choices=[Choice(message=ChatMessage(role="assistant", content=msg.get("content", "")))],
            usage=Usage(
                prompt_tokens=prompt_eval,
                completion_tokens=eval_count,
                total_tokens=prompt_eval + eval_count,
            ),
            provider=self.name,
            latency_ms=latency,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamingChunk]:
        client = await self._get_client()
        body = {
            "model": await self._resolve_model(request.model),
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": True,
        }
        async with client.stream("POST", "/api/chat", json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                data = json.loads(line)
                content = data.get("message", {}).get("content", "")
                done = data.get("done", False)
                if done:
                    # final payload carries the real token counts
                    prompt_eval = data.get("prompt_eval_count", 0)
                    eval_count = data.get("eval_count", 0)
                    yield StreamingChunk(
                        model=data.get("model", request.model),
                        choices=[StreamingChoice(finish_reason="stop", delta={})],
                        usage=Usage(
                            prompt_tokens=prompt_eval,
                            completion_tokens=eval_count,
                            total_tokens=prompt_eval + eval_count,
                        )
                        if (prompt_eval or eval_count)
                        else None,
                    )
                    break
                if content:
                    yield StreamingChunk(
                        model=data.get("model", request.model),
                        choices=[StreamingChoice(delta={"content": content})],
                    )

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get("/api/tags")
            ok = resp.status_code == 200
            self.health.available = ok
            return ok
        except Exception:
            self.health.available = False
            self.health.failures += 1
            return False

    def models(self) -> list[str]:
        return sorted(_OLLAMA_MODELS)

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = "") -> float:
        return 0.0  # local, no cost
