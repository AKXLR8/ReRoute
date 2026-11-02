"""Delete audit rows older than AUDIT_RETENTION_DAYS.

Dry-run by default; pass --apply to delete. Run from backend/:
    python scripts/purge_audit.py
    python scripts/purge_audit.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from reroute.config import get_settings
from reroute.database import dispose_engine, get_session_factory
from reroute.models.audit_log import AuditLog


async def main(days: int | None, apply: bool) -> None:
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(days=days or settings.audit_retention_days)
    async with get_session_factory()() as db:
        count = await db.scalar(
            select(func.count()).select_from(AuditLog).where(AuditLog.timestamp < cutoff)
        )
        print(f"cutoff={cutoff.isoformat()} rows={count} apply={apply}")
        if apply and count:
            await db.execute(delete(AuditLog).where(AuditLog.timestamp < cutoff))
            await db.commit()
            print("deleted")
    await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.days, args.apply))
