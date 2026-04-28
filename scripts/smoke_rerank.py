"""End-to-end comparison smoke: hybrid pipeline WITH vs WITHOUT reranker.

For each canonical query we run:
1. ``rerank=False`` → top-8 from RRF only (day 12 baseline)
2. ``rerank=True``  → top-8 from RRF → BGE-reranker (day 13)

Side-by-side output lets a human eyeball whether the reranker helped:
- Did the canonical sutta climb to position 1?
- Did the reranker pull anything useful from rank-12 up?
- Latency cost of the cross-encoder pass.

This complements the numeric eval that lands on day 14 (Ragas on
synthetic golden v0.0).
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

from qdrant_client import QdrantClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.embeddings.bge_m3 import BGEM3Encoder  # noqa: E402
from src.retrieval.hybrid import hybrid_search  # noqa: E402
from src.retrieval.reranker import BGEReranker  # noqa: E402

QUERIES: list[tuple[str, str]] = [
    ("mindfulness of breathing", "expect MN 118 to rise to top-1 with rerank"),
    ("four noble truths", "expect SN 56.11 (first sermon) to rise"),
    ("Anāthapiṇḍika", "expect MN 143 'Advice to Anāthapiṇḍika' to rise"),
    ("noble eightfold path", "expect SN 45.8 (analysis) at top"),
    ("страдание", "Russian dukkha — does reranker keep cross-lingual?"),
    ("satipaṭṭhāna", "Pali term not in Sujato — can rerank rescue?"),
    ("simile of the saw", "expect MN 21 (Kakacūpama) at top-1"),
    ("parable of the raft", "expect MN 22 at top-1"),
    ("how should a layperson live", "expect DN 31 (Sigālovāda)"),
    ("dukkha", "weak Pali query — see if rerank picks more relevant"),
]


def _fmt(text: str, width: int = 75) -> str:
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= width else one_line[: width - 1] + "…"


async def main() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    qdrant = QdrantClient(url=settings.qdrant_url)
    encoder = BGEM3Encoder(device="auto", use_fp16=True)
    reranker = BGEReranker(device="auto", use_fp16=True)

    print("Loading encoder + reranker (first call downloads weights)…")
    _ = encoder.device
    print(f"  encoder: device={encoder.device} fp16={encoder.uses_fp16}")
    _ = reranker.device
    print(f"  reranker: device={reranker.device} fp16={reranker.uses_fp16}")
    print()

    try:
        async with session_maker() as session:
            for query, note in QUERIES:
                # Without reranker
                hits_no, t_no = await hybrid_search(
                    query=query,
                    encoder=encoder,
                    qdrant_client=qdrant,
                    db_session=session,
                    reranker=reranker,
                    rerank=False,
                    top_k=5,
                )
                # With reranker
                hits_re, t_re = await hybrid_search(
                    query=query,
                    encoder=encoder,
                    qdrant_client=qdrant,
                    db_session=session,
                    reranker=reranker,
                    rerank=True,
                    top_k=5,
                )

                print("=" * 100)
                print(f"Query: {query!r}")
                print(f"Note:  {note}")
                print(
                    f"Latency: no-rerank {t_no.total_s * 1000:6.1f} ms  |  "
                    f"with-rerank {t_re.total_s * 1000:6.1f} ms  "
                    f"(rerank itself: {t_re.rerank_s * 1000:.0f} ms)"
                )
                print("-" * 100)

                print("WITHOUT rerank (top 5 by RRF):")
                for i, h in enumerate(hits_no, 1):
                    print(
                        f"  {i}. [{h.rrf_score:.4f}] {h.work_canonical_id:<10} "
                        f"{h.segment_id or '-':<18}"
                    )
                    print(f"     {_fmt(h.text)}")

                print("WITH rerank (top 5 by reranker, [rrf_rank → score]):")
                for i, h in enumerate(hits_re, 1):
                    rrf_pos = h.rrf_rank if h.rrf_rank is not None else "?"
                    rerank_score = h.rerank_score if h.rerank_score is not None else 0.0
                    print(
                        f"  {i}. [rrf#{rrf_pos:>2} → {rerank_score:+.3f}] "
                        f"{h.work_canonical_id:<10} {h.segment_id or '-':<18}"
                    )
                    print(f"     {_fmt(h.text)}")
                print()
    finally:
        qdrant.close()
        await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
