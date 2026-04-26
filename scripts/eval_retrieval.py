"""Day-14 baseline eval: run the synthetic golden v0.0 with/without rerank.

Usage
-----
::

    python scripts/eval_retrieval.py [--golden PATH] [--top-k 20] [--out PATH]

What it does
------------
1. Load ``docs/eval/golden_v0.0_synthetic.yaml`` (30 QA).
2. Spin up the real pipeline (BGE-M3 encoder, Qdrant client, BGE-reranker,
   Postgres async session) — once, shared between both modes.
3. Run every golden query twice:
   * ``rerank=False`` → top-20 from RRF only (day-12 baseline).
   * ``rerank=True``  → top-20 reranked by BGE-reranker-v2-m3.
4. Compute ``ref_hit@{1,5,10,20}`` and ``MRR`` for each mode, plus
   breakdowns by difficulty and language.
5. Print a side-by-side table to stdout and overwrite
   ``docs/EVAL_BASELINE.md`` with the same numbers + run metadata
   (golden version, git commit, hardware).

GPU note
--------
Both runs need GPU: encoder is shared across modes, reranker only used
when ``rerank=True``. On a free GTX 1080 Ti the full A/B is ~4 minutes;
under contention with Whisper transcription it stretches to ~10. Free
the GPU first for clean numbers.

Authoritative-ness
------------------
Numbers from this script are **relative-only** until a buddhologist
reviews the golden set (B-001). The output file carries that warning
in its header.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import platform
import shutil
import subprocess
import sys
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
    load_golden_set,
    run_eval,
    summarise,
)
from src.retrieval.reranker import BGEReranker  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_OUT_PATH: Path = Path("docs/EVAL_BASELINE.md")


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
    """Console table for one mode (with or without rerank)."""
    print(f"\n=== {s.label} ===")
    print(
        f"n={s.overall.n}  total_latency={s.total_latency_s:.2f}s  "
        f"rerank_total={s.total_rerank_s:.2f}s"
    )
    print("Overall:")
    for k, v in sorted(s.overall.ref_hit_at_k.items()):
        print(f"  ref_hit@{k:<3}: {v:.3f}")
    print(f"  MRR     : {s.overall.mrr:.3f}")

    print("By difficulty:")
    for diff, m in s.by_difficulty.items():
        ref5 = m.ref_hit_at_k.get(5, 0.0)
        print(f"  {diff:<6} n={m.n:<3} ref_hit@5={ref5:.3f}  MRR={m.mrr:.3f}")

    print("By language:")
    for lang, m in s.by_language.items():
        ref5 = m.ref_hit_at_k.get(5, 0.0)
        print(f"  {lang:<4} n={m.n:<3} ref_hit@5={ref5:.3f}  MRR={m.mrr:.3f}")


def _print_ab_table(no: EvalSummary, yes: EvalSummary) -> None:
    """Side-by-side metric comparison: rerank=False vs rerank=True."""
    print("\n=== A/B comparison ===")
    print(f"{'Metric':<14} {'rerank=False':>14} {'rerank=True':>14} {'Δ':>10}")
    print("-" * 56)
    for k in sorted(no.overall.ref_hit_at_k.keys()):
        a = no.overall.ref_hit_at_k[k]
        b = yes.overall.ref_hit_at_k[k]
        print(f"{'ref_hit@' + str(k):<14} {a:>14.3f} {b:>14.3f} {b - a:>+10.3f}")
    print(
        f"{'MRR':<14} {no.overall.mrr:>14.3f} {yes.overall.mrr:>14.3f} "
        f"{yes.overall.mrr - no.overall.mrr:>+10.3f}"
    )


def _render_markdown(
    *,
    golden: GoldenSet,
    summary_no: EvalSummary,
    summary_yes: EvalSummary,
    top_k: int,
    git_sha: str,
) -> str:
    """Build the EVAL_BASELINE.md content as a Markdown string."""
    now = datetime.now(UTC).isoformat(timespec="seconds")
    lines: list[str] = []
    lines.append("# Retrieval evaluation baseline")
    lines.append("")
    lines.append("> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers below come from the")
    lines.append("> synthetic golden set v0.0; absolute quality claims require a")
    lines.append("> buddhologist-curated v0.1 (see B-001 in `docs/STATUS.md`).")
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

    lines.append("## A/B comparison: with vs without reranker")
    lines.append("")
    lines.append("| Metric | rerank=False | rerank=True | Δ |")
    lines.append("|---|---:|---:|---:|")
    for k in sorted(summary_no.overall.ref_hit_at_k.keys()):
        a = summary_no.overall.ref_hit_at_k[k]
        b = summary_yes.overall.ref_hit_at_k[k]
        lines.append(f"| ref_hit@{k} | {a:.3f} | {b:.3f} | {b - a:+.3f} |")
    lines.append(
        f"| MRR | {summary_no.overall.mrr:.3f} | {summary_yes.overall.mrr:.3f} "
        f"| {summary_yes.overall.mrr - summary_no.overall.mrr:+.3f} |"
    )
    lines.append("")
    lines.append(
        f"- Total latency: rerank=False **{summary_no.total_latency_s:.2f}s**, "
        f"rerank=True **{summary_yes.total_latency_s:.2f}s** "
        f"(of which rerank itself: {summary_yes.total_rerank_s:.2f}s)"
    )
    lines.append("")

    for label, s in (("rerank=False", summary_no), ("rerank=True", summary_yes)):
        lines.append(f"## Breakdown — {label}")
        lines.append("")
        lines.append("### By difficulty")
        lines.append("")
        lines.append("| difficulty | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for diff, m in s.by_difficulty.items():
            row = (
                f"| {diff} | {m.n} | {m.ref_hit_at_k.get(1, 0):.3f} | "
                f"{m.ref_hit_at_k.get(5, 0):.3f} | {m.ref_hit_at_k.get(10, 0):.3f} | "
                f"{m.ref_hit_at_k.get(20, 0):.3f} | {m.mrr:.3f} |"
            )
            lines.append(row)
        lines.append("")
        lines.append("### By language")
        lines.append("")
        lines.append("| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for lang, m in s.by_language.items():
            row = (
                f"| {lang} | {m.n} | {m.ref_hit_at_k.get(1, 0):.3f} | "
                f"{m.ref_hit_at_k.get(5, 0):.3f} | {m.ref_hit_at_k.get(10, 0):.3f} | "
                f"{m.ref_hit_at_k.get(20, 0):.3f} | {m.mrr:.3f} |"
            )
            lines.append(row)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "Regenerate with `python scripts/eval_retrieval.py` "
        "(needs Qdrant + Postgres + GPU running)."
    )
    return "\n".join(lines) + "\n"


async def _amain(args: argparse.Namespace) -> int:
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

    print("Warming up models (first call downloads weights)…")
    _ = encoder.device
    print(f"  encoder:  device={encoder.device} fp16={encoder.uses_fp16}")
    _ = reranker.device
    print(f"  reranker: device={reranker.device} fp16={reranker.uses_fp16}")
    print()

    try:
        async with session_maker() as session:
            print(f"Pass 1/2: rerank=False ({golden.total_items} queries)…")
            results_no = await run_eval(
                golden=golden,
                encoder=encoder,
                qdrant_client=qdrant,
                db_session=session,
                reranker=reranker,
                rerank=False,
                top_k=args.top_k,
            )
            print(f"Pass 2/2: rerank=True  ({golden.total_items} queries)…")
            results_yes = await run_eval(
                golden=golden,
                encoder=encoder,
                qdrant_client=qdrant,
                db_session=session,
                reranker=reranker,
                rerank=True,
                top_k=args.top_k,
            )
    finally:
        qdrant.close()
        await engine.dispose()

    summary_no = summarise(results_no, label="rerank=False")
    summary_yes = summarise(results_yes, label="rerank=True")

    _print_summary(summary_no)
    _print_summary(summary_yes)
    _print_ab_table(summary_no, summary_yes)

    md = _render_markdown(
        golden=golden,
        summary_no=summary_no,
        summary_yes=summary_yes,
        top_k=args.top_k,
        git_sha=_git_commit(),
    )
    out_path = Path(args.out)
    out_path.write_text(md, encoding="utf-8")
    print(f"\nWrote {out_path} ({len(md)} chars)")
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
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    raise SystemExit(asyncio.run(_amain(_parse_args())))
