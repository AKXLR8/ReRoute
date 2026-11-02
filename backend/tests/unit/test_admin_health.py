"""On-demand provider health refresh (Vercel has no reliable background loop)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from reroute.app import create_app
from reroute.auth.auth import AuthContext, get_current_user


def _client(auth: AuthContext) -> AsyncClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: auth
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_admin_can_refresh_shared_provider_health():
    provider = SimpleNamespace(
        api_key="sk-test", health_check=AsyncMock(return_value=True)
    )
    keyless = SimpleNamespace(
        api_key="", health_check=AsyncMock(return_value=True)
    )
    ollama = SimpleNamespace(
        api_key="", health_check=AsyncMock(return_value=False)
    )
    app = create_app()
    app.state.registry = SimpleNamespace(
        all=lambda: {"openai": provider, "groq": keyless, "ollama": ollama}
    )
    app.dependency_overrides[get_current_user] = lambda: AuthContext(
        is_admin=True, role="admin"
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/admin/health/refresh")

    assert resp.status_code == 200
    assert resp.json() == {"providers": {"openai": True, "ollama": False}}
    keyless.health_check.assert_not_awaited()


@pytest.mark.asyncio
async def test_member_cannot_refresh_provider_health():
    app = create_app()
    app.state.registry = SimpleNamespace(all=lambda: {})
    app.dependency_overrides[get_current_user] = lambda: AuthContext(
        is_admin=False, role="member"
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/admin/health/refresh")

    assert resp.status_code == 403
