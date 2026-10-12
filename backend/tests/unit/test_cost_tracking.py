"""Cost/usage tracking accuracy — the numbers dashboards are billed on.

Regression history: every provider hardcoded ONE model's price, streaming
wrote zero tokens/cost everywhere, and the Prometheus cost counter never
incremented at all.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4 as _uuid4

import httpx
import pytest
from sqlalchemy.dialects import postgresql

from reroute.auth.auth import AuthContext
from reroute.cache.dedup import RequestDeduplicator
from reroute.gateway import handler as handler_module
from reroute.gateway.handler import GatewayHandler
from reroute.providers.anthropic_provider import AnthropicProvider
from reroute.providers.gemini_provider import GeminiProvider
from reroute.providers.openai_provider import OpenAIProvider
from reroute.schemas.chat import (
    ChatRequest,
    ChatResponse,
    StreamingChoice,
    StreamingChunk,
    Usage,
)

_AUTH = AuthContext(user_id=str(_uuid4()), email="t@example.com", role="member", is_admin=False)
_PROVIDERS: list = []


def _request(model: str = "gpt-4o-mini") -> ChatRequest:
    return ChatRequest(model=model, messages=[{"role": "user", "content": "hi"}])


def _response(model: str = "gpt-4o-mini") -> ChatResponse:
    return ChatResponse(
        id="x",
        model=model,
        choices=[{
            "index": 0,
            "message": {"role": "assistant", "content": "hello"},
            "finish_reason": "stop",
        }],
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        provider="openai",
        latency_ms=1.0,
    )


def _make_handler(route_side_effect=None):
    router = MagicMock()
    provider = MagicMock()
    provider.name = "openai"
    provider.estimate_cost.return_value = 0.0042

    async def _route(request, _providers):
        return provider, _response(), None

    router.route = AsyncMock(side_effect=route_side_effect or _route)
    return GatewayHandler(
        router=router,
        rate_limiter=AsyncMock(),
        cache=AsyncMock(**{"get.return_value": None}),
        circuit_breakers=MagicMock(),
        deduplicator=RequestDeduplicator(),
    ), provider


# --- pricing keyed by the requested model, not one hardcoded model forever ---


def test_openai_cost_uses_requested_model():
    p = OpenAIProvider(api_key="k")
    assert p.estimate_cost(1_000_000, 1_000_000, "gpt-4o-mini") == pytest.approx(0.75)
    assert p.estimate_cost(1_000_000, 1_000_000, "gpt-4o") == pytest.approx(12.50)
    assert p.estimate_cost(1_000_000, 1_000_000, "o1") == pytest.approx(75.0)
    assert p.estimate_cost(1_000_000, 1_000_000) == pytest.approx(12.50)  # unknown → default


def test_anthropic_cost_uses_requested_model():
    p = AnthropicProvider(api_key="k")
    assert p.estimate_cost(1_000_000, 1_000_000, "claude-3-opus-20240229") == pytest.approx(90.0)
    assert p.estimate_cost(1_000_000, 1_000_000, "claude-3-haiku-20240307") == pytest.approx(1.50)


def test_gemini_cost_uses_requested_model():
    p = GeminiProvider(api_key="k")
    assert p.estimate_cost(1_000_000, 1_000_000, "gemini-1.5-pro") == pytest.approx(6.25)
    assert p.estimate_cost(1_000_000, 1_000_000, "gemini-2.0-flash") == pytest.approx(0.50)
    assert p.estimate_cost(1_000_000, 1_000_000, "gemini-2.0-flash-lite") == pytest.approx(0.375)


# --- non-stream: same cost number reaches audit row AND Prometheus ---


@pytest.mark.asyncio
async def test_success_reports_cost_and_tokens_to_metrics_and_audit():
    handler, provider = _make_handler()
    db = AsyncMock()

    with patch.object(handler_module, "metrics_collector") as mc:
        await handler.handle_chat(_request(), db, _AUTH, _PROVIDERS)

    kwargs = mc.record_request.call_args.kwargs
    assert kwargs["cost"] == 0.0042
    assert kwargs["input_tokens"] == 100
    assert kwargs["output_tokens"] == 50
    # cost priced by the requested model, not a hardcoded default
    provider.estimate_cost.assert_called_once_with(100, 50, "gpt-4o-mini")

    row = db.add.call_args[0][0]
    assert row.cost_usd == 0.0042
    assert row.input_tokens == 100
    assert row.output_tokens == 50
    assert row.model_requested == "gpt-4o-mini"
    assert row.model_served == "gpt-4o-mini"
    assert row.latency_ms == 1.0


# --- streaming: provider-reported usage reaches audit + metrics + cost ---


@pytest.mark.asyncio
async def test_stream_audit_and_metrics_carry_usage_and_cost():
    provider = MagicMock()
    provider.name = "openai"
    provider.estimate_cost.return_value = 0.0031

    async def _stream(request):
        yield StreamingChunk(choices=[StreamingChoice(delta={"content": "a"})])
        await asyncio.sleep(0.01)  # non-zero post-TTFT window so tps is computable
        yield StreamingChunk(
            model="gpt-4o-mini-2024-07-18",
            choices=[StreamingChoice(finish_reason="stop")],
            usage=Usage(prompt_tokens=7, completion_tokens=5, total_tokens=12),
        )

    provider.stream = _stream
    router = MagicMock()
    router.route_stream = AsyncMock(return_value=(provider, None))
    handler = GatewayHandler(
        router=router,
        rate_limiter=AsyncMock(),
        cache=AsyncMock(),
        circuit_breakers=MagicMock(),
        deduplicator=RequestDeduplicator(),
    )
    db = AsyncMock()

    with patch.object(handler_module, "metrics_collector") as mc:
        out = [c async for c in handler.handle_stream(_request(), db, _AUTH, _PROVIDERS)]

    assert any("[DONE]" in c for c in out)

    kwargs = mc.record_request.call_args.kwargs
    assert kwargs["status"] == "success"
    assert kwargs["input_tokens"] == 7
    assert kwargs["output_tokens"] == 5
    assert kwargs["cost"] == 0.0031

    stmt = db.execute.call_args[0][0]
    params = stmt.compile(dialect=postgresql.dialect()).params
    assert params["is_stream"] is True
    assert params["input_tokens"] == 7
    assert params["output_tokens"] == 5
    assert params["cost_usd"] == 0.0031
    assert params["model_served"] == "gpt-4o-mini-2024-07-18"
    assert params["status_code"] == 200
    assert params["error_message"] is None
    # stream speed + finish_reason reach the audit row
    assert params["finish_reason"] == "stop"
    assert params["ttft_ms"] is not None and params["ttft_ms"] >= 0
    assert params["tokens_per_sec"] is not None and params["tokens_per_sec"] > 0
    # metrics reported the same
    timing = mc.record_stream_timing.call_args.args
    assert timing[0] == "openai" and timing[1] == "gpt-4o-mini"
    assert timing[2] is not None and timing[3] is not None
    mc.record_finish_reason.assert_called_once_with("openai", "gpt-4o-mini", "stop")


# --- finish_reason on non-stream reaches audit + metrics ---


@pytest.mark.asyncio
async def test_non_stream_finish_reason_tracked():
    handler, provider = _make_handler()
    db = AsyncMock()

    with patch.object(handler_module, "metrics_collector") as mc:
        await handler.handle_chat(_request(), db, _AUTH, _PROVIDERS)

    row = db.add.call_args[0][0]
    assert row.finish_reason == "stop"
    mc.record_finish_reason.assert_called_once_with("openai", "gpt-4o-mini", "stop")


# --- cache hit: $-saved computed from cached usage and provider pricing ---


@pytest.mark.asyncio
async def test_cache_hit_records_savings():
    provider = MagicMock()
    provider.name = "openai"
    provider.estimate_cost.return_value = 0.0042
    cache = AsyncMock()
    cache.get.return_value = {
        "model": "gpt-4o-mini",
        "choices": [],
        "provider": "openai",
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }
    router = MagicMock()
    handler = GatewayHandler(
        router=router,
        rate_limiter=AsyncMock(),
        cache=cache,
        circuit_breakers=MagicMock(),
        deduplicator=RequestDeduplicator(),
    )
    db = AsyncMock()

    with patch.object(handler_module, "metrics_collector") as mc:
        resp = await handler.handle_chat(_request(), db, _AUTH, [provider])

    assert resp.cached is True
    provider.estimate_cost.assert_called_once_with(100, 50, "gpt-4o-mini")
    mc.record_cache_hit.assert_called_once_with(cost_saved=0.0042)
    # cached audit row: zero spend, non-zero savings
    row = db.add.call_args[0][0]
    assert row.is_cached is True
    assert row.cost_usd == 0.0
    assert row.cache_saved_usd == 0.0042


def test_cache_savings_zero_without_usage_or_provider():
    savings = GatewayHandler._cache_savings
    assert savings({"usage": None}, [], "m") == 0.0
    assert savings({}, [], "m") == 0.0
    assert savings({"usage": {"prompt_tokens": 1}, "provider": "nope"}, [], "m") == 0.0


@pytest.mark.asyncio
async def test_openai_stream_requests_and_parses_usage():
    captured = {}

    def _transport(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            text=(
                'data: {"id":"c1","created":1,"model":"gpt-4o-mini",'
                '"choices":[{"index":0,"delta":{"content":"hi"},"finish_reason":null}]}\n\n'
                'data: {"id":"c1","created":1,"model":"gpt-4o-mini","choices":[],'
                '"usage":{"prompt_tokens":7,"completion_tokens":5,"total_tokens":12}}\n\n'
                "data: [DONE]\n\n"
            ),
        )

    p = OpenAIProvider(api_key="k")
    p._client = httpx.AsyncClient(
        base_url=p.base_url,
        transport=httpx.MockTransport(_transport),
        headers={"Authorization": "Bearer k"},
    )
    try:
        chunks = [c async for c in p.stream(_request())]
    finally:
        await p.aclose()

    assert captured["body"]["stream_options"] == {"include_usage": True}
    assert chunks[-1].usage is not None
    assert chunks[-1].usage.prompt_tokens == 7
    assert chunks[-1].usage.completion_tokens == 5
    assert chunks[-1].usage.total_tokens == 12


@pytest.mark.asyncio
async def test_anthropic_stream_captures_split_usage_events():
    def _transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                'data: {"type":"message_start","message":{"id":"m1",'
                '"usage":{"input_tokens":10,"output_tokens":1}}}\n\n'
                'data: {"type":"content_block_delta",'
                '"delta":{"type":"text_delta","text":"hey"}}\n\n'
                'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},'
                '"usage":{"output_tokens":42}}\n\n'
                'data: {"type":"message_stop"}\n\n'
            ),
        )

    p = AnthropicProvider(api_key="k")
    p._client = httpx.AsyncClient(
        base_url=p.base_url, transport=httpx.MockTransport(_transport)
    )
    try:
        chunks = [c async for c in p.stream(_request("claude-3-5-sonnet-20241022"))]
    finally:
        await p.aclose()

    final = chunks[-1]
    assert final.usage is not None
    assert final.usage.prompt_tokens == 10
    assert final.usage.completion_tokens == 42
    assert final.usage.total_tokens == 52
