"""Async SQLAlchemy engine & session factory.

Lazy — env vars are read on first use, not at import time.
"""

from __future__ import annotations

import ssl
from urllib.parse import parse_qs, urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_async_engine_url_and_args(url: str) -> tuple[str, dict]:
    """Parse PostgreSQL URL, extract asyncpg connect args, return clean URL + connect_args."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    connect_args = {}

    # Handle SSL
    sslmode = query.get("sslmode", [None])[0]
    if sslmode in ("require", "verify-ca", "verify-full"):
        ssl_ctx = ssl.create_default_context()
        if sslmode == "verify-full":
            ssl_ctx.check_hostname = True
            ssl_ctx.verify_mode = ssl.CERT_REQUIRED
        elif sslmode == "verify-ca":
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_REQUIRED
        else:  # require
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    # channel_binding is handled by asyncpg automatically when ssl is set

    # Rebuild URL without query params that asyncpg doesn't understand
    clean_query = {
        k: v for k, v in query.items()
        if k not in ("sslmode", "channel_binding")
    }
    clean_parsed = parsed._replace(query="&".join(f"{k}={v[0]}" for k, v in clean_query.items()))
    clean_url = urlunparse(clean_parsed)

    return clean_url, connect_args


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        clean_url, connect_args = _build_async_engine_url_and_args(settings.database_url)
        _engine = create_async_engine(
            clean_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,
            echo=settings.debug,
            connect_args=connect_args,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def dispose_engine() -> None:
    """Dispose the engine (call on shutdown). Resets so tests can re-init."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with get_session_factory()() as session:
        yield session
