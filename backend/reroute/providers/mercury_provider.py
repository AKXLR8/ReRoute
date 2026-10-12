"""Mercury provider (Inception Labs) — OpenAI-compatible chat API."""

from __future__ import annotations

from .openai_provider import OpenAIProvider

_MERCURY_MODELS = {"mercury-2"}

# USD per 1M tokens (https://docs.inceptionlabs.ai/get-started/models)
_MERCURY_PRICING: dict[str, tuple[float, float]] = {
    "mercury-2": (0.25, 0.75),
}


class MercuryProvider(OpenAIProvider):
    """Same wire format as OpenAI, different host. Inherits chat/stream/health."""

    name = "mercury"

    def __init__(
        self, api_key: str = "", base_url: str = "https://api.inceptionlabs.ai/v1"
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url)

    def models(self) -> list[str]:
        return sorted(_MERCURY_MODELS)

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = "") -> float:
        prices = _MERCURY_PRICING.get(model, (0.25, 0.75))
        return (input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000
