"""Tests for semantic cache."""

import fakeredis.aioredis
import pytest

from reroute.cache.semantic_cache import SemanticCache, _cosine_sim, _embed_text
from reroute.schemas.chat import ChatMessage, ChatRequest


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis()
    yield r
    await r.aclose()


async def test_embed_text_deterministic():
    v1 = await _embed_text("hello world test")
    v2 = await _embed_text("hello world test")
    assert v1 == v2


async def test_cosine_sim_identical():
    v = await _embed_text("hello world")
    assert _cosine_sim(v, v) > 0.99


async def test_cosine_sim_different():
    v1 = await _embed_text("hello world")
    v2 = await _embed_text("completely different unrelated text here")
    assert _cosine_sim(v1, v2) < 0.5


async def test_cosine_sim_similar():
    v1 = await _embed_text("the quick brown fox jumps over the lazy dog")
    v2 = await _embed_text("the quick brown fox leaped over the lazy dog")
    assert _cosine_sim(v1, v2) > 0.8


@pytest.mark.asyncio
async def test_cache_miss(redis):
    cache = SemanticCache(redis)
    req = ChatRequest(model="gpt-4o", messages=[ChatMessage(role="user", content="hello")])
    result = await cache.get(req)
    assert result is None


@pytest.mark.asyncio
async def test_cache_exact_hit(redis):
    cache = SemanticCache(redis)
    req = ChatRequest(model="gpt-4o", messages=[ChatMessage(role="user", content="hello")])
    await cache.set(req, {"model": "gpt-4o", "choices": []})

    result = await cache.get(req)
    assert result is not None
    assert result["model"] == "gpt-4o"


@pytest.mark.asyncio
async def test_cache_semantic_hit(redis):
    cache = SemanticCache(redis)
    cache.threshold = 0.5  # lower threshold for bag-of-words

    text1 = "what is the weather like today outside"
    text2 = "what is the weather like today here"
    assert _cosine_sim(await _embed_text(text1), await _embed_text(text2)) > cache.threshold

    req1 = ChatRequest(model="gpt-4o", messages=[ChatMessage(role="user", content=text1)])
    await cache.set(req1, {"model": "gpt-4o", "answer": "sunny"})

    req2 = ChatRequest(model="gpt-4o", messages=[ChatMessage(role="user", content=text2)])
    result = await cache.get(req2)
    assert result is not None
    assert result["answer"] == "sunny"


@pytest.mark.asyncio
async def test_cache_different_model_no_hit(redis):
    cache = SemanticCache(redis)
    cache.threshold = 0.8
    req1 = ChatRequest(model="gpt-4o", messages=[ChatMessage(role="user", content="hello")])
    await cache.set(req1, {"model": "gpt-4o"})

    req2 = ChatRequest(model="claude-3", messages=[ChatMessage(role="user", content="hello")])
    result = await cache.get(req2)
    assert result is None


@pytest.mark.asyncio
async def test_cache_disabled(redis):
    cache = SemanticCache(redis)
    req = ChatRequest(
        model="gpt-4o", messages=[ChatMessage(role="user", content="hi")], cache=False
    )
    await cache.set(req, {"data": "test"})
    result = await cache.get(req)
    assert result is None


@pytest.mark.asyncio
async def test_cache_never_crosses_tenants(redis):
    """Regression: team A's completion must never be served to team B (exact or semantic)."""
    cache = SemanticCache(redis)
    req = ChatRequest(model="gpt-4o", messages=[ChatMessage(role="user", content="hello")])
    await cache.set(req, {"model": "gpt-4o", "who": "team-a"}, scope="team:a")

    assert (await cache.get(req, scope="team:a"))["who"] == "team-a"
    assert await cache.get(req, scope="team:b") is None


@pytest.mark.asyncio
async def test_cache_respects_provider_pin(redis):
    """Regression: a provider-pinned request must not be served an unpinned response."""
    cache = SemanticCache(redis)
    req = ChatRequest(model="gpt-4o", messages=[ChatMessage(role="user", content="hello")])
    await cache.set(req, {"served_by": "anthropic"})

    pinned = ChatRequest(
        model="gpt-4o",
        messages=[ChatMessage(role="user", content="hello")],
        provider="openai",
    )
    assert await cache.get(pinned) is None
    # and the unpinned entry still hits
    assert (await cache.get(req))["served_by"] == "anthropic"


@pytest.mark.asyncio
async def test_cache_semantic_respects_sampling_params(redis):
    """Regression: semantic scan must stay within the same params bucket."""
    cache = SemanticCache(redis)
    cache.threshold = 0.3
    text1 = "what is the weather like today outside"
    text2 = "what is the weather like today here"
    req1 = ChatRequest(model="gpt-4o", messages=[ChatMessage(role="user", content=text1)])
    await cache.set(req1, {"answer": "sunny-temp0"})

    req2 = ChatRequest(
        model="gpt-4o",
        messages=[ChatMessage(role="user", content=text2)],
        temperature=1.5,
    )
    assert await cache.get(req2) is None
