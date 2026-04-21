"""Lookup tables (``*_t``) for controlled vocabularies.

These tables hold small sets of rows that act as enum-like references
from the main FRBR entities. Using tables rather than Postgres enums
keeps them editable without schema migrations, and they can be
translated or annotated over time.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Tradition(Base):
    """Buddhist tradition or school.

    Seeded values (see migration 001): theravada, mahayana, vajrayana,
    zen, chan, pragmatic_dharma, secular. ``code`` is the stable
    identifier referenced from ``work.tradition_code`` and
    ``author_t.tradition_code``.
    """

    __tablename__ = "tradition_t"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class Language(Base):
    """ISO 639-3 language codes used across the corpus.

    Seeded values include pli (Pali), san (Sanskrit), bod (Tibetan),
    zho (Chinese), eng (English), rus (Russian). Extra metadata such as
    ``script`` can distinguish e.g. Traditional vs Simplified Chinese
    through the ISO 15924 tag when needed.
    """

    __tablename__ = "language_t"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    script: Mapped[str | None] = mapped_column(String(32))


class Author(Base):
    """Translators, teachers, commentators, compilers.

    Deliberately omits ``TimestampMixin``: author records rarely change
    and we want to keep Alembic diffs small for seeded data. Add it if
    we ever track editorial revisions.
    """

    __tablename__ = "author_t"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    author_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # One of: translator, teacher, commentator, compiler, editor.
    # Short identifier used by upstream sources (``sujato``, ``ms``,
    # ``brahmali``). UNIQUE when present — see migration 002. The index
    # is a partial index so existing rows without a slug stay valid.
    slug: Mapped[str | None] = mapped_column(String(64))
    tradition_code: Mapped[str | None] = mapped_column(
        ForeignKey("tradition_t.code", ondelete="SET NULL")
    )
    birth_year: Mapped[int | None]
    death_year: Mapped[int | None]
    bio: Mapped[str | None] = mapped_column(Text)
    # Catch-all for source URLs, alt names, affiliations.
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
