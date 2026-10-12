"""Tests for explicit provider preference routing."""

from unittest.mock import MagicMock

import pytest

from reroute.providers.base import Provider, ProviderRegistry
from reroute.router.router import Router


class StubProvider(Provider):
    def __init__(self, name, models):
        super().__init__()
        self.name = name
        self._models = models

    async def chat(self, request):
        raise NotImplementedError

    async def stream(self, request):
        raise NotImplementedError

    async def health_check(self):
        return True

    def models(self):
        return self._models


def _router():
    breakers = MagicMock()
    # Mock circuit breaker with async is_available property
    class MockCB:
        @property
        async def is_available(self):
            return True
    breakers.get.return_value = MockCB()
    return Router(ProviderRegistry(), breakers, MagicMock())


@pytest.mark.asyncio
async def test_preferred_provider_wins():
    router = _router()
    providers = [StubProvider("a", ["m"]), StubProvider("b", ["m"])]
    result = await router._candidates("m", providers, "b")
    assert [p.name for p in result] == ["b"]


@pytest.mark.asyncio
async def test_unknown_preference_yields_no_candidates():
    router = _router()
    result = await router._candidates("m", [StubProvider("a", ["m"])], "zzz")
    assert result == []


@pytest.mark.asyncio
async def test_no_preference_keeps_all_candidates():
    router = _router()
    providers = [StubProvider("a", ["m"]), StubProvider("b", ["m"])]
    result = await router._candidates("m", providers)
    assert len(result) == 2