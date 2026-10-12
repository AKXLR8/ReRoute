"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Teams
    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), unique=True, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("monthly_budget_usd", sa.Float, nullable=False, server_default=sa.text("1000.0")),
        sa.Column("daily_budget_usd", sa.Float, nullable=False, server_default=sa.text("100.0")),
        sa.Column("rate_limit_rpm", sa.Integer, nullable=False, server_default=sa.text("60")),
        sa.Column("rate_limit_tpm", sa.Integer, nullable=False, server_default=sa.text("100000")),
        sa.Column("rate_limit_concurrent", sa.Integer, nullable=False, server_default=sa.text("10")),
        sa.Column("allowed_providers", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("allowed_models", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("priority", sa.Integer, nullable=False, server_default=sa.text("5")),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # API Keys
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_hash", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False, server_default="default"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("rate_limit_rpm", sa.Integer, nullable=True),
        sa.Column("rate_limit_tpm", sa.Integer, nullable=True),
        sa.Column("rate_limit_concurrent", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])

    # Audit Logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model_requested", sa.String(128), nullable=False),
        sa.Column("model_served", sa.String(128), nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("latency_ms", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("prompt_hash", sa.String(64), nullable=True),
        sa.Column("completion_hash", sa.String(64), nullable=True),
        sa.Column("is_stream", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_cached", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("fallback_from", sa.String(64), nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("status_code", sa.Integer, nullable=False, server_default=sa.text("200")),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("extra", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_team_id", "audit_logs", ["team_id"])
    op.create_index("ix_audit_logs_trace_id", "audit_logs", ["trace_id"])

    # Budget Usage
    op.create_table(
        "budget_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usage_date", sa.Date, nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("total_cost_usd", sa.Float, nullable=False, server_default=sa.text("0.0")),
        sa.Column("request_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("team_id", "usage_date", name="uq_team_daily_budget"),
    )


def downgrade() -> None:
    op.drop_table("budget_usage")
    op.drop_table("audit_logs")
    op.drop_table("api_keys")
    op.drop_table("teams")
