"""Immutable audit log — append-only table for every gateway request."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # per-user spend attribution; NULL for legacy/system rows (user deleted)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_requested: Mapped[str] = mapped_column(String(128), nullable=False)
    model_served: Mapped[str] = mapped_column(String(128), nullable=False)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    # stream speed: time to first token (streams only) and output tokens/sec
    ttft_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    tokens_per_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # what a cache hit would have cost if served from the provider
    cache_saved_usd: Mapped[float] = mapped_column(Float, default=0.0)

    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completion_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    is_stream: Mapped[bool] = mapped_column(default=False)
    is_cached: Mapped[bool] = mapped_column(default=False)
    fallback_from: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    status_code: Mapped[int] = mapped_column(Integer, default=200)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    extra: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
