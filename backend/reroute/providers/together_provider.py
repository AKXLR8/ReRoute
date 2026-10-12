"""Together AI provider — OpenAI-compatible chat API (namespaced model IDs)."""

from __future__ import annotations

from .openai_provider import OpenAIProvider

_TOGETHER_MODELS = {"openai/gpt-oss-120b"}

# USD per 1M tokens (https://www.together.ai/pricing)
_TOGETHER_PRICING: dict[str, tuple[float, float]] = {
    "openai/gpt-oss-120b": (0.15, 0.60),
}


class TogetherProvider(OpenAIProvider):
    """Same wire format as OpenAI, different host. Inherits chat/stream/health."""

    name = "together"

    def __init__(self, api_key: str = "", base_url: str = "https://api.together.ai/v1") -> None:
        super().__init__(api_key=api_key, base_url=base_url)

    def models(self) -> list[str]:
        return sorted(_TOGETHER_MODELS)

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = "") -> float:
        prices = _TOGETHER_PRICING.get(model, (0.15, 0.60))
        return (input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000
