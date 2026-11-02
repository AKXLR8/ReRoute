"""Redis-backed semantic cache using a local ONNX embedding model."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import struct
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

# All lookups happen against one bounded hash, so this caps memory + CPU per
# namespace instead of relying on SCAN's arbitrary key order.
_CACHE_VERSION = "v2"


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


def _pack_embedding(values: list[float], cached_at: float) -> bytes:
    return np.asarray(values, dtype=np.float32).tobytes() + struct.pack(">d", cached_at)


def _unpack_embedding(raw: bytes) -> tuple[np.ndarray, float]:
    return np.frombuffer(raw[:-8], dtype=np.float32), struct.unpack(">d", raw[-8:])[0]


def _cosine_sim(a: list[float], b: list[float]) -> float:
    a_arr = np.asarray(a, dtype=np.float32)
    b_arr = np.asarray(b, dtype=np.float32)
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))


def _messages_text(request: ChatRequest) -> str:
    """Canonical messages including role/name — same text in a different role
    must not replay another role's completion."""
    return json.dumps(
        [
            {
                "role": m.role,
                "name": m.name,
                "content": m.content,
            }
            for m in request.messages
        ],
        sort_keys=True,
        ensure_ascii=False,
    )


def _params_key(request: ChatRequest) -> str:
    """Sampling params and provider pin change the answer — they change the key.
    Role structure is included so a system prompt can never semantically match
    a user message with the same text."""
    roles = hashlib.sha256(
        json.dumps(
            [{"role": m.role, "name": m.name} for m in request.messages],
            sort_keys=True,
        ).encode()
    ).hexdigest()[:16]
    return (
        f"t={request.temperature}|m={request.max_tokens}|p={request.top_p}"
        f"|s={request.stop}|r={request.provider}|u={request.user}|roles={roles}"
    )


class SemanticCache:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        s = get_settings()
        self.threshold = s.semantic_cache_threshold
        self.ttl = s.semantic_cache_ttl_seconds
        self.max_entries = max(1, s.semantic_cache_max_entries)

    def _exact_key(self, scope: str, model: str, text: str, params: str) -> str:
        h = hashlib.sha256(f"{scope}:{model}:{text}:{params}".encode()).hexdigest()[:32]
        return f"cache:{_CACHE_VERSION}:exact:{h}"

    def _namespace(self, scope: str, model: str, params: str) -> str:
        """model + tenant + sampling params: fuzzy on text only."""
        h = hashlib.sha256(f"{scope}:{model}:{params}".encode()).hexdigest()[:24]
        return f"cache:{_CACHE_VERSION}:sem:{h}"

    async def get(self, request: ChatRequest, scope: str = "global") -> dict | None:
        """Look up cache for this request. `scope` isolates tenants.

        A cache failure must never fail a user request: Redis/ONNX errors are
        logged and treated as a miss.
        """
        if not request.cache:
            return None

        try:
            return await self._get(request, scope)
        except Exception:
            log.exception("Semantic cache lookup failed; treating as miss")
            return None

    async def _get(self, request: ChatRequest, scope: str) -> dict | None:
        model = request.model
        text = _messages_text(request)
        params = _params_key(request)

        # 1. Exact match (fast path) — get() always returns the response payload
        exact = await self.redis.get(self._exact_key(scope, model, text, params))
        if exact:
            return json.loads(exact).get("response")

        # 2. Semantic match — one bounded HGETALL + cosine, deterministic.
        ns = self._namespace(scope, model, params)
        raw_entries = await self.redis.hgetall(ns)  # embeddings only, compact
        if not raw_entries:
            return None
        query_embed = np.asarray(await _embed_text(text), dtype=np.float32)
        qnorm = max(float(np.linalg.norm(query_embed)), 1e-9)
        now = time.time()
        best_field = None
        best_score = -1.0
        for field, raw in raw_entries.items():
            try:
                cached, cached_at = _unpack_embedding(raw)
            except (TypeError, ValueError):
                continue
            if now - cached_at > self.ttl:
                continue
            cnorm = max(float(np.linalg.norm(cached)), 1e-9)
            score = float(np.dot(query_embed, cached) / (qnorm * cnorm))
            if score > best_score:
                best_score, best_field = score, field
        if best_field is None or best_score < self.threshold:
            return None
        raw_resp = await self.redis.hget(f"{ns}:resp", best_field)
        if not raw_resp:
            return None
        try:
            entry = json.loads(raw_resp)
        except (TypeError, ValueError):
            return None
        # best-effort LRU touch; a failed touch must not fail the hit
        try:
            await self.redis.zadd(f"{ns}:lru", {best_field: now})
        except Exception:
            log.debug("Failed to touch semantic cache LRU", exc_info=True)
        return entry.get("response")

    async def set(self, request: ChatRequest, response: dict, scope: str = "global") -> None:
        """Store response in both exact and semantic caches, namespaced by `scope`.

        Cache writes are best-effort; the completed provider response is still
        returned when Redis or the embedding model is unavailable.
        """
        if not request.cache:
            return

        try:
            await self._set(request, response, scope)
        except Exception:
            log.exception("Semantic cache store failed")

    async def _set(self, request: ChatRequest, response: dict, scope: str) -> None:
        model = request.model
        text = _messages_text(request)
        params = _params_key(request)
        now = time.time()
        field = hashlib.sha256(text.encode()).hexdigest()[:32]
        entry = json.dumps({
            "response": response,
            "model": model,
            "cached_at": now,
        })

        # Exact cache
        await self.redis.set(
            self._exact_key(scope, model, text, params), entry, ex=self.ttl
        )

        # Semantic cache (with real embedding)
        ns = self._namespace(scope, model, params)
        embed = await _embed_text(text)
        sem_entry = json.dumps({"response": response, "cached_at": now})
        pipe = self.redis.pipeline()
        pipe.hset(ns, field, _pack_embedding(embed, now))
        pipe.hset(f"{ns}:resp", field, sem_entry)
        pipe.zadd(f"{ns}:lru", {field: now})
        pipe.expire(ns, self.ttl)
        pipe.expire(f"{ns}:resp", self.ttl)
        pipe.expire(f"{ns}:lru", self.ttl)
        await pipe.execute()

        # Bounded namespace: drop least-recently-used entries.
        count = await self.redis.zcard(f"{ns}:lru")
        overflow = count - self.max_entries
        if overflow > 0:
            oldest = await self.redis.zrange(f"{ns}:lru", 0, overflow - 1)
            if oldest:
                await self.redis.hdel(ns, *oldest)
                await self.redis.hdel(f"{ns}:resp", *oldest)
                await self.redis.zrem(f"{ns}:lru", *oldest)
