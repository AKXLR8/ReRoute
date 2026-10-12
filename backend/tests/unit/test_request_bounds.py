"""Tests for ChatRequest input validation bounds."""

import pytest
from pydantic import ValidationError

from reroute.schemas.chat import ChatMessage, ChatRequest


def _req(**kwargs):
    base = {"model": "m", "messages": [ChatMessage(role="user", content="hi")]}
    base.update(kwargs)
    return ChatRequest(**base)


def test_valid_request_passes():
    assert _req(temperature=0.7, max_tokens=100).model == "m"


def test_empty_messages_rejected():
    with pytest.raises(ValidationError):
        _req(messages=[])


def test_temperature_out_of_range_rejected():
    with pytest.raises(ValidationError):
        _req(temperature=5.0)
    with pytest.raises(ValidationError):
        _req(temperature=-0.5)


def test_max_tokens_must_be_positive():
    with pytest.raises(ValidationError):
        _req(max_tokens=0)


def test_max_tokens_upper_bound():
    with pytest.raises(ValidationError):
        _req(max_tokens=2_000_000)


def test_empty_model_rejected():
    with pytest.raises(ValidationError):
        _req(model="")


def test_model_length_bounded():
    with pytest.raises(ValidationError):
        _req(model="x" * 129)


def test_message_count_bounded():
    with pytest.raises(ValidationError):
        _req(messages=[ChatMessage(role="user", content="hi")] * 1025)


def test_top_p_bounded():
    with pytest.raises(ValidationError):
        _req(top_p=1.5)
    with pytest.raises(ValidationError):
        _req(top_p=-0.1)


def test_total_content_size_capped():
    with pytest.raises(ValidationError):
        _req(messages=[ChatMessage(role="user", content="x" * 2_000_001)])


def test_list_content_counts_toward_cap():
    big = [{"type": "text", "text": "x" * 1_500_000} for _ in range(2)]
    with pytest.raises(ValidationError):
        _req(messages=[ChatMessage(role="user", content=big)])
