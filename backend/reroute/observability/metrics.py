"""Prometheus metrics — lightweight, no external deps beyond prometheus_client."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# --- Counters ---
REQUEST_TOTAL = Counter(
    "forge_requests_total",
    "Total requests processed",
    ["provider", "model", "status"],
)

TOKENS_TOTAL = Counter(
    "forge_tokens_total",
    "Total tokens consumed",
    ["provider", "model", "direction"],
)

COST_TOTAL = Counter(
    "forge_cost_usd_total",
    "Total cost in USD",
    ["provider", "model"],
)

RETRY_TOTAL = Counter(
    "forge_retries_total",
    "Total retry attempts",
    ["provider", "model"],
)

FALLBACK_TOTAL = Counter(
    "forge_fallbacks_total",
    "Total fallback occurrences",
    ["from_provider", "to_provider"],
)

CACHE_HITS = Counter(
    "forge_cache_hits_total",
    "Semantic cache hits",
)

CACHE_MISSES = Counter(
    "forge_cache_misses_total",
    "Semantic cache misses",
)

CACHE_SAVINGS = Counter(
    "forge_cache_savings_usd_total",
    "Estimated USD saved by semantic cache hits",
)

FINISH_REASON_TOTAL = Counter(
    "forge_finish_reasons_total",
    "Completion finish reasons (stop/length/content_filter/...)",
    ["provider", "model", "reason"],
)

# --- Histograms ---
REQUEST_LATENCY = Histogram(
    "forge_request_latency_seconds",
    "Request latency in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

TTFT = Histogram(
    "forge_ttft_seconds",
    "Time to first token on streams, in seconds",
    ["provider", "model"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

TOKENS_PER_SEC = Histogram(
    "forge_output_tokens_per_second",
    "Output tokens per second during streaming",
    ["provider", "model"],
    buckets=(1.0, 5.0, 10.0, 20.0, 40.0, 80.0, 160.0, 320.0),
)

# --- Gauges ---
CONCURRENT_REQUESTS = Gauge(
    "forge_concurrent_requests",
    "Currently in-flight requests",
)

CIRCUIT_BREAKER_STATE = Gauge(
    "forge_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["provider"],
)

PROVIDER_HEALTH = Gauge(
    "forge_provider_health",
    "Provider health (1=healthy, 0=unhealthy)",
    ["provider"],
)


_MAX_LABEL_VALUES = 256
_known_models: set[str] = set()
_known_reasons: set[str] = set()


def _bounded(value: str, seen: set[str] | None = None) -> str:
    """Keep request-controlled labels from growing Prometheus memory forever."""
    value = (value or "unknown")[:128]
    if seen is None:
        return value
    if value in seen:
        return value
    if len(seen) >= _MAX_LABEL_VALUES:
        return "other"
    seen.add(value)
    return value


class MetricsCollector:
    """Thin wrapper so the rest of the code imports one thing."""

    def register_models(self, models: list[str]) -> None:
        """Pre-seed legitimate model names before traffic can invent labels."""
        for model in models:
            _bounded(model, _known_models)

    def record_request(
        self,
        provider: str,
        model: str,
        status: str,
        team_id: str | None = None,
        latency_s: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
    ) -> None:
        # team_id is intentionally ignored: per-user UUID labels are unbounded
        # and per-user analytics already live in Postgres.
        model = _bounded(model, _known_models)
        REQUEST_TOTAL.labels(provider=provider, model=model, status=status).inc()
        REQUEST_LATENCY.labels(provider=provider, model=model).observe(latency_s)
        if input_tokens:
            TOKENS_TOTAL.labels(
                provider=provider, model=model, direction="input"
            ).inc(input_tokens)
        if output_tokens:
            TOKENS_TOTAL.labels(
                provider=provider, model=model, direction="output"
            ).inc(output_tokens)
        if cost:
            COST_TOTAL.labels(provider=provider, model=model).inc(cost)

    def record_retry(self, provider: str, model: str) -> None:
        RETRY_TOTAL.labels(provider=provider, model=_bounded(model, _known_models)).inc()

    def record_fallback(self, from_provider: str, to_provider: str) -> None:
        FALLBACK_TOTAL.labels(from_provider=from_provider, to_provider=to_provider).inc()

    def record_cache_hit(self, cost_saved: float = 0.0) -> None:
        CACHE_HITS.inc()
        if cost_saved:
            CACHE_SAVINGS.inc(cost_saved)

    def record_cache_miss(self) -> None:
        CACHE_MISSES.inc()

    def record_stream_timing(
        self, provider: str, model: str, ttft_s: float | None, tps: float | None
    ) -> None:
        model = _bounded(model, _known_models)
        if ttft_s is not None:
            TTFT.labels(provider=provider, model=model).observe(ttft_s)
        if tps is not None:
            TOKENS_PER_SEC.labels(provider=provider, model=model).observe(tps)

    def record_finish_reason(self, provider: str, model: str, reason: str) -> None:
        model = _bounded(model, _known_models)
        reason = _bounded(reason, _known_reasons)
        FINISH_REASON_TOTAL.labels(provider=provider, model=model, reason=reason).inc()

    def set_circuit_breaker(self, provider: str, state: int) -> None:
        CIRCUIT_BREAKER_STATE.labels(provider=provider).set(state)

    def set_provider_health(self, provider: str, healthy: bool) -> None:
        PROVIDER_HEALTH.labels(provider=provider).set(1 if healthy else 0)


metrics_collector = MetricsCollector()
