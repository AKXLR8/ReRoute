"""Tests for SQLAlchemy models — verify column defaults."""

from reroute.models.audit_log import AuditLog
from reroute.models.provider_key import ProviderKey


def test_provider_key_fields():
    cols = {c.name for c in ProviderKey.__table__.columns}
    assert "provider" in cols
    assert "api_key_encrypted" in cols
    assert "base_url" in cols
    assert "created_at" in cols


def test_audit_log_fields():
    log_entry = AuditLog(
        provider="openai",
        model_requested="gpt-4o",
        model_served="gpt-4o",
    )
    assert log_entry.provider == "openai"
    assert log_entry.model_requested == "gpt-4o"
    assert log_entry.model_served == "model_served" or log_entry.model_served == "gpt-4o"
    cols = {c.name for c in AuditLog.__table__.columns}
    assert "input_tokens" in cols
    assert "output_tokens" in cols
    assert "cost_usd" in cols
    assert "latency_ms" in cols
    assert "is_stream" in cols
    assert "is_cached" in cols
    assert "fallback_from" in cols
    assert "retry_count" in cols
    assert "trace_id" in cols
