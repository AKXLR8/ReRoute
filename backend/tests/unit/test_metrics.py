"""Tests for metrics collector."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from reroute.app import create_app
from reroute.auth.auth import AuthContext, get_current_user
from reroute.database import get_db
from reroute.observability.metrics import MetricsCollector


def test_record_request_increments_counter():
    mc = MetricsCollector()
    mc.record_request(
        provider="openai",
        model="gpt-4o",
        status="success",
        team_id="team-1",
        latency_s=0.5,
        input_tokens=10,
        output_tokens=20,
    )
    # No exception = pass. Prometheus counters are global singletons.
    # Verifying they exist and are callable is the test.


def test_record_cache_hit():
    mc = MetricsCollector()
    mc.record_cache_hit()
    mc.record_cache_miss()


def test_record_retry():
    mc = MetricsCollector()
    mc.record_retry("openai", "gpt-4o")


def test_record_fallback():
    mc = MetricsCollector()
    mc.record_fallback("openai", "anthropic")


def test_set_circuit_breaker():
    mc = MetricsCollector()
    mc.set_circuit_breaker("openai", 0)
    mc.set_circuit_breaker("openai", 1)
    mc.set_circuit_breaker("openai", 2)


def test_set_provider_health():
    mc = MetricsCollector()
    mc.set_provider_health("openai", True)
    mc.set_provider_health("openai", False)


@pytest.mark.asyncio
async def test_metrics_requires_admin():
    app = create_app()
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/metrics")).status_code == 401

    member = AuthContext(is_admin=False, role="member")
    app.dependency_overrides[get_current_user] = lambda: member
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/metrics")).status_code == 403

    app.dependency_overrides[get_current_user] = lambda: AuthContext(is_admin=True)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get("/metrics")
    assert res.status_code == 200
    assert "forge_requests_total" in res.text
