"""Fixtures for integration tests that require a live Postgres.

The RAG-track integration tests exercise the real Alembic migrations
against the ``dharma-db`` container from ``docker-compose.yml``. To
avoid clobbering the developer's main database we create a separate
``dharma_test`` database and run every migration there once per test
session, then truncate non-seed tables between individual tests.

Running without Docker:
- If Postgres is unreachable, every test in this package is skipped
  with a clear message rather than producing a confusing stack trace.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from alembic.config import Config

# Local dev-only credentials for the ``dharma-db`` docker-compose service.
# These are default placeholders documented in ``.env.example``; real
# deployments override them via environment variables.
ADMIN_URL_SYNC = (
    "postgresql+psycopg://dharma:dharma_dev@localhost:5432/postgres"  # pragma: allowlist secret
)
DHARMA_URL_SYNC = (
    "postgresql+psycopg://dharma:dharma_dev@localhost:5432/dharma"  # pragma: allowlist secret
)
TEST_DB_NAME = "dharma_test"
TEST_DB_URL_ASYNC = f"postgresql+asyncpg://dharma:dharma_dev@localhost:5432/{TEST_DB_NAME}"  # pragma: allowlist secret
TEST_DB_URL_SYNC = f"postgresql+psycopg://dharma:dharma_dev@localhost:5432/{TEST_DB_NAME}"  # pragma: allowlist secret

# Non-seed tables that every test is allowed to mutate. Lookup tables
# (``tradition_t``, ``language_t``) are seeded by migration 001 and
# must survive across tests so that FK references keep working.
MUTABLE_TABLES: tuple[str, ...] = (
    "chunk",
    "instance",
    "expression",
    "work",
    "author_t",
)


@pytest.fixture(scope="session")
def _postgres_available() -> Iterator[None]:
    """Skip the whole package if Postgres is unreachable."""
    try:
        engine = sa.create_engine(ADMIN_URL_SYNC, connect_args={"connect_timeout": 2})
        with engine.connect():
            pass
        engine.dispose()
    except Exception as exc:
        pytest.skip(
            "dharma-db Postgres is unreachable — run `docker compose up -d "
            f"dharma-db` to enable integration tests. (error: {exc})"
        )
    yield


@pytest.fixture(scope="session")
def _test_database(_postgres_available: None) -> Iterator[None]:
    """Create ``dharma_test`` database once per session, drop on teardown.

    We connect to the ``postgres`` maintenance DB with AUTOCOMMIT because
    ``CREATE DATABASE`` / ``DROP DATABASE`` cannot run inside a
    transaction in PostgreSQL.
    """
    admin_engine = sa.create_engine(ADMIN_URL_SYNC, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        # Drop any stale test DB from a previous interrupted run.
        conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'))
        conn.execute(sa.text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    admin_engine.dispose()

    yield

    admin_engine = sa.create_engine(ADMIN_URL_SYNC, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)'))
    admin_engine.dispose()


@pytest.fixture(scope="session")
def _migrated(_test_database: None) -> Iterator[None]:
    """Run ``alembic upgrade head`` against the test database."""
    cfg = Config("alembic.ini")
    # Override the URL so Alembic points at ``dharma_test``, not ``dharma``.
    os.environ["DATABASE_URL"] = TEST_DB_URL_ASYNC
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL_ASYNC)
    command.upgrade(cfg, "head")
    yield


@pytest_asyncio.fixture
async def engine(_migrated: None) -> AsyncIterator[AsyncEngine]:
    """Function-scoped async engine pointed at ``dharma_test``.

    Function scope is required because pytest-asyncio's default event
    loop is also function-scoped; a session-scoped asyncpg engine lives
    on a loop that no longer exists by the time a test runs. The cost
    of reconnecting per test is small compared to the complexity of
    matching loop scopes everywhere.
    """
    eng = create_async_engine(TEST_DB_URL_ASYNC, echo=False, future=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Provide an ``AsyncSession`` with per-test cleanup of mutable tables.

    Tests are free to ``commit()``; the post-test TRUNCATE restores a
    clean state. Lookup tables keep their seed data because many ORM
    constraints reference them.
    """
    session_maker = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with session_maker() as session:
        yield session

    # Restart identity to keep sequence state predictable between tests.
    async with engine.begin() as conn:
        await conn.execute(
            sa.text("TRUNCATE TABLE " + ", ".join(MUTABLE_TABLES) + " RESTART IDENTITY CASCADE")
        )
