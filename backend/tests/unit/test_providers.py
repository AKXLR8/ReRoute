"""Tests for provider base classes."""

from reroute.providers.base import Provider, ProviderHealth, ProviderRegistry


class DummyProvider(Provider):
    name = "dummy"

    def __init__(self):
        super().__init__(api_key="test")

    async def chat(self, request):
        raise NotImplementedError

    async def stream(self, request):
        raise NotImplementedError

    async def health_check(self):
        self.health.available = True
        self.health.last_check = 1.0
        return True

    def models(self):
        return ["model-a", "model-b"]


def test_provider_health_defaults():
    h = ProviderHealth()
    assert h.latency_ms == 0.0
    assert h.available is True
    assert h.success_rate == 1.0


def test_provider_health_success_rate():
    h = ProviderHealth()
    h.successes = 8
    h.failures = 2
    assert h.success_rate == 0.8


def test_provider_health_zero_total():
    h = ProviderHealth()
    assert h.success_rate == 1.0


def test_registry_register_and_get():
    reg = ProviderRegistry()
    p = DummyProvider()
    reg.register(p)
    assert reg.get("dummy") is p
    assert reg.get("nonexistent") is None


def test_registry_all():
    reg = ProviderRegistry()
    reg.register(DummyProvider())
    assert "dummy" in reg.all()


def test_registry_available_filters_unhealthy():
    reg = ProviderRegistry()
    p = DummyProvider()
    p.health.available = False
    reg.register(p)
    assert len(reg.available()) == 0
    p.health.available = True
    assert len(reg.available()) == 1


def test_registry_for_model():
    reg = ProviderRegistry()
    p = DummyProvider()
    reg.register(p)
    result = reg.for_model("model-a")
    assert len(result) == 1
    assert result[0].name == "dummy"

    result = reg.for_model("model-c")
    assert len(result) == 0


def test_provider_supports_model():
    p = DummyProvider()
    assert p.supports_model("model-a") is True
    assert p.supports_model("model-c") is False
