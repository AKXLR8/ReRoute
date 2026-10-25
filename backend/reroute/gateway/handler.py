"""Core gateway handler — the main request path.

Authenticate → Rate limit → Policy → Route → Call provider → Audit → Cache → Return
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator

from opentelemetry import trace
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.auth import AuthContext
from ..cache.dedup import RequestDeduplicator
from ..cache.semantic_cache import SemanticCache
from ..circuit_breaker.circuit_breaker import CircuitBreakerRegistry
from ..config import get_settings
from ..models.audit_log import AuditLog
from ..observability.metrics import metrics_collector
from ..prompt.guardrails import GuardrailViolation, PromptGuard, flatten_text
from ..providers.base import Provider
from ..rate_limit.rate_limiter import RateLimiter, RateLimitExceeded
from ..router.router import Router
from ..schemas.chat import ChatRequest, ChatResponse, Usage

log = logging.getLogger(__name__)
tracer = trace.get_tracer("rerouteai.gateway")


def _scope(auth: AuthContext) -> str:
    """Per-user scope for rate limits, cache, dedup, metrics — no shared buckets."""
    return f"user:{auth.user_id}"


def _uid(auth: AuthContext) -> uuid.UUID | None:
    return uuid.UUID(auth.user_id) if auth.user_id else None


class GatewayHandler:
    def __init__(
        self,
        router: Router,
        rate_limiter: RateLimiter,
        cache: SemanticCache,
        circuit_breakers: CircuitBreakerRegistry,
        deduplicator: RequestDeduplicator | None = None,
    ) -> None:
        s = get_settings()
        self.router = router
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.circuit_breakers = circuit_breakers
        self.rpm = s.default_rate_limit_rpm
        self.tpm = s.default_rate_limit_tpm
        self.conc = s.default_rate_limit_concurrent
        self.guard = PromptGuard()
        self.output_guard = PromptGuard(
            detect_secrets=True, detect_pii=False, detect_injection=False
        )
        self.dedup = deduplicator or RequestDeduplicator()

    async def handle_chat(
        self,
        request: ChatRequest,
        db: AsyncSession,
        auth: AuthContext,
        providers: list[Provider],
    ) -> ChatResponse:
        scope = _scope(auth)
        t0 = time.monotonic()
        try:
            return await self.dedup.execute(
                scope, request, self._handle_chat_inner, db, auth, providers
            )
        except Exception as exc:
            # ponytail: error-rate alerts need failures counted, not just successes
            metrics_collector.record_request(
                provider="gateway",
                model=request.model,
                status="error",
                team_id=scope,
                latency_s=time.monotonic() - t0,
            )
            if isinstance(exc, RateLimitExceeded):
                status_code = 429
            elif isinstance(exc, ValueError):
                status_code = 503
            else:
                status_code = 500
            await self._audit_failure(
                db, auth, request, status_code, f"{type(exc).__name__}: {exc}"
            )
            raise

    async def _handle_chat_inner(
        self,
        request: ChatRequest,
        db: AsyncSession,
        auth: AuthContext,
        providers: list[Provider],
    ) -> ChatResponse:
        request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        t0 = time.monotonic()
        scope = _scope(auth)

        # --- Rate limiting first: every authenticated request is metered, even
        # cache hits and guard violations ---
        await self.rate_limiter.check_rpm(f"{scope}:rpm", self.rpm)
        est_tokens = sum(len(flatten_text(m.content)) // 4 for m in request.messages)
        await self.rate_limiter.check_tpm(f"{scope}:tpm", self.tpm, est_tokens or 100)
        await self.rate_limiter.check_concurrent(f"{scope}:concurrent", self.conc)

        try:
            # --- Prompt guardrails (before cache: blocked models are never served) ---
            msg_dicts = [m.model_dump() for m in request.messages]
            try:
                self.guard.check(msg_dicts)
            except GuardrailViolation as e:
                log.warning("Guardrail violation: %s", e)
                metrics_collector.record_request(
                    provider="gateway",
                    model=request.model,
                    status="blocked",
                    team_id=scope,
                    latency_s=time.monotonic() - t0,
                )
                await self._audit_failure(
                    db, auth, request, 403, f"GuardrailViolation: {e.detail}"
                )
                return ChatResponse(
                    id=request_id,
                    model=request.model,
                    choices=[{
                        "index": 0,
                        "message": {"role": "assistant", "content": f"Request blocked: {e.detail}"},
                        "finish_reason": "stop",
                    }],
                    provider="gateway",
                    latency_ms=0,
                )

            # --- Semantic cache (per user: never serve another account's completion) ---
            cached = await self.cache.get(request, scope=scope)
            if cached:
                resp_data = dict(cached)  # cache.get() returns the response payload
                resp_data["cached"] = True
                resp_data["id"] = request_id
                saved = self._cache_savings(resp_data, providers, request.model)
                metrics_collector.record_cache_hit(cost_saved=saved)
                metrics_collector.record_request(
                    provider="gateway",
                    model=request.model,
                    status="cached",
                    team_id=scope,
                    latency_s=time.monotonic() - t0,
                )
                await self._audit_cached(db, request, resp_data, request_id, _uid(auth), saved)
                return ChatResponse(**resp_data)
            metrics_collector.record_cache_miss()

            # --- Route + call (candidates = this user's BYOK providers only).
            # route() performs the provider call (retry + breaker inside) and
            # returns the response — calling chat() again would double-spend.
            provider, response, fallback_from = await self.router.route(request, providers)

            response.id = request_id
            response.trace_id = request_id

            # --- Output guardrails (secrets only: models echoing keys is a leak,
            # PII/injection here would false-positive on legit discussion) ---
            out_text = " ".join(
                c.message.content or ""
                for c in response.choices
                if isinstance(getattr(c.message, "content", None), str)
            )
            try:
                self.output_guard.check([{"content": out_text}])
            except GuardrailViolation as e:
                log.warning("Output guardrail violation: %s", e)
                # provider already charged for these tokens — audit + metrics both count them
                cost = await self._audit_log(
                    db, request, response, provider, fallback_from, request_id, _uid(auth)
                )
                metrics_collector.record_request(
                    provider=provider.name,
                    model=request.model,
                    status="blocked",
                    team_id=scope,
                    latency_s=time.monotonic() - t0,
                    input_tokens=response.usage.prompt_tokens if response.usage else 0,
                    output_tokens=response.usage.completion_tokens if response.usage else 0,
                    cost=cost,
                )
                return ChatResponse(
                    id=request_id,
                    model=request.model,
                    choices=[{
                        "index": 0,
                        "message": {"role": "assistant", "content": f"Request blocked: {e.detail}"},
                        "finish_reason": "stop",
                    }],
                    provider="gateway",
                    latency_ms=0,
                )

            # --- Audit log ---
            finish_reason = response.choices[0].finish_reason if response.choices else None
            cost = await self._audit_log(
                db, request, response, provider, fallback_from, request_id, _uid(auth),
                finish_reason=finish_reason,
            )

            # --- Metrics ---
            total_latency = time.monotonic() - t0
            metrics_collector.record_request(
                provider=provider.name,
                model=request.model,
                status="success",
                team_id=scope,
                latency_s=total_latency,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                cost=cost,
            )
            if finish_reason:
                metrics_collector.record_finish_reason(provider.name, request.model, finish_reason)
            if fallback_from:
                metrics_collector.record_fallback(fallback_from, provider.name)

            # --- Cache store ---
            await self.cache.set(request, response.model_dump(), scope=scope)

            return response

        finally:
            await self.rate_limiter.release_concurrent(f"{scope}:concurrent")

    async def handle_stream(
        self,
        request: ChatRequest,
        db: AsyncSession,
        auth: AuthContext,
        providers: list[Provider],
    ) -> AsyncIterator[str]:
        request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        scope = _scope(auth)

        t0 = time.monotonic()
        t_first: float | None = None
        provider: Provider | None = None
        completed = False
        status_code = 500
        error: str | None = None
        usage: Usage | None = None
        served_model = request.model
        fallback_from: str | None = None
        finish_reason: str | None = None
        cost = 0.0
        acquired = False
        try:
            # Rate limits inside the try so stream 429s are metered + audited,
            # same as the non-stream path. Release only what was acquired.
            await self.rate_limiter.check_rpm(f"{scope}:rpm", self.rpm)
            est_tokens = sum(len(flatten_text(m.content)) // 4 for m in request.messages)
            await self.rate_limiter.check_tpm(f"{scope}:tpm", self.tpm, est_tokens or 100)
            await self.rate_limiter.check_concurrent(f"{scope}:concurrent", self.conc)
            acquired = True

            # --- Prompt guardrails ---
            msg_dicts = [m.model_dump() for m in request.messages]
            try:
                self.guard.check(msg_dicts)
            except GuardrailViolation as e:
                log.warning("Guardrail violation (stream): %s", e)
                status_code = 403
                error = f"GuardrailViolation: {e.detail}"
                yield f'data: {json.dumps({"error": e.detail})}\n\n'
                return

            # --- Route ---
            provider, fallback_from = await self.router.route_stream(request, providers)

            # span duration includes client backpressure; TTFT is set separately
            # from the first content chunk
            with tracer.start_as_current_span("llm.chat") as span:
                span.set_attribute("gen_ai.operation.name", "chat")
                span.set_attribute("gen_ai.provider.name", provider.name)
                span.set_attribute("gen_ai.request.model", request.model)
                span.set_attribute("reroute.stream", True)
                async for chunk in provider.stream(request):
                    # provider-reported usage rides the final chunk — streams
                    # were previously metered at zero tokens forever
                    if chunk.usage:
                        usage = chunk.usage
                    if chunk.model:
                        served_model = chunk.model
                    if chunk.choices:
                        c0 = chunk.choices[0]
                        if c0.finish_reason:
                            finish_reason = c0.finish_reason
                        # first content-bearing delta = first token
                        if t_first is None and c0.delta.get("content"):
                            t_first = time.monotonic()
                    yield f"data: {chunk.model_dump_json()}\n\n"
                span.set_attribute("gen_ai.response.model", served_model)
                if t_first is not None:
                    span.set_attribute(
                        "gen_ai.server.time_to_first_token", t_first - t0
                    )
                if finish_reason:
                    span.set_attribute("gen_ai.response.finish_reasons", [finish_reason])
                if usage:
                    span.set_attribute("gen_ai.usage.input_tokens", usage.prompt_tokens)
                    span.set_attribute("gen_ai.usage.output_tokens", usage.completion_tokens)
            yield "data: [DONE]\n\n"
            completed = True
            status_code = 200
        except RateLimitExceeded as exc:
            status_code = 429
            error = f"{type(exc).__name__}: {exc}"
            raise
        except ValueError as exc:
            status_code = 503
            error = f"{type(exc).__name__}: {exc}"
            raise
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            if acquired:
                await self.rate_limiter.release_concurrent(f"{scope}:concurrent")
            latency_s = time.monotonic() - t0
            ttft_s = (t_first - t0) if t_first is not None else None
            # tokens/sec = completion tokens over the post-first-token window
            tps: float | None = None
            if usage and ttft_s is not None and usage.completion_tokens:
                post_ttft = latency_s - ttft_s
                if post_ttft > 0:
                    tps = usage.completion_tokens / post_ttft
            if usage and provider:
                # billed even if the connection dropped mid-stream
                cost = provider.estimate_cost(
                    usage.prompt_tokens, usage.completion_tokens, request.model
                )
            metrics_collector.record_request(
                provider=provider.name if provider else "gateway",
                model=request.model,
                status=(
                    "success" if completed
                    else ("blocked" if status_code == 403 else "error")
                ),
                team_id=scope,
                latency_s=latency_s,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                cost=cost,
            )
            if provider and completed:
                metrics_collector.record_stream_timing(
                    provider.name, request.model, ttft_s, tps
                )
                if finish_reason:
                    metrics_collector.record_finish_reason(
                        provider.name, request.model, finish_reason
                    )
            if completed and fallback_from and provider:
                metrics_collector.record_fallback(fallback_from, provider.name)

            # Audit log for stream — written even on failure (provider may be
            # unset if we never routed). Failures never mask the original error.
            try:
                stmt = AuditLog.__table__.insert().values(
                    user_id=_uid(auth),
                    provider=provider.name if provider else "gateway",
                    model_requested=request.model,
                    model_served=served_model,
                    input_tokens=usage.prompt_tokens if usage else 0,
                    output_tokens=usage.completion_tokens if usage else 0,
                    cost_usd=cost,
                    is_stream=True,
                    latency_ms=latency_s * 1000,
                    ttft_ms=ttft_s * 1000 if ttft_s is not None else None,
                    tokens_per_sec=tps,
                    finish_reason=finish_reason,
                    fallback_from=fallback_from,
                    error_message=error[:500] if error else None,
                    prompt_hash=hashlib.sha256(
                        json.dumps(
                            [m.model_dump() for m in request.messages], sort_keys=True
                        ).encode()
                    ).hexdigest(),
                    trace_id=request_id,
                    status_code=status_code,
                )
                await db.execute(stmt)
                await db.commit()
            except Exception:
                log.exception("Failed to write stream audit row")

    async def _audit_failure(
        self,
        db: AsyncSession,
        auth: AuthContext,
        request: ChatRequest,
        status_code: int,
        error: str,
    ) -> None:
        """Failures and guard blocks must still appear in activity/analytics.
        Failures never fail the response."""
        try:
            # a failed insert elsewhere leaves the session mid-transaction; without
            # clearing it this commit raises PendingRollbackError and the request
            # vanishes from every dashboard graph
            await db.rollback()
            db.add(
                AuditLog(
                    user_id=_uid(auth),
                    provider="gateway",
                    model_requested=request.model,
                    model_served=request.model,
                    status_code=status_code,
                    error_message=error[:500],
                )
            )
            await db.commit()
        except Exception:
            log.exception("Failed to write failure audit row")

    async def _audit_log(
        self,
        db: AsyncSession,
        request: ChatRequest,
        response: ChatResponse,
        provider: Provider,
        fallback_from: str | None,
        trace_id: str,
        user_id: uuid.UUID | None,
        finish_reason: str | None = None,
    ) -> float:
        """Write the success audit row; returns the cost so the caller reports
        the same number to Prometheus."""
        cost = 0.0
        if response.usage:
            cost = provider.estimate_cost(
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                request.model,
            )

        log_entry = AuditLog(
            user_id=user_id,
            provider=provider.name,
            model_requested=request.model,
            model_served=response.model,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            cost_usd=cost,
            latency_ms=response.latency_ms,
            finish_reason=finish_reason,
            prompt_hash=hashlib.sha256(
                json.dumps(
                    [m.model_dump() for m in request.messages], sort_keys=True
                ).encode()
            ).hexdigest(),
            fallback_from=fallback_from,
            trace_id=trace_id,
            status_code=200,
        )
        db.add(log_entry)
        await db.commit()
        return cost

    @staticmethod
    def _cache_savings(
        resp_data: dict, providers: list[Provider], model: str
    ) -> float:
        """What a cache hit would have cost if served by the provider — the $ saved.

        ponytail: best-effort — needs the original provider still connected;
        unknown provider or missing usage = 0 saved (still a latency win).
        """
        usage = resp_data.get("usage")
        if not usage:
            return 0.0
        prov = next(
            (p for p in providers if p.name == (resp_data.get("provider") or "")), None
        )
        if prov is None:
            return 0.0
        return prov.estimate_cost(
            usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), model
        )

    async def _audit_cached(
        self,
        db: AsyncSession,
        request: ChatRequest,
        resp_data: dict,
        trace_id: str,
        user_id: uuid.UUID | None,
        cache_saved_usd: float = 0.0,
    ) -> None:
        """Cache hits must still appear in activity/analytics.

        Tokens/cost stay 0 — already counted on the original request.
        cache_saved_usd records what the hit avoided. Failures never fail
        the response.
        """
        try:
            db.add(
                AuditLog(
                    user_id=user_id,
                    provider=resp_data.get("provider") or "gateway",
                    model_requested=request.model,
                    model_served=resp_data.get("model") or request.model,
                    input_tokens=0,  # already counted on the original request
                    output_tokens=0,
                    cost_usd=0.0,
                    is_cached=True,
                    cache_saved_usd=cache_saved_usd,
                    prompt_hash=hashlib.sha256(
                        json.dumps(
                            [m.model_dump() for m in request.messages], sort_keys=True
                        ).encode()
                    ).hexdigest(),
                    trace_id=trace_id,
                    status_code=200,
                )
            )
            await db.commit()
        except Exception:
            log.exception("Failed to write cache-hit audit row")
