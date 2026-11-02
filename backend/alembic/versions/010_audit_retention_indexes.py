"""audit dedup flag + composite indexes

Revision ID: 010
Revises: 009
Create Date: 2026-11-01 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("is_deduped", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # admin/member log pages filter by user then order by newest first
    op.create_index(
        "ix_audit_logs_user_id_timestamp",
        "audit_logs",
        ["user_id", "timestamp"],
    )
    # analytics group/filter by provider over a time window
    op.create_index(
        "ix_audit_logs_timestamp_provider",
        "audit_logs",
        ["timestamp", "provider"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_timestamp_provider", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id_timestamp", table_name="audit_logs")
    op.drop_column("audit_logs", "is_deduped")
