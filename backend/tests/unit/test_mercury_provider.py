"""Tests for the Mercury provider (no network — routing + pricing only)."""

from reroute.providers.base import ProviderRegistry
from reroute.providers.mercury_provider import MercuryProvider


def test_mercury_registers_and_routes():
    reg = ProviderRegistry()
    reg.register(MercuryProvider(api_key="test"))
    assert [p.name for p in reg.for_model("mercury-2")] == ["mercury"]
    assert reg.for_model("gpt-4o") == []


def test_mercury_cost_matches_published_pricing():
    p = MercuryProvider(api_key="test")
    assert p.estimate_cost(1_000_000, 1_000_000) == 1.0  # 0.25 + 0.75
    assert p.estimate_cost(0, 0) == 0.0
