"""Integration tests — full request flow through the gateway."""


import pytest
from httpx import ASGITransport, AsyncClient

from reroute.app import create_app


@pytest.fixture
def app():
    application = create_app()
    # Simulate what lifespan sets up — registry, handler, etc.
    from reroute.providers.base import ProviderRegistry
    application.state.registry = ProviderRegistry()
    return application


@pytest.mark.asyncio
async def test_health_endpoint(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/v1/chat/completions", json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "hi"}],
        })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_key_cannot_list_models(app):
    """Per-user BYOK: the break-glass admin key has no user, so /v1/models
    refuses it — models are only meaningful for a signed-in account."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        from reroute.config import get_settings
        s = get_settings()
        resp = await client.get(
            "/v1/models",
            headers={"X-API-Key": s.admin_api_key},
        )
    assert resp.status_code == 401
    assert "signed-in" in resp.json()["detail"]
