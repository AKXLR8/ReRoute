"""Tests for GET /admin/activity (mocked DB via dependency_overrides)."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from reroute.app import create_app
from reroute.auth.auth import AuthContext, get_current_user
from reroute.database import get_db


def _client_with_rows(rows):
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows
    db.execute = AsyncMock(return_value=result)

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: AuthContext(is_admin=True)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_activity_returns_per_day_rows():
    rows = [
        SimpleNamespace(day=date(2026, 9, 18), requests=10, input_tokens=100,
                        output_tokens=50, cost=1.5, avg_latency=120.0, cached=3,
                        avg_ttft=250.0, avg_tps=45.0, cache_saved=0.012),
        SimpleNamespace(day=date(2026, 9, 19), requests=4, input_tokens=None,
                        output_tokens=None, cost=None, avg_latency=None, cached=None,
                        avg_ttft=None, avg_tps=None, cache_saved=None),
    ]
    async with _client_with_rows(rows) as client:
        resp = await client.get("/admin/activity?days=7")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0] == {"date": "2026-09-18", "requests": 10, "input_tokens": 100,
                       "output_tokens": 50, "cost_usd": 1.5, "avg_latency_ms": 120.0,
                       "cached": 3, "avg_ttft_ms": 250.0, "avg_tokens_per_sec": 45.0,
                       "cache_saved_usd": 0.012}
    assert data[1]["requests"] == 4
    assert data[1]["cost_usd"] == 0  # NULL sums become 0, not null
    assert data[1]["avg_ttft_ms"] is None  # NULL averages stay null (no data ≠ 0ms)
