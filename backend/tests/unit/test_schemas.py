"""Tests for Pydantic schemas."""

from reroute.schemas.chat import ChatMessage, ChatRequest, ChatResponse, Choice, Usage


def test_chat_request_defaults():
    req = ChatRequest(model="gpt-4o", messages=[ChatMessage(role="user", content="hi")])
    assert req.stream is False
    assert req.cache is True
    assert req.provider is None


def test_chat_response():
    resp = ChatResponse(
        model="gpt-4o",
        choices=[Choice(message=ChatMessage(role="assistant", content="hello"))],
        usage=Usage(prompt_tokens=5, completion_tokens=1, total_tokens=6),
        provider="openai",
        latency_ms=123.4,
    )
    assert resp.object == "chat.completion"
    assert resp.choices[0].message.content == "hello"
