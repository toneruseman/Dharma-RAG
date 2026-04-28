"""Qualitative BM25 smoke test against the live dharma corpus.

Runs a curated panel of 10 queries and prints the top-5 BM25 hits with
``work_canonical_id``, ``segment_id``, score, and a text excerpt pulled
from Postgres. The plan's day-11 gate is "10 sanity-запросов
осмысленные" — this script is that gate's exhibit.

The queries are deliberately chosen to demonstrate BOTH the strength of
BM25 on this corpus (proper nouns, English doctrinal terms) and its
known limit (pure Pāli doctrinal terms are absent from Sujato's English
translation, so ``satipaṭṭhāna`` returns no hits; that gap is what
day-16 contextual retrieval and later multi-translator ingest close).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.db.models.frbr import Chunk  # noqa: E402
from src.retrieval.bm25 import search  # noqa: E402

# Ten queries, each with a comment stating the *expected behaviour* so
# a future reader can tell regressions from working-as-designed noise.
QUERIES: list[tuple[str, str]] = [
    # Strong: proper names preserved in Sujato's translation
    ("Anāthapiṇḍika", "proper name, survives translation → high rank"),
    ("Sāvatthī", "place name, very high document frequency"),
    ("Gotama", "Buddha's clan name, preserved"),
    # Strong: English doctrinal terminology
    ("four noble truths", "English doctrinal term; expect SN 56.*"),
    ("mindfulness meditation", "Sujato's English for satipaṭṭhāna; expect MN 10"),
    ("noble eightfold path", "English doctrinal term"),
    # Weak: pure Pāli doctrinal term — absent from Sujato's English
    ("satipaṭṭhāna", "KNOWN GAP: 0 hits, Sujato translates to English"),
    ("anapanasati", "KNOWN GAP: ditto"),
    # Mixed: common words — should return lots but not be garbage
    ("buddha", "ubiquitous; BM25 ranks term-dense chunks first"),
    # Diacritic handling — query has none, corpus has diacritics
    ("savatthi anathapindika", "ASCII query must match diacritic text"),
]


def _fmt(text: str, width: int = 80) -> str:
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= width else one_line[: width - 1] + "…"


async def main() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_maker() as session:
            total_chunks = (
                await session.execute(
                    sa.select(sa.func.count(Chunk.id)).where(Chunk.is_parent.is_(False))
                )
            ).scalar_one()
            print(f"BM25 smoke against {total_chunks} child chunks in dharma-db")
            print()

            for query, note in QUERIES:
                hits = await search(session, query, limit=5)

                print("=" * 80)
                print(f"Query: {query!r}")
                print(f"Note:  {note}")
                print("-" * 80)
                if not hits:
                    print("  (no hits)")
                    print()
                    continue

                hit_ids = [h.chunk_id for h in hits]
                text_rows = (
                    await session.execute(
                        sa.select(Chunk.id, Chunk.text).where(Chunk.id.in_(hit_ids))
                    )
                ).all()
                texts = {r.id: r.text for r in text_rows}

                for h in hits:
                    print(
                        f"  [{h.score:.4f}] {h.work_canonical_id:<10} " f"{h.segment_id or '-':<18}"
                    )
                    print(f"      {_fmt(texts.get(h.chunk_id, '<missing>'))}")
                print()
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
