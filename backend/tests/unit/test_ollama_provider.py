"""Tests for Ollama tag resolution (no Ollama needed — stubbed client)."""

from unittest.mock import AsyncMock, MagicMock

from reroute.providers.ollama_provider import OllamaProvider


def _provider_with_tags(tags):
    p = OllamaProvider()
    client = AsyncMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"models": [{"name": t} for t in tags]}
    client.get = AsyncMock(return_value=resp)
    p._get_client = AsyncMock(return_value=client)
    return p


async def test_resolve_exact_tag():
    p = _provider_with_tags(["llama3.1:8b"])
    assert await p._resolve_model("llama3.1:8b") == "llama3.1:8b"


async def test_resolve_bare_name_to_single_tag():
    p = _provider_with_tags(["llama3.1:8b"])
    assert await p._resolve_model("llama3.1") == "llama3.1:8b"


async def test_resolve_prefers_latest():
    p = _provider_with_tags(["phi3:latest", "phi3:mini"])
    assert await p._resolve_model("phi3") == "phi3:latest"


async def test_resolve_ambiguous_passes_through():
    p = _provider_with_tags(["qwen3:0.6b", "qwen3:4b"])
    assert await p._resolve_model("qwen3") == "qwen3"


async def test_resolve_tags_unreachable_passes_through():
    p = OllamaProvider()
    client = AsyncMock()
    client.get = AsyncMock(side_effect=ConnectionError("down"))
    p._get_client = AsyncMock(return_value=client)
    assert await p._resolve_model("llama3.1") == "llama3.1"
