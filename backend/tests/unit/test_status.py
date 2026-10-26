"""Tests for the public /status feed (no auth, aggregate info only)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from reroute import app as app_module
from reroute.app import create_app
from reroute.database import get_db


def _client(db) -> tuple:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return app, AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_status_is_public_and_leaks_no_secrets():
    app_module._status_cache.clear()
    app, client = _client(AsyncMock())

    async with client:
        resp = await client.get("/status")

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"service", "checks", "providers", "generated_at"}
    assert body["checks"]["database"] == "ok"
    assert body["providers"] == []  # lifespan does not run under ASGITransport

    text = resp.text.lower()
    for leak in ("api_key", "authorization", "base_url", "sk-"):
        assert leak not in text


@pytest.mark.asyncio
async def test_status_reports_provider_health_and_open_circuit():
    app_module._status_cache.clear()
    provider = SimpleNamespace(
        api_key="sk-secret-value",
        health=SimpleNamespace(last_check=1.0, available=True, latency_ms=12.34),
    )
    breakers = SimpleNamespace(
        all_status=AsyncMock(return_value={"openai": {"state": "open"}})
    )
    app, client = _client(AsyncMock())
    app.state.redis = AsyncMock()
    app.state.registry = SimpleNamespace(all=lambda: {"openai": provider})
    app.state.handler = SimpleNamespace(circuit_breakers=breakers)

    async with client:
        resp = await client.get("/status")

    body = resp.json()
    assert body["service"] == "degraded"  # open circuit
    assert body["providers"] == [
        {
            "name": "openai",
            "configured": True,
            "health": "up",
            "circuit": "open",
            "latency_ms": 12.3,
        }
    ]
    assert "sk-secret-value" not in resp.text
