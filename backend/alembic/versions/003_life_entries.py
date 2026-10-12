"""life_entries — AI Life Dashboard metrics

Revision ID: 003
Revises: 002
Create Date: 2026-10-02 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("life_entries")
