"""Database layer: SQLAlchemy models, session factory, and migrations glue.

The module is split so that Alembic can import ``Base.metadata`` without
pulling in the async engine, and so runtime code can obtain sessions
without re-importing the model registry.

Public surface:

- ``Base`` — the declarative base that all models inherit from.
- ``get_engine`` / ``get_sessionmaker`` — async engine and session
  factory singletons.
- ``models`` submodule — re-exports every ORM class.
"""

from __future__ import annotations

from src.db.base import Base, TimestampMixin
from src.db.session import get_engine, get_sessionmaker

__all__ = ["Base", "TimestampMixin", "get_engine", "get_sessionmaker"]
