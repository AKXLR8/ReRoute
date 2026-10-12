"""Tests for Cerebras + Together providers (no network — routing + pricing only)."""

from reroute.providers.base import ProviderRegistry
from reroute.providers.cerebras_provider import CerebrasProvider
from reroute.providers.together_provider import TogetherProvider


def test_cerebras_registers_and_routes():
    reg = ProviderRegistry()
    reg.register(CerebrasProvider(api_key="test"))
    assert [p.name for p in reg.for_model("gpt-oss-120b")] == ["cerebras"]
    assert reg.for_model("gpt-4o") == []


def test_cerebras_cost_matches_published_pricing():
    p = CerebrasProvider(api_key="test")
    assert p.estimate_cost(1_000_000, 1_000_000) == 1.1  # 0.35 + 0.75


def test_together_registers_and_routes():
    reg = ProviderRegistry()
    reg.register(TogetherProvider(api_key="test"))
    assert [p.name for p in reg.for_model("openai/gpt-oss-120b")] == ["together"]
    assert reg.for_model("gpt-4o") == []


def test_together_cost_matches_published_pricing():
    p = TogetherProvider(api_key="test")
    assert p.estimate_cost(1_000_000, 1_000_000) == 0.75  # 0.15 + 0.60
