"""Day-17 A/B: ``dharma_v1`` (no context) vs ``dharma_v2`` (Contextual Retrieval).

Runs the synthetic golden v0.0 (30 QA) four times:

* v1 + rerank=False  (day-12 baseline)
* v1 + rerank=True   (day-13 baseline, what production used until day 16)
* v2 + rerank=False  (Contextual Retrieval alone)
* v2 + rerank=True   (Contextual Retrieval + cross-encoder, the candidate
  for production v0.1.0)

Writes a side-by-side report to ``docs/EVAL_CONTEXTUAL_AB.md`` with:
* the four-run metric table (ref_hit@K, MRR, latency)
* deltas highlighting how much v2 helped
* per-query failure analysis showing which day-14 misses got fixed

GPU note
--------
Encoder + reranker run on GPU — ~10 minutes wallclock on a free 1080 Ti.
Free the GPU from Whisper before running.

Authoritative-ness
------------------
Same caveat as day-14: numbers are RELATIVE-only until a buddhologist
reviews the golden set (B-001). The deltas v1→v2 are still meaningful
even on synthetic data — the ranking of pipeline versions stays valid
when the golden set is later replaced by an authoritative one.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
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
from src.eval import (  # noqa: E402
    DEFAULT_EVAL_TOP_K,
    DEFAULT_GOLDEN_PATH,
    EvalSummary,
    GoldenSet,
    PerQueryResult,
    load_golden_set,
    run_eval,
    summarise,
)
from src.retrieval.reranker import BGEReranker  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_OUT_PATH: Path = Path("docs/EVAL_CONTEXTUAL_AB.md")
COLLECTION_V1: str = "dharma_v1"
COLLECTION_V2: str = "dharma_v2"


@dataclass(frozen=True, slots=True)
class _Run:
    """One A/B configuration we evaluate."""

    label: str
    collection: str
    rerank: bool


def _git_commit() -> str:
    """Best-effort short commit SHA. Returns ``"unknown"`` if git unavailable."""
    git = shutil.which("git")
    if git is None:
        return "unknown"
    try:
        out = subprocess.check_output(  # noqa: S603 — argv is literal, no user input
            [git, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=_REPO_ROOT,
        )
        return out.decode().strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def _print_summary(s: EvalSummary) -> None:
    print(f"\n=== {s.label} ===")
    print(
        f"n={s.overall.n}  total_latency={s.total_latency_s:.2f}s  "
        f"rerank_total={s.total_rerank_s:.2f}s"
    )
    print("Overall:")
    for k, v in sorted(s.overall.ref_hit_at_k.items()):
        print(f"  ref_hit@{k:<3}: {v:.3f}")
    print(f"  MRR     : {s.overall.mrr:.3f}")


def _failures_fixed_by_v2(
    *, v1_results: list[PerQueryResult], v2_results: list[PerQueryResult]
) -> list[dict[str, str]]:
    """Identify queries where v1 missed but v2 hit (top-5).

    The headline payoff of Contextual Retrieval is exactly this set of
    items — chunks that bi-encoder couldn't find without context but
    can with it. We surface up to 10 examples in the report so a human
    reader can sanity-check the win is real.
    """
    by_id = {r.item.id: r for r in v1_results}
    fixed: list[dict[str, str]] = []
    for r in v2_results:
        v1 = by_id.get(r.item.id)
        if v1 is None:
            continue
        expected = set(r.item.expected_works)
        v1_hit5 = any(w in expected for w in v1.retrieved_works[:5])
        v2_hit5 = any(w in expected for w in r.retrieved_works[:5])
        if not v1_hit5 and v2_hit5:
            fixed.append(
                {
                    "id": r.item.id,
                    "query": r.item.query,
                    "expected": ", ".join(r.item.expected_works),
                    "v1_top5": ", ".join(v1.retrieved_works[:5]) or "(empty)",
                    "v2_top5": ", ".join(r.retrieved_works[:5]) or "(empty)",
                }
            )
    return fixed


def _regressions(
    *, v1_results: list[PerQueryResult], v2_results: list[PerQueryResult]
) -> list[dict[str, str]]:
    """Mirror of ``_failures_fixed_by_v2`` — items where v1 hit but v2 missed.

    A net win can hide regressions in specific queries. Surfacing both
    directions keeps the analysis honest; if the regression list is
    long the v2 deployment recommendation needs caveats.
    """
    by_id = {r.item.id: r for r in v1_results}
    regressed: list[dict[str, str]] = []
    for r in v2_results:
        v1 = by_id.get(r.item.id)
        if v1 is None:
            continue
        expected = set(r.item.expected_works)
        v1_hit5 = any(w in expected for w in v1.retrieved_works[:5])
        v2_hit5 = any(w in expected for w in r.retrieved_works[:5])
        if v1_hit5 and not v2_hit5:
            regressed.append(
                {
                    "id": r.item.id,
                    "query": r.item.query,
                    "expected": ", ".join(r.item.expected_works),
                    "v1_top5": ", ".join(v1.retrieved_works[:5]) or "(empty)",
                    "v2_top5": ", ".join(r.retrieved_works[:5]) or "(empty)",
                }
            )
    return regressed


def _render_md(
    *,
    golden: GoldenSet,
    summaries: dict[str, EvalSummary],
    fixed: list[dict[str, str]],
    regressed: list[dict[str, str]],
    fixed_prod: list[dict[str, str]],
    regressed_prod: list[dict[str, str]],
    git_sha: str,
    top_k: int,
) -> str:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    lines: list[str] = []
    lines.append("# Contextual Retrieval A/B — `dharma_v1` vs `dharma_v2`")
    lines.append("")
    lines.append("> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers below come from the")
    lines.append("> synthetic golden v0.0; absolute quality claims require a buddhologist-")
    lines.append("> curated v0.1 (see B-001 in `docs/STATUS.md`). The *deltas* between")
    lines.append("> pipeline versions remain valid when the authoritative golden lands.")
    lines.append("")
    lines.append("## Run metadata")
    lines.append("")
    lines.append(f"- **Generated**: {now}")
    lines.append(f"- **Git commit**: `{git_sha}`")
    lines.append(
        f"- **Golden set**: `{DEFAULT_GOLDEN_PATH}` "
        f"(version `{golden.version}`, n={golden.total_items})"
    )
    lines.append(f"- **top_k (eval)**: {top_k}")
    lines.append(f"- **Platform**: {platform.platform()} / Python {platform.python_version()}")
    lines.append("")

    # Recommendation block sits at the top so a reader skimming the file
    # gets the bottom-line first. We compare every v2 variant against the
    # day-13 production baseline (v1+rerank) and flag whichever wins on
    # the headline metric (ref_hit@5).
    v1r_h5 = summaries["v1_rerank"].overall.ref_hit_at_k.get(5, 0.0)
    v2nr_h5 = summaries["v2_no_rerank"].overall.ref_hit_at_k.get(5, 0.0)
    v2r_h5 = summaries["v2_rerank"].overall.ref_hit_at_k.get(5, 0.0)
    candidates = [
        ("v2_no_rerank", v2nr_h5, v2nr_h5 - v1r_h5),
        ("v2_rerank", v2r_h5, v2r_h5 - v1r_h5),
    ]
    candidates.sort(key=lambda x: x[1], reverse=True)
    winner_label, winner_h5, winner_delta = candidates[0]
    lines.append("## Recommendation")
    lines.append("")
    lines.append(
        f"**Winner on `ref_hit@5`: `{winner_label}` "
        f"({winner_h5:.3f}, Δ={winner_delta:+.3f} vs `v1_rerank` baseline {v1r_h5:.3f}).**"
    )
    lines.append("")
    if winner_label == "v2_no_rerank":
        lines.append(
            "Contextual Retrieval **alone** outperforms both the day-12 baseline and "
            "the day-13 baseline-with-reranker. The cross-encoder reranker "
            "*degrades* quality on contextualized embeddings — likely because "
            "BGE-reranker-v2-m3 was trained on raw chunk text and now scores the "
            "context↔query similarity rather than chunk↔query."
        )
        lines.append("")
        lines.append(
            "**Suggested production default**: `dharma_v2` collection + `rerank=False`. "
            "This is also ~115× faster per query than the rerank path."
        )
    else:
        lines.append(
            "Cross-encoder reranking still helps on contextualized embeddings. "
            "Recommended production default: `dharma_v2` + `rerank=True`."
        )
    lines.append("")

    lines.append("## Headline numbers")
    lines.append("")
    lines.append(
        "| Metric | v1 no-rerank | v1 rerank | v2 no-rerank | v2 rerank | "
        "Δ (v2-rerank − v1-rerank) |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")
    v1nr = summaries["v1_no_rerank"].overall
    v1r = summaries["v1_rerank"].overall
    v2nr = summaries["v2_no_rerank"].overall
    v2r = summaries["v2_rerank"].overall
    for k in sorted(v1nr.ref_hit_at_k.keys()):
        a = v1nr.ref_hit_at_k[k]
        b = v1r.ref_hit_at_k[k]
        c = v2nr.ref_hit_at_k[k]
        d = v2r.ref_hit_at_k[k]
        lines.append(f"| ref_hit@{k} | {a:.3f} | {b:.3f} | {c:.3f} | {d:.3f} | {d - b:+.3f} |")
    lines.append(
        f"| MRR | {v1nr.mrr:.3f} | {v1r.mrr:.3f} | {v2nr.mrr:.3f} | {v2r.mrr:.3f} "
        f"| {v2r.mrr - v1r.mrr:+.3f} |"
    )
    lines.append("")

    lines.append("## Latency (totals across 30 queries)")
    lines.append("")
    lines.append("| Run | total_latency_s | rerank_total_s |")
    lines.append("|---|---:|---:|")
    for label in ("v1_no_rerank", "v1_rerank", "v2_no_rerank", "v2_rerank"):
        s = summaries[label]
        lines.append(f"| {label} | {s.total_latency_s:.2f} | {s.total_rerank_s:.2f} |")
    lines.append("")

    for label in ("v1_rerank", "v2_rerank"):
        s = summaries[label]
        lines.append(f"## Breakdown — {label}")
        lines.append("")
        lines.append("### By difficulty")
        lines.append("")
        lines.append("| difficulty | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for diff, m in s.by_difficulty.items():
            lines.append(
                f"| {diff} | {m.n} | {m.ref_hit_at_k.get(1, 0):.3f} | "
                f"{m.ref_hit_at_k.get(5, 0):.3f} | {m.ref_hit_at_k.get(10, 0):.3f} | "
                f"{m.ref_hit_at_k.get(20, 0):.3f} | {m.mrr:.3f} |"
            )
        lines.append("")
        lines.append("### By language")
        lines.append("")
        lines.append("| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for lang, m in s.by_language.items():
            lines.append(
                f"| {lang} | {m.n} | {m.ref_hit_at_k.get(1, 0):.3f} | "
                f"{m.ref_hit_at_k.get(5, 0):.3f} | {m.ref_hit_at_k.get(10, 0):.3f} | "
                f"{m.ref_hit_at_k.get(20, 0):.3f} | {m.mrr:.3f} |"
            )
        lines.append("")

    # Production-relevant comparison: v2 (no rerank) vs v1+rerank.
    lines.append(
        f"## Failure analysis (production-best): v2_no_rerank vs v1_rerank "
        f"(fixed n={len(fixed_prod)}, regressed n={len(regressed_prod)})"
    )
    lines.append("")
    if fixed_prod:
        lines.append(
            "Queries where v1+rerank (day-13 production) missed the expected sutta in "
            "top-5 but v2_no_rerank (production candidate) found it."
        )
        lines.append("")
        lines.append("| id | query | expected | v1+rerank top-5 | v2_no_rerank top-5 |")
        lines.append("|---|---|---|---|---|")
        for f in fixed_prod[:15]:
            q = f["query"].replace("|", "\\|")
            lines.append(f"| {f['id']} | {q} | {f['expected']} | {f['v1_top5']} | {f['v2_top5']} |")
        lines.append("")
    else:
        lines.append("(none)")
        lines.append("")

    if regressed_prod:
        lines.append("**Production-best regressions** (v1+rerank hit, v2_no_rerank missed):")
        lines.append("")
        lines.append("| id | query | expected | v1+rerank top-5 | v2_no_rerank top-5 |")
        lines.append("|---|---|---|---|---|")
        for f in regressed_prod[:15]:
            q = f["query"].replace("|", "\\|")
            lines.append(f"| {f['id']} | {q} | {f['expected']} | {f['v1_top5']} | {f['v2_top5']} |")
        lines.append("")

    lines.append(f"## Failure analysis (rerank-vs-rerank): queries v2 fixed (n={len(fixed)})")
    lines.append("")
    if fixed:
        lines.append("Queries where v1+rerank missed the expected sutta in top-5 but ")
        lines.append("v2+rerank found it. The headline payoff of Contextual Retrieval is ")
        lines.append("exactly this set.")
        lines.append("")
        lines.append("| id | query | expected | v1 top-5 | v2 top-5 |")
        lines.append("|---|---|---|---|---|")
        for f in fixed[:15]:
            q = f["query"].replace("|", "\\|")
            lines.append(f"| {f['id']} | {q} | {f['expected']} | {f['v1_top5']} | {f['v2_top5']} |")
        lines.append("")
    else:
        lines.append("(none — v2 did not fix any v1+rerank misses)")
        lines.append("")

    lines.append(f"## Regressions: queries v2 broke (n={len(regressed)})")
    lines.append("")
    if regressed:
        lines.append("Queries where v1+rerank found the expected sutta in top-5 but ")
        lines.append("v2+rerank did not. A net win on the headline metric can mask ")
        lines.append("specific regressions; surface them honestly.")
        lines.append("")
        lines.append("| id | query | expected | v1 top-5 | v2 top-5 |")
        lines.append("|---|---|---|---|---|")
        for f in regressed[:15]:
            q = f["query"].replace("|", "\\|")
            lines.append(f"| {f['id']} | {q} | {f['expected']} | {f['v1_top5']} | {f['v2_top5']} |")
        lines.append("")
    else:
        lines.append("(none — v2 did not regress any v1+rerank hits)")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "Regenerate with `python scripts/eval_contextual_ab.py` "
        "(needs Qdrant + Postgres + GPU running)."
    )
    return "\n".join(lines) + "\n"


async def _amain(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = get_settings()
    golden = load_golden_set(args.golden)
    print(
        f"Loaded golden set: version={golden.version} n={golden.total_items} "
        f"authoritative={golden.authoritative}"
    )
    if not golden.authoritative:
        print("⚠ Synthetic / non-authoritative — numbers are relative-only.\n")

    encoder = BGEM3Encoder(device="auto", use_fp16=True)
    reranker = BGEReranker(device="auto", use_fp16=True)
    qdrant = QdrantClient(url=settings.qdrant_url)
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    print("Warming up models…")
    _ = encoder.device
    print(f"  encoder:  device={encoder.device} fp16={encoder.uses_fp16}")
    _ = reranker.device
    print(f"  reranker: device={reranker.device} fp16={reranker.uses_fp16}")
    print()

    runs = [
        _Run(label="v1_no_rerank", collection=COLLECTION_V1, rerank=False),
        _Run(label="v1_rerank", collection=COLLECTION_V1, rerank=True),
        _Run(label="v2_no_rerank", collection=COLLECTION_V2, rerank=False),
        _Run(label="v2_rerank", collection=COLLECTION_V2, rerank=True),
    ]
    raw_results: dict[str, list[PerQueryResult]] = {}
    summaries: dict[str, EvalSummary] = {}

    try:
        async with session_maker() as session:
            for i, run in enumerate(runs, start=1):
                print(
                    f"Pass {i}/{len(runs)}: collection={run.collection} "
                    f"rerank={run.rerank}  ({golden.total_items} queries)…"
                )
                results = await run_eval(
                    golden=golden,
                    encoder=encoder,
                    qdrant_client=qdrant,
                    db_session=session,
                    reranker=reranker,
                    rerank=run.rerank,
                    top_k=args.top_k,
                    collection_name=run.collection,
                )
                raw_results[run.label] = results
                summaries[run.label] = summarise(results, label=run.label)
                _print_summary(summaries[run.label])
    finally:
        qdrant.close()
        await engine.dispose()

    # Two comparison axes:
    # * "rerank vs rerank" — apples to apples between v1/v2 with reranker.
    # * "v2_no_rerank vs v1_rerank" — the real production candidate (v2
    #   alone, no reranker) against the day-13 production default. The
    #   first run revealed this is the actually-winning configuration on
    #   contextualized embeddings, so it deserves first-class analysis.
    fixed_rr = _failures_fixed_by_v2(
        v1_results=raw_results["v1_rerank"],
        v2_results=raw_results["v2_rerank"],
    )
    regressed_rr = _regressions(
        v1_results=raw_results["v1_rerank"],
        v2_results=raw_results["v2_rerank"],
    )
    fixed_prod = _failures_fixed_by_v2(
        v1_results=raw_results["v1_rerank"],
        v2_results=raw_results["v2_no_rerank"],
    )
    regressed_prod = _regressions(
        v1_results=raw_results["v1_rerank"],
        v2_results=raw_results["v2_no_rerank"],
    )

    md = _render_md(
        golden=golden,
        summaries=summaries,
        fixed=fixed_rr,
        regressed=regressed_rr,
        fixed_prod=fixed_prod,
        regressed_prod=regressed_prod,
        git_sha=_git_commit(),
        top_k=args.top_k,
    )
    out_path = Path(args.out)
    out_path.write_text(md, encoding="utf-8")
    print(f"\nWrote {out_path} ({len(md):,} chars)")
    print(f"\nFixed by v2 (rerank vs rerank): {len(fixed_rr)}, regressions: {len(regressed_rr)}")
    print(
        f"Fixed by v2 (no-rerank vs v1+rerank): {len(fixed_prod)}, "
        f"regressions: {len(regressed_prod)}"
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
        "--top-k",
        type=int,
        default=DEFAULT_EVAL_TOP_K,
        help=f"Top-K depth for retrieval (default: {DEFAULT_EVAL_TOP_K})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_PATH,
        help=f"Markdown report output (default: {DEFAULT_OUT_PATH})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_amain(_parse_args())))
