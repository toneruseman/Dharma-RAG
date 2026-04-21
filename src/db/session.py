"""Async engine and session factory singletons.

Runtime code should prefer the ``get_sessionmaker()`` helper; tests can
replace the engine via the ``_reset_engine_for_tests()`` utility.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return the process-wide async engine.

    We cache at module level so every request reuses the connection pool
    built by asyncpg. Pool sizing is intentionally conservative for the
    €9 Hetzner tier; adjust when we move to CX42.
    """
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide async session factory."""
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        class_=AsyncSession,
    )


def _reset_engine_for_tests() -> None:
    """Clear cached engine/sessionmaker — used by test fixtures."""
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
