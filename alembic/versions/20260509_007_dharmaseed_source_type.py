"""Add work.source_type + seed Rob Burbea author (rag-day-37 pilot).

Revision ID: 007
Revises: 006
Create Date: 2026-05-09

Two changes for the LLM-free Dharmaseed pilot:

1. ``work.source_type`` — discriminator between canonical scripture and
   Dharmaseed dharma talks. Lets the retrieval API filter by corpus
   (variant A from concept-37 — single ``dharma_v2`` collection,
   payload-tag filter). Existing rows backfilled to ``'canonical'``.

2. ``author_t`` row for Rob Burbea (slug ``rob_burbea``) — pilot
   teacher. ``author_type='teacher'`` distinguishes from translators;
   ``tradition_code='pragmatic_dharma'`` matches the existing seed
   tradition for modern Western teachers.

When pilot scales to multiple teachers, each gets its own seed-row in
a follow-up migration; no schema changes needed.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


_VALID_SOURCE_TYPES = ("canonical", "dharmaseed_talk")
_BURBEA_AUTHOR_ID = "11111111-1111-1111-1111-111111111201"
_BURBEA_SLUG = "rob_burbea"


def upgrade() -> None:
    op.add_column(
        "work",
        sa.Column(
            "source_type",
            sa.String(length=32),
            nullable=True,
            comment="Discriminator: canonical scripture vs dharmaseed_talk recording.",
        ),
    )
    # Backfill existing rows to ``canonical`` (all Phase 1-2 work_t are
    # SuttaCentral suttas).
    op.execute(sa.text("UPDATE work SET source_type = 'canonical' WHERE source_type IS NULL"))
    # Now make NOT NULL with default for future inserts. Existing
    # backends (FastAPI / scripts) keep working — Alembic's autogen
    # would prefer a server_default, but we'd rather force callers to
    # state intent at insert time.
    op.alter_column("work", "source_type", nullable=False)
    op.create_check_constraint(
        "ck_work_source_type",
        "work",
        "source_type IN ('canonical', 'dharmaseed_talk')",
    )
    op.create_index("ix_work_source_type", "work", ["source_type"])

    op.bulk_insert(
        sa.table(
            "author_t",
            sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
            sa.column("name", sa.String),
            sa.column("author_type", sa.String),
            sa.column("tradition_code", sa.String),
            sa.column("slug", sa.String),
            sa.column("birth_year", sa.Integer),
            sa.column("death_year", sa.Integer),
            sa.column("bio", sa.Text),
            sa.column("metadata_json", sa.dialects.postgresql.JSONB),
        ),
        [
            {
                "id": _BURBEA_AUTHOR_ID,
                "name": "Rob Burbea",
                "author_type": "teacher",
                "tradition_code": "pragmatic_dharma",
                "slug": _BURBEA_SLUG,
                "birth_year": 1965,
                "death_year": 2020,
                "bio": (
                    "Rob Burbea (1965–2020) was a teacher in the Insight "
                    "tradition based at Gaia House (UK). Known for "
                    "Soulmaking Dharma and Imaginal Practice, his "
                    "teachings emphasise emptiness, eros, and the "
                    "creative dimension of contemplative life."
                ),
                "metadata_json": {
                    "source": "dharmaseed",
                    "estate": "https://sanghalive.org",
                    "url": "https://dharmaseed.org/teacher/210/",
                    "note": (
                        "Pilot teacher for rag-day-37 LLM-free dharma talk "
                        "ingestion. Estate via Sangha Live. License "
                        "CC-BY-NC-ND-4.0 default; local-dev only — "
                        "public consent campaign deferred (B-001-class)."
                    ),
                },
            }
        ],
    )


def downgrade() -> None:
    op.execute(sa.text(f"DELETE FROM author_t WHERE slug = '{_BURBEA_SLUG}'"))  # noqa: S608
    op.drop_index("ix_work_source_type", table_name="work")
    op.drop_constraint("ck_work_source_type", "work")
    op.drop_column("work", "source_type")
