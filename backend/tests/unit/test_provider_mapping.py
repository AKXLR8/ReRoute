"""Tests for provider message-shape edge cases."""

import pytest

from reroute.providers.anthropic_provider import AnthropicProvider
from reroute.providers.gemini_provider import GeminiProvider
from reroute.schemas.chat import ChatMessage


def _msg(role, content="hi"):
    return ChatMessage(role=role, content=content)


def test_anthropic_merges_consecutive_same_role():
    p = AnthropicProvider(api_key="test")
    system, messages = p._extract_system([_msg("user", "a"), _msg("user", "b")])
    assert system is None
    assert messages == [{"role": "user", "content": "a\n\nb"}]


def test_anthropic_concatenates_system_prompts():
    p = AnthropicProvider(api_key="test")
    system, messages = p._extract_system(
        [_msg("system", "s1"), _msg("system", "s2"), _msg("user", "hi")]
    )
    assert system == "s1\n\ns2"
    assert len(messages) == 1


def test_anthropic_rejects_system_only():
    p = AnthropicProvider(api_key="test")
    with pytest.raises(ValueError):
        p._extract_system([_msg("system", "s1")])


def test_gemini_rejects_empty_contents():
    p = GeminiProvider(api_key="test")
    with pytest.raises(ValueError):
        p._convert_messages([_msg("system", "s1")])


def test_gemini_maps_roles():
    p = GeminiProvider(api_key="test")
    body = p._convert_messages([_msg("system", "s"), _msg("user", "u"), _msg("assistant", "a")])
    assert body["system_instruction"] == {"parts": [{"text": "s"}]}
    assert [c["role"] for c in body["contents"]] == ["user", "model"]
