"""Initial FRBR schema: Work, Expression, Instance, Chunk, plus lookups.

This is the first migration of the corpus database. It creates the
FRBR-inspired entity hierarchy described in
``docs/decisions/0001-phase1-architecture.md`` and seeds the lookup
tables ``tradition_t`` and ``language_t`` with their initial values so
that downstream ingest code does not need to pre-populate them.

Revision ID: 001
Revises:
Create Date: 2026-04-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Alembic identifiers.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# -----------------------------------------------------------------------------
# Seed data for lookup tables.
#
# Kept in-migration so the data travels with the schema change — a fresh
# clone of the repo running ``alembic upgrade head`` against an empty
# database gets a usable corpus skeleton without extra steps.
# -----------------------------------------------------------------------------
TRADITIONS: list[tuple[str, str, str]] = [
    (
        "theravada",
        "Theravāda",
        "The tradition of the elders — Pali Canon and its commentaries.",
    ),
    (
        "mahayana",
        "Mahāyāna",
        "The great vehicle — Sanskrit sūtras and their Chinese/Tibetan translations.",
    ),
    (
        "vajrayana",
        "Vajrayāna",
        "The diamond vehicle — tantric teachings within Mahāyāna.",
    ),
    (
        "zen",
        "Zen",
        "Japanese lineage of Chan Buddhism.",
    ),
    (
        "chan",
        "Chan",
        "Chinese lineage emphasising direct insight.",
    ),
    (
        "pragmatic_dharma",
        "Pragmatic Dharma",
        "Contemporary Western dharma drawing from multiple traditions.",
    ),
    (
        "secular",
        "Secular Buddhism",
        "Non-religious adaptation of Buddhist practice and ethics.",
    ),
]

# ISO 639-3 codes so we do not collide with ISO 639-1 two-letter codes.
LANGUAGES: list[tuple[str, str, str | None]] = [
    ("pli", "Pāli", "Latn"),
    ("san", "Sanskrit", "Deva"),
    ("bod", "Tibetan", "Tibt"),
    ("zho", "Chinese", "Hans"),
    ("jpn", "Japanese", "Jpan"),
    ("kor", "Korean", "Kore"),
    ("eng", "English", "Latn"),
    ("rus", "Russian", "Cyrl"),
    ("fra", "French", "Latn"),
    ("deu", "German", "Latn"),
    ("spa", "Spanish", "Latn"),
    ("por", "Portuguese", "Latn"),
    ("ita", "Italian", "Latn"),
    ("pol", "Polish", "Latn"),
    ("nld", "Dutch", "Latn"),
]


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Lookup tables — created first so FRBR entities can reference them.
    # ------------------------------------------------------------------
    op.create_table(
        "language_t",
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("script", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "tradition_t",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "author_t",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("author_type", sa.String(length=32), nullable=False),
        sa.Column("tradition_code", sa.String(length=32), nullable=True),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("death_year", sa.Integer(), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tradition_code"],
            ["tradition_t.code"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # FRBR hierarchy.
    # ------------------------------------------------------------------
    op.create_table(
        "work",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("canonical_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("title_pali", sa.String(length=512), nullable=True),
        sa.Column("tradition_code", sa.String(length=32), nullable=False),
        sa.Column("primary_language_code", sa.String(length=8), nullable=False),
        sa.Column(
            "is_restricted",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["primary_language_code"],
            ["language_t.code"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tradition_code"],
            ["tradition_t.code"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_work_canonical_id"),
        "work",
        ["canonical_id"],
        unique=True,
    )

    op.create_table(
        "expression",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("language_code", sa.String(length=8), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("edition_note", sa.Text(), nullable=True),
        sa.Column("license", sa.String(length=64), nullable=False),
        sa.Column("consent_ledger_ref", sa.String(length=256), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["author_t.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["language_code"],
            ["language_t.code"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["work_id"],
            ["work.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_expression_work_lang",
        "expression",
        ["work_id", "language_code"],
        unique=False,
    )

    op.create_table(
        "instance",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("expression_id", sa.Uuid(), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("source_format", sa.String(length=32), nullable=False),
        sa.Column(
            "retrieved_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["expression_id"],
            ["expression.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_instance_content_hash",
        "instance",
        ["content_hash"],
        unique=False,
    )
    op.create_index(
        "ix_instance_expression",
        "instance",
        ["expression_id"],
        unique=False,
    )

    op.create_table(
        "chunk",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instance_id", sa.Uuid(), nullable=False),
        sa.Column("parent_chunk_id", sa.Uuid(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_ascii_fold", sa.Text(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column(
            "is_parent",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("segment_id", sa.String(length=128), nullable=True),
        sa.Column("speaker", sa.String(length=128), nullable=True),
        sa.Column("audience", sa.String(length=128), nullable=True),
        sa.Column("pericope_id", sa.String(length=128), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instance_id"],
            ["instance.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_chunk_id"],
            ["chunk.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chunk_instance_seq",
        "chunk",
        ["instance_id", "sequence"],
        unique=False,
    )
    op.create_index("ix_chunk_parent", "chunk", ["parent_chunk_id"], unique=False)
    op.create_index("ix_chunk_pericope", "chunk", ["pericope_id"], unique=False)
    op.create_index("ix_chunk_segment", "chunk", ["segment_id"], unique=False)

    # ------------------------------------------------------------------
    # Seed lookup data. Bulk-insert via ``op.bulk_insert`` so the values
    # travel with the schema and a fresh clone has a usable DB after
    # ``alembic upgrade head``.
    # ------------------------------------------------------------------
    tradition_table = sa.table(
        "tradition_t",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        tradition_table,
        [
            {"code": code, "name": name, "description": description}
            for code, name, description in TRADITIONS
        ],
    )

    language_table = sa.table(
        "language_t",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("script", sa.String),
    )
    op.bulk_insert(
        language_table,
        [{"code": code, "name": name, "script": script} for code, name, script in LANGUAGES],
    )


def downgrade() -> None:
    # Reverse order: chunks → instances → expressions → works → authors →
    # lookups. Indexes go before their tables to keep PostgreSQL happy.
    op.drop_index("ix_chunk_segment", table_name="chunk")
    op.drop_index("ix_chunk_pericope", table_name="chunk")
    op.drop_index("ix_chunk_parent", table_name="chunk")
    op.drop_index("ix_chunk_instance_seq", table_name="chunk")
    op.drop_table("chunk")

    op.drop_index("ix_instance_expression", table_name="instance")
    op.drop_index("ix_instance_content_hash", table_name="instance")
    op.drop_table("instance")

    op.drop_index("ix_expression_work_lang", table_name="expression")
    op.drop_table("expression")

    op.drop_index(op.f("ix_work_canonical_id"), table_name="work")
    op.drop_table("work")

    op.drop_table("author_t")
    op.drop_table("tradition_t")
    op.drop_table("language_t")
