"""Delete expired refresh tokens and revoked ones older than the retention window.

Dry-run by default; pass --apply to delete. Run from backend/:
    python scripts/purge_refresh_tokens.py
    python scripts/purge_refresh_tokens.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, or_, select

from reroute.config import get_settings
from reroute.database import dispose_engine, get_session_factory
from reroute.models.user import RefreshToken


async def main(days: int | None, apply: bool) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=days or settings.refresh_token_retention_days)
    condition = or_(
        RefreshToken.expires_at < now,
        RefreshToken.revoked_at < cutoff,
    )
    async with get_session_factory()() as db:
        count = await db.scalar(
            select(func.count()).select_from(RefreshToken).where(condition)
        )
        print(f"cutoff={cutoff.isoformat()} rows={count} apply={apply}")
        if apply and count:
            await db.execute(delete(RefreshToken).where(condition))
            await db.commit()
            print("deleted")
    await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.days, args.apply))
