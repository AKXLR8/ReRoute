"""Alembic env — async support for SQLAlchemy 2."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Same source of truth as the app: pydantic Settings (reads backend/.env),
# incl. the sslmode -> ssl-context mapping asyncpg needs for Neon-style URLs.
from reroute.config import get_settings  # noqa: E402
from reroute.database import _build_async_engine_url_and_args  # noqa: E402

_clean_url, _connect_args = _build_async_engine_url_and_args(get_settings().database_url)
config.set_main_option("sqlalchemy.url", _clean_url)

# Import models so Alembic can detect them
import reroute.models  # noqa: E402, F401
from reroute.models.base import Base  # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(
        _clean_url, poolclass=pool.NullPool, connect_args=_connect_args
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
