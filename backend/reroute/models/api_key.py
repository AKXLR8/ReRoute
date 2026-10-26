"""Per-user gateway API keys - the credential apps use to call /v1.

Only the SHA-256 of the key is stored (same scheme as refresh tokens); the raw
value is shown once at creation. Revocation is immediate: auth re-reads the row
on every request, so a killed key stops working on the next call.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ApiKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # sha256 hex of the raw key - never the raw value
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # display form, e.g. rr_live_ab12 - enough to tell keys apart, useless to guess
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
