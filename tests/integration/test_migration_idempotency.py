"""Migration round-trip test: upgrade → downgrade → upgrade cleanly.

This guards against migrations that forget a ``drop_index`` or leave
the schema in a state that cannot be rebuilt from scratch. Running on
a dedicated throwaway database keeps the ``dharma_test`` state used by
the other integration tests untouched.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

# Local dev-only credentials for the ``dharma-db`` docker-compose service.
_ADMIN_URL = (
    "postgresql+psycopg://dharma:dharma_dev@localhost:5432/postgres"  # pragma: allowlist secret
)
_ROUNDTRIP_DB = "dharma_roundtrip"
_ROUNDTRIP_URL_ASYNC = f"postgresql+asyncpg://dharma:dharma_dev@localhost:5432/{_ROUNDTRIP_DB}"  # pragma: allowlist secret


def test_upgrade_downgrade_upgrade_is_clean(_postgres_available: None) -> None:
    """Full migration round-trip should not error.

    Uses a throwaway DB so nothing else is affected. The test is
    synchronous — Alembic itself runs sync operations, so there is no
    reason to involve an event loop here.
    """
    admin_engine = sa.create_engine(_ADMIN_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{_ROUNDTRIP_DB}" WITH (FORCE)'))
            conn.execute(sa.text(f'CREATE DATABASE "{_ROUNDTRIP_DB}"'))

        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", _ROUNDTRIP_URL_ASYNC)

        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")

        # Sanity: the re-applied migration should still seed traditions.
        sync_url = _ROUNDTRIP_URL_ASYNC.replace("+asyncpg", "+psycopg")
        check_engine = sa.create_engine(sync_url)
        with check_engine.connect() as conn:
            traditions = conn.execute(sa.text("SELECT COUNT(*) FROM tradition_t")).scalar()
        check_engine.dispose()
        assert traditions == 7, f"Expected 7 traditions seeded after re-upgrade, got {traditions}"
    finally:
        with admin_engine.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{_ROUNDTRIP_DB}" WITH (FORCE)'))
        admin_engine.dispose()
