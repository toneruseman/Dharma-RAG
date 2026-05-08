"""Seed Russian translators (rag-day-34: theravada.ru / SuttaCentral RU coverage).

Revision ID: 006
Revises: 005
Create Date: 2026-05-08

SuttaCentral bilara-data ships Russian translations under four translator
slugs: ``sv`` (Sergey V., the same translator as theravada.ru), ``o``,
``narinyanievmenenko``, ``khantibalo``. Together they cover all five
Nikāyas. Seed them so ``ingest_sc.py --language ru`` can resolve
authors at load time.

Note: ``narinyanievmenenko`` is a community-attributed slug that
resolves to multiple translators per the SC site; we record it as a
single ``editor`` row to keep ingest simple. Per-translator splits
can come later if needed.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


_NEW_SLUGS = ("sv", "o", "narinyanievmenenko", "khantibalo")


def upgrade() -> None:
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
                "id": "11111111-1111-1111-1111-111111111103",
                "name": "Sergey V.",
                "author_type": "translator",
                "tradition_code": "theravada",
                "slug": "sv",
                "metadata_json": {
                    "source": "suttacentral",
                    "url": "https://suttacentral.net/sv",
                    "note": "Russian translator — same person as theravada.ru SV. Coverage: AN/MN/SN/KN.",
                },
            },
            {
                "id": "11111111-1111-1111-1111-111111111104",
                "name": "O.",
                "author_type": "translator",
                "tradition_code": "theravada",
                "slug": "o",
                "metadata_json": {
                    "source": "suttacentral",
                    "url": "https://suttacentral.net/o",
                    "note": "Russian translator. Coverage: DN/MN/SN/AN/KN/Vinaya — broadest RU coverage.",
                },
            },
            {
                "id": "11111111-1111-1111-1111-111111111105",
                "name": "Narinyani / Evmenenko",
                "author_type": "editor",
                "tradition_code": "theravada",
                "slug": "narinyanievmenenko",
                "metadata_json": {
                    "source": "suttacentral",
                    "note": "Community-attributed compound slug for Russian KN translations.",
                },
            },
            {
                "id": "11111111-1111-1111-1111-111111111106",
                "name": "Khantibalo",
                "author_type": "translator",
                "tradition_code": "theravada",
                "slug": "khantibalo",
                "metadata_json": {
                    "source": "suttacentral",
                    "note": "Russian translator with limited coverage (5 files).",
                },
            },
        ],
    )


def downgrade() -> None:
    # Slugs are hardcoded constants (no external input) — interpolation safe.
    placeholders = ", ".join(f"'{slug}'" for slug in _NEW_SLUGS)
    op.execute(sa.text(f"DELETE FROM author_t WHERE slug IN ({placeholders})"))  # noqa: S608
