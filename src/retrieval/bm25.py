"""BM25-style lexical retrieval via Postgres FTS.

Why a classical lexical scorer in 2026
--------------------------------------
Dense embeddings (BGE-M3 ``bge_m3_dense``) excel at semantic similarity
and cross-lingual matching but can "smear" rare proper nouns across
neighbours: ``Anāthapiṇḍika`` looks too much like ``Sāriputta`` in
1024-d space when both are sutta-opening names. BGE-M3's learned
sparse head helps, but its BPE tokenizer splits rare terms into
sub-pieces (``sati`` + ``##patt`` + ...), diluting exact-match signal.

BM25 on whole words, with the rarity reward baked in (IDF), is the
classical fix. It costs near-nothing on top of Postgres and gives the
hybrid fusion step (day 12) a third, independent retrieval channel.

Known limit with the current corpus
-----------------------------------
Sujato's English translation replaces most Pāli doctrinal terms with
English ("Satipaṭṭhāna Sutta" → "Mindfulness Meditation"), so BM25 on
our day-10 corpus will NOT retrieve MN 10 for a query of
"satipaṭṭhāna". What it WILL catch:

* Proper nouns that survive translation (``Sāvatthī``, ``Anāthapiṇḍika``,
  ``Gotama``, ``Kuru``).
* English doctrinal terms (``buddha`` → 2,309 chunks; ``noble truths``
  → SN 56.* collection).
* Anglicised Pāli that Sujato keeps (``Jhāna``, ``Nibbāna`` when
  retained; ``Arahant``).

The gap for raw Pāli doctrinal terms closes on two later days:
contextual retrieval on day 16 (adds Pāli uid + title context to each
chunk before embedding), and adding a Pāli root-text Instance on day 23+.

Design
------
* **Pure ASCII-folded FTS.** Postgres ``simple`` config, no stemming.
  We query against ``chunk.fts_vector`` which is a GENERATED STORED
  column derived from ``text_ascii_fold``. The client-side
  :func:`normalize_query` runs the same ``to_ascii_fold`` used at
  ingest, so ``satipaṭṭhāna`` and ``satipatthana`` query identically.
* **``websearch_to_tsquery``** — Postgres dialect that accepts plain
  user-style queries ("four noble truths", "mindfulness OR breathing")
  instead of strict tsquery operators. Safer against arbitrary input
  than ``to_tsquery`` which throws on unescaped punctuation.
* **``ts_rank_cd``** — cover-density ranking. Treats documents where
  query terms appear close together as more relevant. Not formally BM25
  but shares the IDF-weighted, position-aware family. Close enough for
  hybrid fusion; a strict BM25 would need a third-party extension.
* **Children-only by default.** Retrieval runs on child chunks to match
  day-10 Qdrant indexing; parents come back via FK expansion on day 18.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.processing.cleaner import to_ascii_fold

logger = logging.getLogger(__name__)

# Using the same config name as the migration so it is easy to grep.
# Changing this in one place without the other would produce silent
# "zero results" the way our sanity probe initially did.
FTS_CONFIG: str = "simple"


@dataclass(frozen=True, slots=True)
class BM25Hit:
    """One row from a BM25 search.

    Mirrors the payload shape we use elsewhere so hybrid fusion on
    day 12 can treat dense / sparse / BM25 hits uniformly — a list
    of :class:`BM25Hit` lines up directly with Qdrant ``ScoredPoint``
    objects for the RRF step.
    """

    chunk_id: UUID
    score: float
    work_canonical_id: str
    segment_id: str | None
    parent_chunk_id: UUID | None
    is_parent: bool


class SessionFactory(Protocol):
    """Duck-type for ``async_sessionmaker`` — lets callers swap out
    the real SQLAlchemy factory in tests that do not need Postgres.
    The ``bm25.search`` function accepts a pre-opened session directly
    so this Protocol is defined mostly for the smoke script's benefit.
    """

    def __call__(self) -> AsyncSession: ...


def normalize_query(query: str) -> str:
    """Prepare a raw user query for ``websearch_to_tsquery``.

    The same :func:`to_ascii_fold` that day-6 used to build the indexed
    column runs here on the client side. That keeps the query space in
    sync with the indexed space: ``satipaṭṭhāna`` and ``satipatthana``
    produce identical tsqueries, and a user who copy-pastes Pāli from a
    PDF gets the same hits as one who typed it on a plain keyboard.

    Whitespace is collapsed because Postgres treats repeated whitespace
    as a single token boundary anyway; normalising here makes tests
    easier to read.

    We also lowercase. ``to_ascii_fold`` is case-preserving by design
    (it's a diacritic-stripper, not a case-folder), and the ``simple``
    FTS config lowercases at tokenisation anyway — so this is free on
    the wire, but keeps the client-side query-space predictable for
    tests and logs.
    """
    if not query:
        return ""
    folded = to_ascii_fold(query).lower()
    return " ".join(folded.split())


async def search(
    session: AsyncSession,
    query: str,
    *,
    limit: int = 10,
    include_parents: bool = False,
) -> list[BM25Hit]:
    """Run FTS against ``chunk.fts_vector`` and return ranked hits.

    Parameters
    ----------
    session:
        Caller-owned session; no commit is issued here.
    query:
        Free-form user query. Empty string returns ``[]`` without
        hitting the database.
    limit:
        Max hits. Default 10 matches the plan's sanity-check target.
        Day-12 hybrid fusion will call with a larger ``limit`` (~30)
        per channel before RRF.
    include_parents:
        By default we search children only, matching Qdrant's scope.

    Returns
    -------
    List of :class:`BM25Hit` ordered by descending ``score``. Empty
    when the query yields no matches — the tsquery machinery treats
    all-stopword or empty folded queries as "no-op", which is fine.
    """
    normalised = normalize_query(query)
    if not normalised:
        return []

    # websearch_to_tsquery never raises on weird input. to_tsquery would.
    # The CROSS JOIN style keeps the query readable; the planner handles
    # it the same as a subquery on this size.
    stmt = sa.text(
        """
        SELECT
            c.id AS chunk_id,
            ts_rank_cd(c.fts_vector, q) AS score,
            c.parent_chunk_id AS parent_chunk_id,
            c.segment_id AS segment_id,
            c.is_parent AS is_parent,
            w.canonical_id AS work_canonical_id
        FROM chunk c
        JOIN instance i ON i.id = c.instance_id
        JOIN expression e ON e.id = i.expression_id
        JOIN work w ON w.id = e.work_id,
             websearch_to_tsquery(:cfg, :q) AS q
        WHERE c.fts_vector @@ q
          AND (:include_parents OR c.is_parent = false)
        ORDER BY score DESC
        LIMIT :limit
        """
    )
    result = await session.execute(
        stmt,
        {
            "cfg": FTS_CONFIG,
            "q": normalised,
            "include_parents": include_parents,
            "limit": limit,
        },
    )
    return [
        BM25Hit(
            chunk_id=row.chunk_id,
            score=float(row.score),
            work_canonical_id=row.work_canonical_id,
            segment_id=row.segment_id,
            parent_chunk_id=row.parent_chunk_id,
            is_parent=row.is_parent,
        )
        for row in result
    ]
