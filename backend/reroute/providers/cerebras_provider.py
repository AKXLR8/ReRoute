"""Cerebras provider — OpenAI-compatible chat API."""

from __future__ import annotations

from .openai_provider import OpenAIProvider

_CEREBRAS_MODELS = {"gpt-oss-120b"}

# USD per 1M tokens (https://inference-docs.cerebras.ai/models/openai-oss)
_CEREBRAS_PRICING: dict[str, tuple[float, float]] = {
    "gpt-oss-120b": (0.35, 0.75),
}


class CerebrasProvider(OpenAIProvider):
    """Same wire format as OpenAI, different host. Inherits chat/stream/health."""

    name = "cerebras"

    def __init__(self, api_key: str = "", base_url: str = "https://api.cerebras.ai/v1") -> None:
        super().__init__(api_key=api_key, base_url=base_url)

    def models(self) -> list[str]:
        return sorted(_CEREBRAS_MODELS)

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = "") -> float:
        prices = _CEREBRAS_PRICING.get(model, (0.35, 0.75))
        return (input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000
