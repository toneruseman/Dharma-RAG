"""End-to-end retrieval smoke test against Qdrant + Postgres.

Runs a fixed set of canonical queries (English + Pali + Russian),
encodes each one with BGE-M3, fetches top-K from Qdrant using both
dense and sparse named vectors separately, then joins the hits back
to ``chunk.text`` in Postgres so a human reviewer can eyeball the
results.

This is a qualitative gate, not a numeric one — the numeric gate is
Ragas/LLM-judge eval on day 14. What we want to see here:

* Canonical Pali terms (``anapanasati``, ``satipaṭṭhāna``) surface
  passages from the right suttas (MN 10, MN 118).
* An English paraphrase retrieves something related even when the
  exact Pali string does not appear.
* Dense and sparse disagree on some queries — that is the whole
  point of keeping both for later hybrid fusion.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import UUID

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sqlalchemy as sa  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.models import SparseVector  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.db.models.frbr import Chunk  # noqa: E402
from src.embeddings.bge_m3 import BGEM3Encoder  # noqa: E402
from src.embeddings.indexer import (  # noqa: E402
    COLLECTION_NAME,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
)

# Carefully curated so a Buddhism-literate reader can tell at a glance
# whether retrieval is sensible: each query has an expected "this should
# hit text from sutta X" intuition in the docstring.
QUERIES: list[tuple[str, str]] = [
    # English paraphrase of the Ānāpānassati suttaverse — should surface MN 118
    ("mindfulness of breathing", "English paraphrase; expect MN 118 Anāpānassati"),
    # Pali term with diacritics — dense should handle, sparse should spike
    ("satipaṭṭhāna", "Pali term with diacritics; expect MN 10 / DN 22"),
    # Diacritic-free version — matters for user-typed queries
    ("anapanasati", "ASCII Pali; expect MN 118"),
    # Core doctrinal question
    ("four noble truths", "English doctrinal term; expect SN 56.11 Dhammacakka"),
    # Bare Pali word — sparse signal should dominate
    ("dukkha", "single-word Pali; expect many suttas"),
    # Russian query — BGE-M3 is multilingual; dense should cross the bridge
    ("страдание", "Russian for dukkha; dense cross-lingual test"),
]


def _fmt_text(text: str, width: int = 80) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= width:
        return one_line
    return one_line[: width - 1] + "…"


async def _text_for_chunks(
    session_maker: async_sessionmaker,  # type: ignore[type-arg]
    chunk_ids: list[UUID],
) -> dict[UUID, str]:
    if not chunk_ids:
        return {}
    async with session_maker() as session:
        rows = (
            await session.execute(sa.select(Chunk.id, Chunk.text).where(Chunk.id.in_(chunk_ids)))
        ).all()
    return {row.id: row.text for row in rows}


async def main() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    client = QdrantClient(url=settings.qdrant_url)
    encoder = BGEM3Encoder(device="cuda", use_fp16=True)

    print(f"Collection: {COLLECTION_NAME}")
    count = client.count(COLLECTION_NAME, exact=True).count
    print(f"Points in collection: {count}")
    print()

    try:
        for query, note in QUERIES:
            encoded = encoder.encode([query])
            q_dense = encoded.dense[0]
            q_sparse = encoded.sparse[0]

            dense_hits = client.query_points(
                collection_name=COLLECTION_NAME,
                query=q_dense,
                using=DENSE_VECTOR_NAME,
                limit=3,
            ).points

            sparse_indices = [int(k) for k in q_sparse]
            sparse_values = [float(v) for v in q_sparse.values()]
            sparse_hits = client.query_points(
                collection_name=COLLECTION_NAME,
                query=SparseVector(indices=sparse_indices, values=sparse_values),
                using=SPARSE_VECTOR_NAME,
                limit=3,
            ).points

            all_ids = [UUID(h.id) for h in dense_hits + sparse_hits]
            texts = await _text_for_chunks(session_maker, all_ids)

            print("=" * 80)
            print(f"Query:   {query!r}")
            print(f"Note:    {note}")
            print("-" * 80)
            print("DENSE top 3:")
            for h in dense_hits:
                uid = UUID(h.id)
                print(
                    f"  [{h.score:.3f}] {h.payload['work_canonical_id']:<10} "
                    f"{h.payload['segment_id'] or '-':<16}"
                )
                print(f"      {_fmt_text(texts.get(uid, '<missing>'))}")
            print("SPARSE top 3:")
            for h in sparse_hits:
                uid = UUID(h.id)
                print(
                    f"  [{h.score:.3f}] {h.payload['work_canonical_id']:<10} "
                    f"{h.payload['segment_id'] or '-':<16}"
                )
                print(f"      {_fmt_text(texts.get(uid, '<missing>'))}")
            print()
    finally:
        await engine.dispose()
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
