"""FRBR-inspired entity hierarchy for the corpus.

Work → Expression → Instance → Chunk.

The mapping to the FRBR model from library science:

- **Work** — an abstract intellectual creation (e.g. MN 10 Satipaṭṭhāna
  Sutta *as an idea*).
- **Expression** — a realisation of the work in some language/edition
  (Bhikkhu Sujato's 2018 English translation of MN 10).
- **Instance** — a physical or digital embodiment (a specific HTML file
  on SuttaCentral at revision X, or a PDF).
- **Chunk** — a searchable fragment derived from an instance, sized for
  retrieval (parent ≈1024-2048 tokens, child ≈384 tokens per ADR-0001).

Why FRBR from day 1: the same sutta has dozens of translations across
centuries. Without this hierarchy, deduplication and parallel-translation
views become very painful to retrofit later.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Computed, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin


class Work(Base, TimestampMixin):
    """Abstract work, identified by its canonical reference.

    ``canonical_id`` is the stable human-readable identifier used in all
    citations (``mn10``, ``dn22``, ``sn56.11``, ``toh44``). It is unique
    across the corpus so that multi-canon searches never confuse
    different works with similar titles.
    """

    __tablename__ = "work"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    canonical_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    title_pali: Mapped[str | None] = mapped_column(String(512))

    tradition_code: Mapped[str] = mapped_column(
        ForeignKey("tradition_t.code", ondelete="RESTRICT"), nullable=False
    )
    primary_language_code: Mapped[str] = mapped_column(
        ForeignKey("language_t.code", ondelete="RESTRICT"), nullable=False
    )

    # Vajrayana / tantric works that require initiation before sharing.
    # The app layer filters these out of public responses unless the
    # instance is self-hosted with DHARMA_RAG_UNLOCK_RESTRICTED=true.
    is_restricted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )


class Expression(Base, TimestampMixin):
    """A specific translation or edition of a Work.

    One Work has many Expressions: Bodhi 1995 English, Sujato 2018
    English, Thanissaro 2002 English, Horner 1954 English, and so on.
    Queries that ask "show me all translations of MN 10" iterate here.
    """

    __tablename__ = "expression"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    work_id: Mapped[UUID] = mapped_column(ForeignKey("work.id", ondelete="CASCADE"), nullable=False)

    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("author_t.id", ondelete="SET NULL"))
    language_code: Mapped[str] = mapped_column(
        ForeignKey("language_t.code", ondelete="RESTRICT"), nullable=False
    )

    # The translation's own title may differ from the work's canonical
    # title, e.g. "The Discourse on the Establishing of Mindfulness" vs
    # "Satipaṭṭhāna Sutta".
    title: Mapped[str | None] = mapped_column(String(512))
    publication_year: Mapped[int | None]
    edition_note: Mapped[str | None] = mapped_column(Text)

    # License MUST be set; every row in the corpus has a known license
    # or it never makes it past ingest. Typical values: CC0, CC-BY-4.0,
    # CC-BY-NC-4.0, CC-BY-NC-ND-4.0, custom-free-distribution, ARR.
    license: Mapped[str] = mapped_column(String(64), nullable=False)

    # Points into consent-ledger/ for audit. Example:
    # "public-domain/suttacentral-cc0.yaml".
    consent_ledger_ref: Mapped[str | None] = mapped_column(String(256))

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    __table_args__ = (Index("ix_expression_work_lang", "work_id", "language_code"),)


class Instance(Base, TimestampMixin):
    """A concrete retrievable copy of an Expression at a point in time.

    Revisions matter: if SuttaCentral updates their HTML, we capture a
    new Instance with a new ``content_hash`` rather than mutating the
    old one. This keeps embeddings reproducible — a chunk's embedding
    always corresponds to a specific (non-changing) text.
    """

    __tablename__ = "instance"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    expression_id: Mapped[UUID] = mapped_column(
        ForeignKey("expression.id", ondelete="CASCADE"), nullable=False
    )

    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    # Free-form tag such as "html", "pdf", "epub", "json", "txt", "audio".
    source_format: Mapped[str] = mapped_column(String(32), nullable=False)

    retrieved_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # sha256 hex of the raw bytes — dedupe key, also survives renames.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Local path under data/, relative to project root. Nullable when
    # we choose not to persist the raw bytes (e.g. ephemeral scrapes).
    storage_path: Mapped[str | None] = mapped_column(String(1024))

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    __table_args__ = (
        Index("ix_instance_expression", "expression_id"),
        Index("ix_instance_content_hash", "content_hash"),
    )


class Chunk(Base, TimestampMixin):
    """A searchable fragment of an Instance.

    Parent/child relationship is encoded via ``parent_chunk_id``: small
    child chunks drive high-precision retrieval, while the corresponding
    parent chunk is what we hand to the LLM for context. See ADR-0001
    section "Chunking" for the target sizes.
    """

    __tablename__ = "chunk"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instance_id: Mapped[UUID] = mapped_column(
        ForeignKey("instance.id", ondelete="CASCADE"), nullable=False
    )
    # Self-reference: children point at their parent. We intentionally
    # leave the ORM relationship unmapped to keep the model file simple
    # — callers query ``select(Chunk).where(Chunk.parent_chunk_id == x)``
    # when they need the children of a specific parent.
    parent_chunk_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chunk.id", ondelete="SET NULL")
    )

    # Order within the parent Instance (0-based). Together with
    # instance_id this is unique, but we don't enforce it at the DB
    # level because re-ingestion may temporarily hold duplicates.
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Pali diacritics stripped (satipaṭṭhāna → satipatthana), used as a
    # BM25 fallback and to match user queries that omit diacritics.
    text_ascii_fold: Mapped[str | None] = mapped_column(Text)

    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Parent chunks (~1024-2048 tokens) are what we send to the LLM.
    # Child chunks (~384 tokens) are what we index for dense/sparse.
    is_parent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # SuttaCentral-style segment id when available (e.g. "mn10:12.3") —
    # lets us produce human-readable citations even before we know the
    # chunk's position in the final ranking.
    segment_id: Mapped[str | None] = mapped_column(String(128))

    # Dialogue metadata preserved for provenance in answers.
    speaker: Mapped[str | None] = mapped_column(String(128))
    audience: Mapped[str | None] = mapped_column(String(128))
    # Identifier for recurring canonical formulas (e.g. the jhāna
    # pericope). Used by the dedup step to avoid returning 10 copies
    # of the same boilerplate from different suttas.
    pericope_id: Mapped[str | None] = mapped_column(String(128))

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    # BM25-backing FTS vector — GENERATED STORED from text_ascii_fold by
    # Postgres (migration 003). Mapped read-only so the ORM never tries
    # to INSERT a value here. Queries use raw SQL with ts_rank_cd; this
    # mapping exists mainly for type checkers and schema introspection.
    fts_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', COALESCE(text_ascii_fold, ''))", persisted=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_chunk_instance_seq", "instance_id", "sequence"),
        Index("ix_chunk_parent", "parent_chunk_id"),
        Index("ix_chunk_segment", "segment_id"),
        Index("ix_chunk_pericope", "pericope_id"),
        Index("ix_chunk_fts_vector", "fts_vector", postgresql_using="gin"),
    )
