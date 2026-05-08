"""Day-26 retrieval failure analysis on synthetic golden v0.0-extended.

One-off helper. Runs the production retrieval config
(``dharma_v2 + rerank=False + expand_parents=True``) over every QA in
a golden set with ``top_k=100``, computes ``ref_rank`` (position of the
first matching expected work), sorts by worst-first, and prints the
top-N for manual categorisation.

Output goes to **stdout only** — by design. The user copies the
records they want to discuss into ``docs/FAILURE_PATTERNS.md`` and
attaches a category + explanation by hand. File-output would tempt us
into auto-pipelining; this day is a *manual* analysis.

GPU
---
BGE-M3 encodes every query (no reranker — production config). 100 QA
on a free 1080 Ti is ~1-2 minutes; under Whisper contention ~5 min.
Free the GPU before running.

Usage::

    python scripts/eval_failure_analysis.py
    python scripts/eval_failure_analysis.py --top-n 20 > tmp/failures.txt
    python scripts/eval_failure_analysis.py --golden some/other.yaml --top-k 50
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from math import inf
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
from src.eval import PerQueryResult, load_golden_set, run_eval  # noqa: E402
from src.expand import load_foundational_matcher  # noqa: E402
from src.processing.glossary import load_glossary  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_GOLDEN_PATH: Path = Path("docs/eval/golden_v0.0_extended.yaml")
DEFAULT_TOP_N: int = 10
DEFAULT_TOP_K: int = 100
PROD_COLLECTION: str = "dharma_v2"
SNIPPET_CHARS: int = 140


@dataclass(frozen=True, slots=True)
class _Ranked:
    """Per-query result enriched with the position of the expected work."""

    result: PerQueryResult
    ref_rank: float  # 1-based position; ``inf`` if not in top_k.


def _ref_rank(result: PerQueryResult) -> float:
    """First 1-based position of any expected work in retrieved_works."""
    expected = set(result.item.expected_works)
    for i, w in enumerate(result.retrieved_works, start=1):
        if w in expected:
            return float(i)
    return inf


def _format_rank(r: float) -> str:
    return "∞" if r == inf else str(int(r))


def _snippet(text: str, n: int = SNIPPET_CHARS) -> str:
    """Trim text to ``n`` chars, collapse whitespace, escape newlines."""
    flat = " ".join(text.split())
    return flat if len(flat) <= n else flat[:n].rstrip() + "…"


def _print_record(rk: _Ranked) -> None:
    item = rk.result.item
    print(
        f"=== {item.id} ({item.language}/{item.difficulty}): {item.query!r} === "
        f"ref_rank={_format_rank(rk.ref_rank)}"
    )
    expected_str = ", ".join(item.expected_works) or "(none)"
    print(f"Expected: {expected_str}")
    print("Retrieved top-5:")
    if not rk.result.hits:
        print("  (no hits)")
        print()
        return
    for i, hit in enumerate(rk.result.hits[:5], start=1):
        seg = f" [{hit.segment_id}]" if hit.segment_id else ""
        print(
            f"  {i}. {hit.work_canonical_id:12s}{seg}  rrf={hit.rrf_score:.3f}  "
            f":: {_snippet(hit.text)}"
        )
    print()


async def _amain(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = get_settings()
    golden = load_golden_set(args.golden)
    print(
        f"Loaded golden set: version={golden.version} "
        f"n={golden.total_items} authoritative={golden.authoritative}"
    )
    print(
        f"Production config: collection={PROD_COLLECTION} rerank=False "
        f"expand_parents=True top_k={args.top_k}"
    )
    print()

    encoder = BGEM3Encoder(device="auto", use_fp16=True)
    qdrant = QdrantClient(url=settings.qdrant_url)
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    glossary = None
    foundational = None
    if args.full_stack:
        try:
            glossary = load_glossary()
        except FileNotFoundError:
            print("WARN: Pāli glossary not found")
        try:
            foundational = load_foundational_matcher(
                default_boost=settings.glossary_foundational_boost_factor,
            )
            print(f"Loaded foundational matcher: {len(foundational.entries)} entries")
        except FileNotFoundError:
            print("WARN: foundational.yaml not found")
        print("Mode: FULL STACK (glossary + definitional + foundational + bm25 bridge)")
    else:
        print("Mode: BASELINE (no expansion knobs — rag-day-26 config)")

    print(f"Encoder ready (device={encoder.device}, fp16={encoder.uses_fp16}). Running…")

    try:
        async with session_maker() as session:
            results = await run_eval(
                golden=golden,
                encoder=encoder,
                qdrant_client=qdrant,
                db_session=session,
                reranker=None,
                rerank=False,
                top_k=args.top_k,
                collection_name=PROD_COLLECTION,
                expand_parents=True,
                glossary=glossary,
                glossary_max_meanings=1,
                foundational_matcher=foundational,
                expand_definitional=args.full_stack,
            )
    finally:
        qdrant.close()
        await engine.dispose()

    ranked = [_Ranked(result=r, ref_rank=_ref_rank(r)) for r in results]
    # Worst first: ``inf`` (fully missed) at the top, then finite ranks
    # in descending order (deeper misses before near-hits). Tiebreak by
    # qa-id so order is deterministic across runs.
    ranked.sort(key=lambda r: (0 if r.ref_rank == inf else 1, -r.ref_rank, r.result.item.id))

    n_missed = sum(1 for r in ranked if r.ref_rank == inf)
    n_in_top5 = sum(1 for r in ranked if r.ref_rank != inf and r.ref_rank <= 5)
    n_in_top20 = sum(1 for r in ranked if r.ref_rank != inf and r.ref_rank <= 20)
    print()
    print(
        f"Headline: ref_hit@5={n_in_top5/len(ranked):.3f}  "
        f"ref_hit@20={n_in_top20/len(ranked):.3f}  "
        f"missed (ref_rank=∞ at top_k={args.top_k}): {n_missed}/{len(ranked)}"
    )
    print()
    print(f"--- Worst {args.top_n} queries (sorted by ref_rank descending; ∞ first) ---")
    print()

    for rk in ranked[: args.top_n]:
        _print_record(rk)

    print(
        f"--- end of top {args.top_n}. "
        f"Total {len(ranked)} QAs evaluated, {n_missed} fully missed. ---"
    )
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--golden",
        type=Path,
        default=DEFAULT_GOLDEN_PATH,
        help=f"Path to golden YAML (default: {DEFAULT_GOLDEN_PATH})",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=DEFAULT_TOP_N,
        help=f"How many worst queries to print (default: {DEFAULT_TOP_N})",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Retrieval depth for ref_rank measurement (default: {DEFAULT_TOP_K})",
    )
    parser.add_argument(
        "--full-stack",
        action="store_true",
        help=(
            "Run with full post-rag-day-34 stack: Pāli glossary + "
            "definitional expansion + foundational boost + BM25 bridge. "
            "Default is rag-day-26 baseline (no expansion) for historical "
            "comparison."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_amain(_parse_args())))
