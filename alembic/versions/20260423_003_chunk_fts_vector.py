"""Add BM25-backing FTS vector and GIN index on chunk.text_ascii_fold.

Revision ID: 003
Revises: 002
Create Date: 2026-04-23

Day-11 plan: classical lexical retrieval via Postgres FTS to complement
the BGE-M3 dense + learned-sparse pair from day 10. Hybrid fusion (RRF)
of all three lands on day 12.

Design
------
* **Column is GENERATED STORED.** Postgres computes ``fts_vector`` from
  ``text_ascii_fold`` on INSERT/UPDATE — no trigger maintenance. We store
  rather than compute-on-read so the GIN index works: expression indexes
  on tsvectors are supported, but they rebuild on every UPDATE and force
  us to repeat the config across every query. A stored column is the
  canonical Postgres FTS pattern in PG 12+.
* **`simple` config** — no stemming, no stopword list. We index and
  query on the ASCII-folded diacritic-free text, so Pali terms like
  ``satipatthana`` are one token with proper IDF rarity. English
  stemming (``breathings → breath``) is explicitly out of scope: that
  is dense-retrieval's job on day 12. BM25's job here is exact-term
  precision for rare Pali technical vocabulary.
* **GIN index** (Generalized Inverted iNdex) — standard choice for
  tsvector. Supports the ``@@`` match operator used by ``ts_rank_cd``.
  GiST would be 2-3x slower on reads for our size.

The column is nullable only because ``text_ascii_fold`` itself is
nullable (some legacy rows pre-day-6 may have NULL). Post-cleaner
rechunk backfill from day-6 left all current rows populated, so in
practice fts_vector will be non-null for everything.
"""

from __future__ import annotations

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Generated stored tsvector computed from the diacritic-folded text.
    # ``COALESCE`` keeps Postgres happy if any row has NULL text_ascii_fold
    # — the tsvector is empty rather than NULL, which is what GIN wants.
    op.execute(
        """
        ALTER TABLE chunk
        ADD COLUMN fts_vector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('simple', COALESCE(text_ascii_fold, ''))
        ) STORED
        """
    )
    op.create_index(
        "ix_chunk_fts_vector",
        "chunk",
        ["fts_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_chunk_fts_vector", table_name="chunk")
    op.execute("ALTER TABLE chunk DROP COLUMN fts_vector")
