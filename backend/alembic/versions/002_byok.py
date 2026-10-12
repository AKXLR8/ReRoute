"""team_provider_keys — BYOK

Revision ID: 002
Revises: 001
Create Date: 2026-09-27 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team_provider_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("api_key_encrypted", sa.Text, nullable=False, server_default=""),
        sa.Column("base_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("team_id", "provider", name="uq_team_provider"),
    )
    op.create_index("ix_team_provider_keys_team_id", "team_provider_keys", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_team_provider_keys_team_id", table_name="team_provider_keys")
    op.drop_table("team_provider_keys")
