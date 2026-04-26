"""Alembic environment for Dharma-RAG.

Runs migrations with SQLAlchemy's async engine. We swap the asyncpg
driver for psycopg 3 only when running in offline mode (no live
connection), matching the pattern described in the SQLAlchemy docs.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Importing the models package registers every table on Base.metadata.
from src.config import get_settings
from src.db import (
    Base,
    models,  # noqa: F401 — register models on Base.metadata
)

config = context.config

# Feed the logging section declared in alembic.ini into Python's logger.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# URL resolution order:
#   1. Whatever the caller set via ``cfg.set_main_option`` (tests override here).
#   2. Otherwise, ``DATABASE_URL`` from the environment via Settings.
#
# We previously overwrote the URL unconditionally with Settings, which
# meant ``command.upgrade(cfg, ...)`` ignored any caller override and
# silently ran migrations against the main database. Tests now need the
# ability to target a throwaway DB without mutating env vars.
_cfg_url = config.get_main_option("sqlalchemy.url")
if not _cfg_url:
    _cfg_url = get_settings().database_url
    config.set_main_option("sqlalchemy.url", _cfg_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL statements to stdout without connecting to the database.

    Useful for review in code review and for applying DDL via a DBA.
    We swap the asyncpg driver for psycopg 3 because offline mode does
    not actually open a connection, but Alembic still parses the URL to
    select a dialect and asyncpg's scheme is async-only.
    """
    url = _cfg_url.replace("+asyncpg", "+psycopg")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Connect via asyncpg and run migrations inside a transaction."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
