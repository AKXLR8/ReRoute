"""Tests for request deduplication."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from reroute.cache.dedup import RequestDeduplicator
from reroute.schemas.chat import ChatMessage, ChatRequest

SCOPE = "team:1"


def _make_request(content: str = "hello", model: str = "gpt-4o") -> ChatRequest:
    return ChatRequest(model=model, messages=[ChatMessage(role="user", content=content)])


@pytest.mark.asyncio
async def test_dedup_single_call():
    dedup = RequestDeduplicator()
    func = AsyncMock(return_value="result")
    req = _make_request()
    result = await dedup.execute(SCOPE, req, func)
    assert result == "result"
    func.assert_called_once()


@pytest.mark.asyncio
async def test_dedup_identical_requests_share_result():
    dedup = RequestDeduplicator()
    call_count = 0

    async def slow_func(req):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return f"result-{call_count}"

    req = _make_request()
    r1, r2 = await asyncio.gather(
        dedup.execute(SCOPE, req, slow_func),
        dedup.execute(SCOPE, req, slow_func),
    )
    # Both should get the same result from the single invocation
    assert r1 == r2
    assert call_count == 1


@pytest.mark.asyncio
async def test_dedup_different_requests_independent():
    dedup = RequestDeduplicator()
    func = AsyncMock(side_effect=lambda req: f"result-{req.messages[0].content}")

    req1 = _make_request("hello")
    req2 = _make_request("world")
    r1 = await dedup.execute(SCOPE, req1, func)
    r2 = await dedup.execute(SCOPE, req2, func)
    assert r1 != r2
    assert func.call_count == 2


@pytest.mark.asyncio
async def test_dedup_error_propagates():
    dedup = RequestDeduplicator()
    func = AsyncMock(side_effect=ValueError("boom"))

    req = _make_request()
    with pytest.raises(ValueError, match="boom"):
        await dedup.execute(SCOPE, req, func)


@pytest.mark.asyncio
async def test_dedup_cleanup_after_completion():
    dedup = RequestDeduplicator()
    func = AsyncMock(return_value="ok")
    req = _make_request()
    await dedup.execute(SCOPE, req, func)
    assert len(dedup._in_flight) == 0


@pytest.mark.asyncio
async def test_dedup_never_coalesces_across_tenants():
    """Regression: identical requests from different teams must not share a response."""
    dedup = RequestDeduplicator()
    call_count = 0

    async def slow_func(req):
        nonlocal call_count
        call_count += 1
        n = call_count
        await asyncio.sleep(0.05)
        return f"result-{n}"

    req = _make_request()
    r1, r2 = await asyncio.gather(
        dedup.execute("team:a", req, slow_func),
        dedup.execute("team:b", req, slow_func),
    )
    assert call_count == 2
    assert r1 != r2


@pytest.mark.asyncio
async def test_dedup_respects_sampling_params():
    """Regression: temperature=0 and temperature=1.5 must not coalesce."""
    dedup = RequestDeduplicator()
    func = AsyncMock(return_value="x")
    cold = _make_request()
    hot = ChatRequest(
        model="gpt-4o", messages=[ChatMessage(role="user", content="hello")], temperature=1.5
    )
    await dedup.execute(SCOPE, cold, func)
    await dedup.execute(SCOPE, hot, func)
    assert func.call_count == 2
