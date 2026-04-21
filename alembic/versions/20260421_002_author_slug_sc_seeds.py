"""Add author_t.slug and seed SuttaCentral authors.

Revision ID: 002
Revises: 001
Create Date: 2026-04-21

Bilara files identify translators with short slugs (``sujato``, ``ms``,
``brahmali``). Looking them up by slug is the cleanest primary key for
ingest-time upserts, so we add a UNIQUE column for it rather than
encoding the slug in ``metadata_json``. The column is NULLable so that
future authors without a canonical slug (e.g. legacy PDF imports) can
still be recorded.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add slug column + unique index.
    op.add_column("author_t", sa.Column("slug", sa.String(length=64), nullable=True))
    op.create_index(
        "ix_author_t_slug",
        "author_t",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("slug IS NOT NULL"),
    )

    # 2. Seed the two SuttaCentral authors we need on day one. More
    #    translators are added opportunistically during their first ingest.
    op.bulk_insert(
        sa.table(
            "author_t",
            sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
            sa.column("name", sa.String),
            sa.column("author_type", sa.String),
            sa.column("tradition_code", sa.String),
            sa.column("slug", sa.String),
            sa.column("metadata_json", sa.dialects.postgresql.JSONB),
        ),
        [
            {
                "id": "11111111-1111-1111-1111-111111111101",
                "name": "Bhikkhu Sujato",
                "author_type": "translator",
                "tradition_code": "theravada",
                "slug": "sujato",
                "metadata_json": {
                    "source": "suttacentral",
                    "url": "https://suttacentral.net/sujato",
                },
            },
            {
                "id": "11111111-1111-1111-1111-111111111102",
                "name": "Mahāsaṅgīti Tipiṭaka Buddhavasse 2500",
                "author_type": "editor",
                "tradition_code": "theravada",
                "slug": "ms",
                "metadata_json": {
                    "source": "suttacentral",
                    "note": "Root-edition of the Pāli canon used as the Pali text upstream of sujato's translations.",
                },
            },
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM author_t WHERE slug IN ('sujato', 'ms')")
    op.drop_index("ix_author_t_slug", table_name="author_t")
    op.drop_column("author_t", "slug")
