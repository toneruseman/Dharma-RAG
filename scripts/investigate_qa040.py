"""rag-day-27: deep-dive diagnostic for the qa_040 satipaṭṭhāna anomaly.

One-off helper. From rag-day-26 failure analysis we know that
``qa_040 = "What is satipaṭṭhāna?"`` doesn't surface ``mn10``/``dn22``
in top-5 on production config (``dharma_v2 + rerank=False +
expand_parents=True``), even though those *are* the foundational
suttas, and on a Russian variant (``qa_061``) they appear at #3 / #4.

This script runs three diagnostic phases:

* **A — query variants × collections.** Five phrasings of the
  satipaṭṭhāna query against ``dharma_v1`` (no Contextual Retrieval)
  and ``dharma_v2`` (with CR). For each variant prints (i) the actual
  top-10 work-ids returned by hybrid retrieval, and (ii) per-channel
  ranks of the target works ``mn10``/``dn22`` if they appear at all
  in the top-200 of any channel.
* **B — generalisation probes.** Same diagnostic against three other
  foundational definitional queries (dukkha / anatta / Right View) on
  the production config to see whether the failure is an isolated
  satipaṭṭhāna case or a class-wide pattern.
* **C — chunk-level inspection.** Dumps ``context_text`` and the first
  300 chars of ``text`` for a sample of mn10/dn22 child chunks. Tests
  H1 (does the contextual prefix even mention "satipaṭṭhāna"?).

Output goes to **stdout only** — copy interesting fragments into
``docs/QA040_INVESTIGATION.md`` by hand.

GPU
---
BGE-M3 encodes each query variant. ~13 retrieval calls × ~3-5 s GPU =
~1 minute on a free 1080 Ti. Free the GPU from Whisper before running.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sqlalchemy as sa  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import get_settings  # noqa: E402
from src.db.models.frbr import Chunk, Expression, Instance, Work  # noqa: E402
from src.embeddings.bge_m3 import BGEM3Encoder  # noqa: E402
from src.retrieval.hybrid import hybrid_search  # noqa: E402
from src.retrieval.schemas import HybridHit  # noqa: E402

logger = logging.getLogger(__name__)

WIDE_TOP_K: int = 200  # Per-channel pool wide enough to find target works deep.
SNIPPET_CHARS: int = 300


@dataclass(frozen=True, slots=True)
class _Probe:
    label: str
    query: str
    expected: tuple[str, ...]


# Phase A: five phrasings of the satipaṭṭhāna question.
PHASE_A_PROBES: tuple[_Probe, ...] = (
    _Probe(
        label="A1 / qa_040 literal",
        query="What is satipaṭṭhāna?",
        expected=("mn10", "dn22"),
    ),
    _Probe(
        label="A2 / no-diacritics",
        query="What is satipatthana?",
        expected=("mn10", "dn22"),
    ),
    _Probe(
        label="A3 / expanded EN gloss",
        query="What are the four foundations of mindfulness?",
        expected=("mn10", "dn22"),
    ),
    _Probe(
        label="A4 / RU literal transliteration",
        query="Что такое сатипаттхана?",
        expected=("mn10", "dn22"),
    ),
    _Probe(
        label="A5 / RU synonym (qa_061 wording)",
        query="Что Будда говорит о медитации випассана?",
        expected=("mn10", "dn22"),
    ),
)

# Phase B: foundational definitional queries on three other terms.
# Generalisation check — is qa_040 isolated or class-wide?
PHASE_B_PROBES: tuple[_Probe, ...] = (
    _Probe(
        label="B1 / dukkha",
        query="What is dukkha?",
        expected=("sn56.11",),
    ),
    _Probe(
        label="B2 / anatta",
        query="What is anatta?",
        expected=("sn22.59", "mn22"),
    ),
    _Probe(
        label="B3 / Right View",
        query="What is Right View?",
        expected=("mn117", "mn41", "mn9"),
    ),
)

COLLECTIONS_PHASE_A: tuple[str, ...] = ("dharma_v1", "dharma_v2")
COLLECTION_PROD: str = "dharma_v2"
SAMPLE_CHUNKS_PER_WORK: int = 3


async def _run_probe(
    *,
    encoder: BGEM3Encoder,
    qdrant: QdrantClient,
    db_session: AsyncSession,
    probe: _Probe,
    collection: str,
) -> None:
    """Run one query against one collection and print diagnostic table."""
    print(f"\n=== {probe.label}  |  collection={collection} ===")
    print(f"Query:    {probe.query!r}")
    print(f"Expected: {', '.join(probe.expected)}")

    hits, _timings = await hybrid_search(
        query=probe.query,
        encoder=encoder,
        qdrant_client=qdrant,
        db_session=db_session,
        reranker=None,
        rerank=False,
        top_k=WIDE_TOP_K,
        per_channel_limit=WIDE_TOP_K,
        collection_name=collection,
        expand_parents=True,
    )

    if not hits:
        print("  (no hits — empty channels)")
        return

    # Top-10 actual results — what retrieval thinks the answer is.
    print("Top-10 actual:")
    for i, h in enumerate(hits[:10], start=1):
        seg = f" [{h.segment_id}]" if h.segment_id else ""
        per = h.per_channel_rank
        per_compact = (
            f"d={_or_dash(per.get('dense'))} "
            f"s={_or_dash(per.get('sparse'))} "
            f"b={_or_dash(per.get('bm25'))}"
        )
        print(f"  {i:>2}. {h.work_canonical_id:12s}{seg}  rrf={h.rrf_score:.4f}  ({per_compact})")

    # Per-channel ranks of target works (foundational suttas).
    expected_lower = {w.lower() for w in probe.expected}
    target_hits = [h for h in hits if h.work_canonical_id.lower() in expected_lower]
    print(
        f"Target works ({', '.join(probe.expected)}) — "
        f"{len(target_hits)} child-chunks reached top-{WIDE_TOP_K}:"
    )
    if not target_hits:
        print(f"  (none — mn10/dn22 absent from all channels' top-{WIDE_TOP_K})")
    else:
        # Group by work_canonical_id, print best (smallest rrf rank) per work.
        by_work: dict[str, list[HybridHit]] = {}
        for h in target_hits:
            by_work.setdefault(h.work_canonical_id, []).append(h)
        for work_id, group in sorted(by_work.items()):
            best = min(group, key=lambda h: -h.rrf_score)  # best-rrf first
            per = best.per_channel_rank
            per_compact = (
                f"dense={_or_dash(per.get('dense'))} "
                f"sparse={_or_dash(per.get('sparse'))} "
                f"bm25={_or_dash(per.get('bm25'))}"
            )
            seg = f" [{best.segment_id}]" if best.segment_id else ""
            # Find the rrf-rank position (1-based among all hits).
            rrf_position = next(
                (i for i, h in enumerate(hits, start=1) if h is best),
                None,
            )
            print(
                f"  {work_id}{seg}: rrf_rank=#{rrf_position}  "
                f"rrf_score={best.rrf_score:.4f}  ({per_compact})  "
                f"[{len(group)} chunks total]"
            )


def _or_dash(v: int | None) -> str:
    return "—" if v is None else str(v)


async def _dump_chunk_samples(db_session: AsyncSession, work_ids: tuple[str, ...]) -> None:
    """Print context_text + text-snippet for sample child chunks of given works."""
    print("\n" + "=" * 70)
    print(
        f"Phase C — chunk-level inspection (sample of {SAMPLE_CHUNKS_PER_WORK} child chunks per work)"
    )
    print("=" * 70)

    for work_id in work_ids:
        print(f"\n--- {work_id} child-chunk samples ---")
        stmt = (
            sa.select(
                Chunk.id,
                Chunk.segment_id,
                Chunk.text,
                Chunk.context_text,
                Chunk.context_version,
            )
            .select_from(Chunk)
            .join(Instance, Instance.id == Chunk.instance_id)
            .join(Expression, Expression.id == Instance.expression_id)
            .join(Work, Work.id == Expression.work_id)
            .where(Work.canonical_id == work_id)
            .where(Chunk.is_parent.is_(False))
            .order_by(Chunk.sequence)
            .limit(SAMPLE_CHUNKS_PER_WORK)
        )
        rows = (await db_session.execute(stmt)).all()
        if not rows:
            print(f"  (no child chunks found for {work_id})")
            continue
        for row in rows:
            seg = row.segment_id or "(no segment_id)"
            print(f"\n  [{seg}] (chunk_id={row.id}, context_version={row.context_version})")
            ctx = (row.context_text or "").strip()
            if ctx:
                print("  context_text:")
                for line in _wrap(ctx, 76):
                    print(f"    {line}")
            else:
                print("  context_text: (empty)")
            text = (row.text or "").strip()
            print(f"  text[:{SNIPPET_CHARS}]:")
            for line in _wrap(text[:SNIPPET_CHARS], 76):
                print(f"    {line}")


def _wrap(s: str, n: int) -> list[str]:
    flat = " ".join(s.split())
    out: list[str] = []
    while flat:
        out.append(flat[:n])
        flat = flat[n:]
    return out


async def _amain(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = get_settings()
    print("rag-day-27 — qa_040 satipaṭṭhāna anomaly investigation")
    print(
        f"Probes: {len(PHASE_A_PROBES)} variants × {len(COLLECTIONS_PHASE_A)} collections "
        f"+ {len(PHASE_B_PROBES)} generalisation = "
        f"{len(PHASE_A_PROBES) * len(COLLECTIONS_PHASE_A) + len(PHASE_B_PROBES)} retrieval calls"
    )
    print(f"Per-channel pool: top-{WIDE_TOP_K}\n")

    encoder = BGEM3Encoder(device="auto", use_fp16=True)
    qdrant = QdrantClient(url=settings.qdrant_url)
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    print(f"Encoder ready (device={encoder.device}, fp16={encoder.uses_fp16}).")

    try:
        async with session_maker() as session:
            print("\n" + "=" * 70)
            print("Phase A — satipaṭṭhāna variants × collections")
            print("=" * 70)
            for probe in PHASE_A_PROBES:
                for collection in COLLECTIONS_PHASE_A:
                    await _run_probe(
                        encoder=encoder,
                        qdrant=qdrant,
                        db_session=session,
                        probe=probe,
                        collection=collection,
                    )

            print("\n" + "=" * 70)
            print(f"Phase B — generalisation (collection={COLLECTION_PROD})")
            print("=" * 70)
            for probe in PHASE_B_PROBES:
                await _run_probe(
                    encoder=encoder,
                    qdrant=qdrant,
                    db_session=session,
                    probe=probe,
                    collection=COLLECTION_PROD,
                )

            await _dump_chunk_samples(session, work_ids=("mn10", "dn22"))
    finally:
        qdrant.close()
        await engine.dispose()

    print("\n--- end of investigation ---")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_amain(_parse_args())))
