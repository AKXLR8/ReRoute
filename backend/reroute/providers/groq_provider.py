"""Groq provider — OpenAI-compatible endpoint."""

from __future__ import annotations

from .openai_provider import OpenAIProvider

_GROQ_MODELS = {
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
}


class GroqProvider(OpenAIProvider):
    """Same wire format as OpenAI, different host. Inherits chat/stream/health."""

    name = "groq"

    def __init__(self, api_key: str = "", base_url: str = "https://api.groq.com/openai/v1") -> None:
        super().__init__(api_key=api_key, base_url=base_url)

    def models(self) -> list[str]:
        return sorted(_GROQ_MODELS)

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = "") -> float:
        return 0.0  # free tier; matches pre-subclass behavior (base returned 0.0)
