"""Observability — Prometheus scrape endpoint + OpenTelemetry tracing.

Tracing is opt-in: set OTEL_EXPORTER_OTLP_ENDPOINT (OTLP/HTTP collector,
port 4318) and every request gets a server span plus per-provider `llm.chat`
spans. Without it, setup is a no-op and Prometheus /metrics still works.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from fastapi import FastAPI
    from opentelemetry.sdk.trace import TracerProvider

log = logging.getLogger(__name__)

_provider: TracerProvider | None = None  # set only when tracing is enabled


async def prometheus_endpoint(request: Request) -> Response:
    """Expose all Prometheus metrics at /metrics."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def setup_telemetry(app: FastAPI) -> None:
    """Wire OTLP export + FastAPI request spans. No-op unless an endpoint is set."""
    from ..config import get_settings

    s = get_settings()
    endpoint = s.otel_exporter_otlp_endpoint.strip()
    if not endpoint:
        log.info("Tracing disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # Accept either the collector base URL or the full traces URL.
    url = endpoint.rstrip("/")
    if not url.endswith("/v1/traces"):
        url += "/v1/traces"

    global _provider
    provider = TracerProvider(
        resource=Resource.create({"service.name": s.otel_service_name}),
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=url)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    _provider = provider
    log.info("Tracing enabled → %s (service=%s)", url, s.otel_service_name)


def shutdown() -> None:
    """Flush pending spans and stop the processor. Safe when tracing is off."""
    global _provider
    if _provider is not None:
        _provider.shutdown()
        _provider = None
