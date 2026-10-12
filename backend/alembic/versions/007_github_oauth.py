"""github oauth — users.oauth_provider + users.oauth_id

Revision ID: 007
Revises: 006
Create Date: 2026-10-07 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("oauth_provider", sa.String(16), nullable=True))
    op.add_column("users", sa.Column("oauth_id", sa.String(64), nullable=True))
    # unique: one GitHub account may link to at most one user (NULLs don't collide)
    op.create_index("ix_users_oauth_id", "users", ["oauth_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_oauth_id", table_name="users")
    op.drop_column("users", "oauth_id")
    op.drop_column("users", "oauth_provider")
