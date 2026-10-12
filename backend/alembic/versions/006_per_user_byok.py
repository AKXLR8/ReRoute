"""per-user BYOK — provider_keys.user_id + audit_logs.user_id

Revision ID: 006
Revises: 005
Create Date: 2026-10-04 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # provider_keys: one row per (user, provider); existing rows belong to the oldest admin
    op.add_column("provider_keys", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        """
        UPDATE provider_keys SET user_id = (
            SELECT id FROM users WHERE role = 'admin' ORDER BY created_at ASC LIMIT 1
        )
        """
    )
    op.execute("DELETE FROM provider_keys WHERE user_id IS NULL")  # orphans: no admin to inherit
    op.alter_column("provider_keys", "user_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_constraint("provider_keys_provider_key", "provider_keys", type_="unique")
    op.create_unique_constraint("uq_provider_keys_user_provider", "provider_keys", ["user_id", "provider"])
    op.create_foreign_key(
        "fk_provider_keys_user", "provider_keys", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )

    # audit_logs: per-user spend attribution (NULL = legacy/system row)
    op.add_column("audit_logs", sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_foreign_key(
        "fk_audit_logs_user", "audit_logs", "users", ["user_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_audit_logs_user", "audit_logs", type_="foreignkey")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_column("audit_logs", "user_id")

    op.drop_constraint("fk_provider_keys_user", "provider_keys", type_="foreignkey")
    op.drop_constraint("uq_provider_keys_user_provider", "provider_keys", type_="unique")
    op.create_unique_constraint("provider_keys_provider_key", "provider_keys", ["provider"])
    op.drop_column("provider_keys", "user_id")
