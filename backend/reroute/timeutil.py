"""Time helpers — all business-day boundaries are UTC, everywhere."""

from __future__ import annotations

from datetime import UTC, date, datetime


def utc_today() -> date:
    """Today's date in UTC. Never date.today() (server-local zone varies)."""
    return datetime.now(UTC).date()
