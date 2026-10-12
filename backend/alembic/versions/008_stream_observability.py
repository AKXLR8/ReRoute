"""stream observability — audit_logs.ttft_ms + tokens_per_sec + finish_reason + cache_saved_usd

Revision ID: 008
Revises: 007
Create Date: 2026-10-10 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("ttft_ms", sa.Float(), nullable=True))
    op.add_column("audit_logs", sa.Column("tokens_per_sec", sa.Float(), nullable=True))
    op.add_column("audit_logs", sa.Column("finish_reason", sa.String(32), nullable=True))
    op.add_column("audit_logs", sa.Column("cache_saved_usd", sa.Float(), nullable=True, server_default="0"))


def downgrade() -> None:
    op.drop_column("audit_logs", "cache_saved_usd")
    op.drop_column("audit_logs", "finish_reason")
    op.drop_column("audit_logs", "tokens_per_sec")
    op.drop_column("audit_logs", "ttft_ms")
