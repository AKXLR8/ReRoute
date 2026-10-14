"""Redis-backed semantic cache using a local ONNX embedding model."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path

import numpy as np
from redis.asyncio import Redis

from ..config import get_settings
from ..schemas.chat import ChatRequest

# Vercel: scripts/prefetch_model.py baked the model into .hf/ at build time;
# the runtime FS is read-only, so point the HF cache at the bundled copy.
if os.environ.get("VERCEL"):
    os.environ.setdefault("HF_HOME", str(Path(__file__).resolve().parents[2] / ".hf"))

log = logging.getLogger(__name__)

_model = None

# O(n) full-scan guard: never walk more than this many embedding keys per lookup
_SCAN_LIMIT = 50


def _get_model():
    """Lazy-load the ONNX session + tokenizer (bundled under HF_HOME on Vercel)."""
    global _model
    if _model is None:
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        name = get_settings().embedding_model
        log.info("Loading ONNX embedding model: %s", name)
        tokenizer = Tokenizer.from_file(hf_hub_download(name, "tokenizer.json"))
        tokenizer.enable_truncation(max_length=256)
        session = ort.InferenceSession(
            hf_hub_download(name, "onnx/model_quantized.onnx"),
            providers=["CPUExecutionProvider"],
        )
        _model = (tokenizer, session)
    return _model


def _mean_pool(hidden: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Attention-mask-weighted mean pooling — parity with sentence-transformers."""
    m = mask.astype(np.float32)[..., None]
    return (hidden * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)


def _embed_sync(texts: list[str]) -> np.ndarray:
    """Tokenize → ONNX → mean-pool → L2-normalize. Returns (n, dim)."""
    tokenizer, session = _get_model()
    encodings = [tokenizer.encode(t) for t in texts]
    max_len = max(len(e.ids) for e in encodings)
    input_ids = np.zeros((len(encodings), max_len), dtype=np.int64)
    attention_mask = np.zeros((len(encodings), max_len), dtype=np.int64)
    for row, enc in enumerate(encodings):
        input_ids[row, : len(enc.ids)] = enc.ids
        attention_mask[row, : len(enc.attention_mask)] = enc.attention_mask
    hidden = session.run(
        ["last_hidden_state"],
        {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": np.zeros_like(input_ids),
        },
    )[0]
    pooled = _mean_pool(hidden, attention_mask)
    return pooled / np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9)


async def _embed_text(text: str) -> list[float]:
    """Encode off the event loop — ONNX inference must never block it."""
    loop = asyncio.get_running_loop()
    return (await loop.run_in_executor(None, _embed_sync, [text]))[0].tolist()


def _cosine_sim(a: list[float], b: list[float]) -> float:
    a_arr = np.asarray(a, dtype=np.float32)
    b_arr = np.asarray(b, dtype=np.float32)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))


def _messages_text(request: ChatRequest) -> str:
    return " ".join(
        m.content if isinstance(m.content, str) else str(m.content)
        for m in request.messages
        if m.content
    )


def _params_key(request: ChatRequest) -> str:
    """Sampling params and provider pin change the answer — they change the key."""
    return (
        f"t={request.temperature}|m={request.max_tokens}|p={request.top_p}"
        f"|s={request.stop}|r={request.provider}"
    )


class SemanticCache:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        s = get_settings()
        self.threshold = s.semantic_cache_threshold
        self.ttl = s.semantic_cache_ttl_seconds

    def _exact_key(self, scope: str, model: str, text: str, params: str) -> str:
        h = hashlib.sha256(f"{scope}:{model}:{text}:{params}".encode()).hexdigest()[:32]
        return f"cache:exact:{h}"

    def _embed_key(self, scope: str, model: str, text: str, params: str) -> str:
        h = hashlib.sha256(f"{scope}:{model}:{text}:{params}".encode()).hexdigest()[:32]
        return f"cache:embed:{model}:{scope}:{self._params_hash(params)}:{h}"

    @staticmethod
    def _params_hash(params: str) -> str:
        return hashlib.sha256(params.encode()).hexdigest()[:16]

    async def get(self, request: ChatRequest, scope: str = "global") -> dict | None:
        """Look up cache for this request. `scope` isolates tenants."""
        if not request.cache:
            return None

        model = request.model
        text = _messages_text(request)
        params = _params_key(request)

        # 1. Exact match (fast path) — get() always returns the response payload
        exact = await self.redis.get(self._exact_key(scope, model, text, params))
        if exact:
            return json.loads(exact).get("response")

        # 2. Semantic match — bounded scan, cosine similarity.
        # Namespace = model + tenant scope + params: fuzzy on text only, never
        # across tenants or differing sampling/provider params.
        pattern = f"cache:embed:{model}:{scope}:{self._params_hash(params)}:*"
        query_embed = await _embed_text(text)
        scanned = 0
        async for key in self.redis.scan_iter(match=pattern, count=100):
            if scanned >= _SCAN_LIMIT:
                break
            scanned += 1
            raw = await self.redis.get(key)
            if not raw:
                continue
            entry = json.loads(raw)
            cached_embed = entry.get("embedding", [])
            if cached_embed and _cosine_sim(query_embed, cached_embed) >= self.threshold:
                return entry.get("response")

        return None

    async def set(self, request: ChatRequest, response: dict, scope: str = "global") -> None:
        """Store response in both exact and semantic caches, namespaced by `scope`."""
        if not request.cache:
            return

        model = request.model
        text = _messages_text(request)
        params = _params_key(request)
        entry = json.dumps({"response": response, "model": model, "cached_at": time.time()})

        # Exact cache
        await self.redis.set(self._exact_key(scope, model, text, params), entry, ex=self.ttl)

        # Semantic cache (with real embedding)
        embed = await _embed_text(text)
        sem_entry = json.dumps({"embedding": embed, "response": response})
        await self.redis.set(self._embed_key(scope, model, text, params), sem_entry, ex=self.ttl)
