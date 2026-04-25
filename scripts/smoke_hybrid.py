"""End-to-end hybrid retrieval smoke test against the live stack.

Mirrors :mod:`scripts.smoke_retrieval` and :mod:`scripts.smoke_bm25`
but runs the full day-12 pipeline: BGE-M3 encode → dense + sparse
(Qdrant) + BM25 (Postgres FTS) in parallel → RRF fusion → enrichment.

What to look for in the output:

* Per-query top-5 with channel-rank annotations: ``[1/2/None]`` means
  rank 1 in dense, rank 2 in sparse, missing in BM25. Helps you see at
  a glance which channel(s) carried each hit.
* Latency line per query — the day-12 plan target is <200 ms end-to-end.
  The encode step dominates on CPU; on GPU it should drop ~6×.
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

QUERIES: list[tuple[str, str]] = [
    # English paraphrase — dense should carry it
    ("mindfulness of breathing", "expect MN 118; dense-led"),
    ("four noble truths", "expect SN 56.* + MN 141; all three should agree"),
    # Cross-lingual — only dense produces a signal
    ("страдание", "Russian for dukkha; dense cross-lingual only"),
    # Pure Pāli term — was 0/middling on each individual channel; hybrid
    # should still produce something sensible thanks to dense's
    # multilingual head finding adjacent passages.
    ("satipaṭṭhāna", "known weak spot; hybrid should still produce a list"),
    # Proper nouns — BM25 should dominate; dense+sparse may scatter
    ("Anāthapiṇḍika", "proper name; BM25 should rank MN 143 first"),
    # Place name in a phrase context
    ("teaching at Sāvatthī", "BM25 + dense should agree on Sāvatthī suttas"),
    # English doctrinal phrase
    ("noble eightfold path", "doctrinal English; expect SN 45.*"),
    # Single very common Pāli that survives translation
    ("dukkha", "BM25 likely empty; dense + sparse pick up semantic neighbours"),
    # Compound English
    ("right mindfulness", "doctrinal phrase from the eightfold path"),
    # Misspelling / typo robustness
    ("savathi", "ASCII typo; BM25 fold + dense fuzzy should still surface results"),
]


def _fmt(text: str, width: int = 80) -> str:
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= width else one_line[: width - 1] + "…"


def _rank_str(per_channel: dict[str, int | None]) -> str:
    """Compact ``[d/s/b]`` rendering — None becomes '·'."""

    def cell(v: int | None) -> str:
        return str(v) if v is not None else "·"

    return f"[{cell(per_channel.get('dense'))}/{cell(per_channel.get('sparse'))}/{cell(per_channel.get('bm25'))}]"


async def main() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    qdrant = QdrantClient(url=settings.qdrant_url)
    encoder = BGEM3Encoder(device="auto", use_fp16=True)

    # Force model load up-front so per-query timings exclude the
    # first-call download/load and reflect steady-state latency.
    print("Loading BGE-M3 encoder…")
    _ = encoder.device
    print(f"  encoder: device={encoder.device} fp16={encoder.uses_fp16}")
    print()

    try:
        async with session_maker() as session:
            for query, note in QUERIES:
                hits, timings = await hybrid_search(
                    query=query,
                    encoder=encoder,
                    qdrant_client=qdrant,
                    db_session=session,
                    top_k=5,
                )
                print("=" * 80)
                print(f"Query: {query!r}")
                print(f"Note:  {note}")
                print(
                    f"Lat:   {timings.total_s * 1000:6.1f} ms  "
                    f"(encode {timings.encode_s * 1000:.0f} ms · "
                    f"channels {timings.channels_s * 1000:.0f} ms · "
                    f"fusion {timings.fusion_s * 1000:.1f} ms · "
                    f"enrich {timings.enrich_s * 1000:.0f} ms)"
                )
                print("-" * 80)
                if not hits:
                    print("  (no hits)")
                    print()
                    continue
                for h in hits:
                    print(
                        f"  {h.rrf_score:.5f} {_rank_str(h.per_channel_rank)} "
                        f"{h.work_canonical_id:<10} {h.segment_id or '-':<18}"
                    )
                    print(f"      {_fmt(h.text)}")
                print()
    finally:
        qdrant.close()
        await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
