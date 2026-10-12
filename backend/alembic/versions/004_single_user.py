"""single-user BYOK — drop teams/keys/budgets/life; global provider keys

Revision ID: 004
Revises: 003
Create Date: 2026-10-02 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("life_entries")
    op.drop_table("budget_usage")
    op.drop_table("api_keys")

    # team_provider_keys -> provider_keys: one global row per provider
    op.create_table(
        "provider_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False, unique=True),
        sa.Column("api_key_encrypted", sa.Text, nullable=False, server_default=""),
        sa.Column("base_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.execute(
        """
        INSERT INTO provider_keys (id, provider, api_key_encrypted, base_url, created_at, updated_at)
        SELECT DISTINCT ON (provider) id, provider, api_key_encrypted, base_url, created_at, updated_at
        FROM team_provider_keys
        ORDER BY provider, updated_at DESC
        """
    )
    op.drop_table("team_provider_keys")

    op.drop_table("teams")

    op.drop_index("ix_audit_logs_team_id", table_name="audit_logs")
    op.drop_column("audit_logs", "team_id")
    op.drop_column("audit_logs", "api_key_id")


def downgrade() -> None:
    op.add_column("audit_logs", sa.Column("team_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("audit_logs", sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_audit_logs_team_id", "audit_logs", ["team_id"])

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
    op.create_table(
        "life_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("day", sa.Date, nullable=False, unique=True),
        sa.Column("sleep_hours", sa.Float, nullable=False),
        sa.Column("screen_time_min", sa.Integer, nullable=False),
        sa.Column("calendar_min", sa.Integer, nullable=False),
        sa.Column("mood", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "team_provider_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("api_key_encrypted", sa.Text, nullable=False, server_default=""),
        sa.Column("base_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("team_id", "provider", name="uq_team_provider"),
    )
    op.create_index("ix_team_provider_keys_team_id", "team_provider_keys", ["team_id"])
