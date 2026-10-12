"""OpenTelemetry wiring — opt-in, enabled only via OTEL_EXPORTER_OTLP_ENDPOINT."""

from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace

from reroute.config import Settings
from reroute.observability import telemetry


def _settings(endpoint: str) -> Settings:
    return Settings(otel_exporter_otlp_endpoint=endpoint, _env_file=None)


def test_setup_is_noop_without_endpoint(monkeypatch):
    monkeypatch.setattr("reroute.config.get_settings", lambda: _settings(""))
    telemetry.setup_telemetry(FastAPI())
    assert telemetry._provider is None


def test_setup_wires_provider_and_records_spans(monkeypatch):
    captured: dict[str, str] = {}

    class FakeExporter:  # no network in tests — assert on the URL instead
        def __init__(self, endpoint: str | None = None, **_: object) -> None:
            captured["endpoint"] = endpoint or ""

        def export(self, _spans: object) -> object:
            return None

        def force_flush(self, timeout_millis: int = 30_000) -> bool:
            return True

        def shutdown(self) -> None:
            return None

    monkeypatch.setattr(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
        FakeExporter,
    )
    monkeypatch.setattr(
        "reroute.config.get_settings", lambda: _settings("http://localhost:4318")
    )

    telemetry.setup_telemetry(FastAPI())
    try:
        assert telemetry._provider is not None
        # collector base URL is expanded to the traces path
        assert captured["endpoint"] == "http://localhost:4318/v1/traces"

        with trace.get_tracer("test").start_as_current_span("llm.chat") as span:
            span.set_attribute("gen_ai.provider.name", "openai")
            trace_id = span.get_span_context().trace_id
        assert trace_id != 0  # spans are recorded, not no-ops
    finally:
        telemetry.shutdown()
    assert telemetry._provider is None
