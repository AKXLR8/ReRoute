"""Chat completion request / response schemas — OpenAI-compatible wire format."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class ChatMessage(BaseModel):
    role: str
    content: str | list[Any] | None = None
    name: str | None = None


def _text_len(content: Any) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(
            len(p["text"])
            for p in content
            if isinstance(p, dict) and isinstance(p.get("text"), str)
        )
    return 0


class ChatRequest(BaseModel):
    model: str = Field(min_length=1, max_length=128)
    messages: list[ChatMessage] = Field(min_length=1, max_length=1024)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=1_000_000)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    stream: bool = False
    stop: str | list[str] | None = None
    user: str | None = None
    # Gateway-specific extensions
    provider: str | None = None  # explicit provider preference
    cache: bool = True  # enable semantic cache

    @model_validator(mode="after")
    def _size_cap(self) -> ChatRequest:
        # ponytail: caps post-parse blast (guard/embed/audit); a proxy-level
        # client_max_body_size still needed — pydantic only sees the body
        # after it's fully read into RAM
        total = sum(_text_len(m.content) for m in self.messages)
        if total > 2_000_000:
            raise ValueError("request too large: content exceeds 2,000,000 characters")
        return self


class ChatResponse(BaseModel):
    id: str = Field(default_factory=lambda: "chatcmpl-gw")
    object: str = "chat.completion"
    created: int = 0
    model: str
    choices: list[Choice]
    usage: Usage | None = None
    # Gateway metadata
    provider: str = ""
    latency_ms: float = 0
    cached: bool = False
    trace_id: str | None = None


class Choice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: str | None = "stop"


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class StreamingChunk(BaseModel):
    id: str = ""
    object: str = "chat.completion.chunk"
    created: int = 0
    model: str = ""
    choices: list[StreamingChoice]
    # Provider-reported usage, attached to whichever chunk carries it
    # (final chunk for OpenAI/Gemini, message_stop for Anthropic, done for Ollama)
    usage: Usage | None = None


class StreamingChoice(BaseModel):
    index: int = 0
    delta: dict[str, Any] = Field(default_factory=dict)
    finish_reason: str | None = None
