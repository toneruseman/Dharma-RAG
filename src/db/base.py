"""Declarative base and shared column mixins for all Dharma-RAG tables.

Keeping ``Base`` isolated from the session factory lets Alembic import it
without side-effects (no async engine is created just to load metadata).
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):  # type: ignore[misc]
    """Declarative base for every Dharma-RAG ORM model.

    All tables created through this base share a single ``MetaData``
    instance, which is what Alembic's ``target_metadata`` points at.
    """


class TimestampMixin:
    """Add ``created_at`` / ``updated_at`` columns with server-side defaults.

    Server-side defaults (``server_default``) ensure the timestamps are
    populated even when rows are inserted by non-ORM paths such as
    Alembic data migrations or raw ``COPY``.
    """

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )
