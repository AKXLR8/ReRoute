"""Tests for GET /admin/breakdown (mocked DB via dependency_overrides)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from reroute.app import create_app
from reroute.auth.auth import AuthContext, get_current_user
from reroute.database import get_db


def _client_with_results(results):
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[
        MagicMock(all=MagicMock(return_value=r)) for r in results
    ])

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: AuthContext(is_admin=True)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_breakdown_shapes():
    providers = [SimpleNamespace(name="acme", requests=10, cost=2.5),
                 SimpleNamespace(name=None, requests=1, cost=0.0)]
    models = [SimpleNamespace(model="mercury-2", requests=10, cost=2.5, avg_latency=300.0,
                              avg_ttft=210.0, avg_tps=80.0, truncated=1)]
    finishes = [SimpleNamespace(reason="stop", n=8), SimpleNamespace(reason="length", n=2)]
    async with _client_with_results([providers, models, finishes]) as client:
        resp = await client.get("/admin/breakdown?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert data["by_provider"][0] == {"name": "acme", "requests": 10, "cost_usd": 2.5}
    assert data["by_provider"][1]["name"] is None
    assert data["by_model"][0]["model"] == "mercury-2"
    assert data["by_model"][0]["avg_ttft_ms"] == 210.0
    assert data["by_model"][0]["avg_tokens_per_sec"] == 80.0
    assert data["by_model"][0]["truncated"] == 1
    assert data["by_finish_reason"] == [{"reason": "stop", "count": 8},
                                        {"reason": "length", "count": 2}]
