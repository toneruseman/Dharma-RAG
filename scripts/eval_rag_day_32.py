"""rag-day-32 cumulative re-eval (28+29+30 stack vs pre-28 baseline).

Two configurations on production stack ``dharma_v2 + rerank=False +
expand_parents=True + glossary``:

* **A. pre-28 baseline** — only Pāli glossary expansion (rag-day-23).
  This is the ``v0.1.0`` shipping config (ref_hit@5 = 0.450 on
  ``EVAL_ABLATION_v0.0e.md``).
* **B. post-30 stack** — full retrieval improvements added between
  rag-day-28 and rag-day-30: definitional expansion + foundational
  boost + BM25 translation bridge + expanded ``foundational.yaml``.

Decision rule (from ``docs/concepts/32-cumulative-eval.md``):

* B.ref_hit@5 ≥ 0.50 → cut ``v0.2.0``.
* B.ref_hit@5 ∈ [0.45, 0.50) → marginal, inspect breakdown.
* B.ref_hit@5 < 0.45 → regression, diagnose before release.

GPU
---
Encoder on GPU. Wallclock estimate on a free 1080 Ti:

* 100 queries × 2 cells × ~80 ms ≈ 16 s pure retrieval
* model warmup + first-batch encode ≈ 60-90 s
* total: **~2 min wallclock**

Free the GPU from Whisper before running.

Output
------
``docs/EVAL_RAG_DAY_32.md`` — headline numbers (overall + by language),
fixed/regressed list at top-5, decision call.

Authoritative-ness
------------------
RELATIVE ONLY (synthetic). v0.0_extended is built without buddhologist
input (B-001 still open). Useful for measuring the cumulative effect
of rag-day-28+29+30 against the v0.1.0 baseline; absolute quality
claims need v0.1_authoritative.
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
    EvalSummary,
    GoldenSet,
    PerQueryResult,
    load_golden_set,
    run_eval,
    summarise,
)
from src.expand import FoundationalMatcher, load_foundational_matcher  # noqa: E402
from src.processing.glossary import Glossary, load_glossary  # noqa: E402
from src.retrieval.reranker import BGEReranker  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_GOLDEN_PATH: Path = Path("docs/eval/golden_v0.0_extended.yaml")
DEFAULT_OUT_PATH: Path = Path("docs/EVAL_RAG_DAY_32.md")
COLLECTION: str = "dharma_v2"
DECISION_THRESHOLD_RELEASE: float = 0.50
DECISION_THRESHOLD_REGRESSION: float = 0.45


@dataclass(frozen=True, slots=True)
class _Cell:
    """One of the two re-eval configurations."""

    label: str
    description: str
    use_foundational: bool
    expand_definitional: bool


def _cells() -> list[_Cell]:
    return [
        _Cell(
            label="A_pre28_baseline",
            description="v0.1.0 baseline: Pāli glossary only",
            use_foundational=False,
            expand_definitional=False,
        ),
        _Cell(
            label="B_post30_stack",
            description="rag-day-28+29+30 stack: glossary + definitional + foundational + BM25 bridge",
            use_foundational=True,
            expand_definitional=True,
        ),
    ]


def _git_commit() -> str:
    git = shutil.which("git")
    if git is None:
        return "unknown"
    try:
        out = subprocess.check_output(  # noqa: S603 — argv is literal
            [git, "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=_REPO_ROOT,
        )
        return out.decode().strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def _print_summary(s: EvalSummary) -> None:
    print(f"\n=== {s.label} ===")
    print(f"n={s.overall.n}  total_latency={s.total_latency_s:.2f}s")
    for k, v in sorted(s.overall.ref_hit_at_k.items()):
        print(f"  ref_hit@{k:<3}: {v:.3f}")
    print(f"  MRR     : {s.overall.mrr:.3f}")


def _failures_top5(
    *,
    base_results: list[PerQueryResult],
    cand_results: list[PerQueryResult],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return (fixed-by-cand, regressed-vs-base) at top-5."""
    by_id = {r.item.id: r for r in base_results}
    fixed: list[dict[str, str]] = []
    regressed: list[dict[str, str]] = []
    for r in cand_results:
        b = by_id.get(r.item.id)
        if b is None:
            continue
        expected = set(r.item.expected_works)
        b_hit = any(w in expected for w in b.retrieved_works[:5])
        c_hit = any(w in expected for w in r.retrieved_works[:5])
        row = {
            "id": r.item.id,
            "query": r.item.query,
            "expected": ", ".join(r.item.expected_works),
            "base_top5": ", ".join(b.retrieved_works[:5]) or "(empty)",
            "cand_top5": ", ".join(r.retrieved_works[:5]) or "(empty)",
        }
        if not b_hit and c_hit:
            fixed.append(row)
        elif b_hit and not c_hit:
            regressed.append(row)
    return fixed, regressed


def _decision_call(b_hit5: float) -> str:
    """Apply decision rule from concept-32."""
    if b_hit5 >= DECISION_THRESHOLD_RELEASE:
        return (
            f"**RELEASE** — `B.ref_hit@5 = {b_hit5:.3f}` ≥ "
            f"{DECISION_THRESHOLD_RELEASE} threshold. Cut `v0.2.0`."
        )
    if b_hit5 >= DECISION_THRESHOLD_REGRESSION:
        return (
            f"**MARGINAL** — `B.ref_hit@5 = {b_hit5:.3f}` ∈ "
            f"[{DECISION_THRESHOLD_REGRESSION}, {DECISION_THRESHOLD_RELEASE}). "
            "Inspect language breakdown; if Russian wins clearly, frame "
            "release as Russian-coverage milestone."
        )
    return (
        f"**HOLD** — `B.ref_hit@5 = {b_hit5:.3f}` < "
        f"{DECISION_THRESHOLD_REGRESSION} threshold. Regression vs v0.1.0 "
        "baseline. Diagnose worst cases before release."
    )


def _render_md(  # noqa: PLR0915 — long but linear; report rendering
    *,
    golden: GoldenSet,
    summaries: dict[str, EvalSummary],
    fixed: list[dict[str, str]],
    regressed: list[dict[str, str]],
    git_sha: str,
    top_k: int,
    golden_path: Path,
) -> str:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    a = summaries["A_pre28_baseline"].overall
    b = summaries["B_post30_stack"].overall
    a_hit5 = a.ref_hit_at_k.get(5, 0.0)
    b_hit5 = b.ref_hit_at_k.get(5, 0.0)
    delta = b_hit5 - a_hit5

    lines: list[str] = []
    lines.append("# rag-day-32 — cumulative re-eval (synthetic golden v0.0_extended, n=100)")
    lines.append("")
    lines.append(
        "> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers come from "
        "`golden_v0.0_extended.yaml` (100 synthetic QA without buddhologist "
        "review — B-001 still open). Deltas between configurations remain "
        "valid even on synthetic data."
    )
    lines.append("")

    # Headline
    lines.append("## Headline")
    lines.append("")
    lines.append(
        f"- **A** (pre-rag-day-28 baseline, glossary only): "
        f"`ref_hit@5 = {a_hit5:.3f}`, MRR = {a.mrr:.3f}"
    )
    lines.append(
        f"- **B** (rag-day-28+29+30 full stack): " f"`ref_hit@5 = {b_hit5:.3f}`, MRR = {b.mrr:.3f}"
    )
    lines.append(f"- **Δ ref_hit@5**: `{delta:+.3f}` ({delta * 100:+.1f} pp)")
    lines.append("")
    lines.append("### Decision")
    lines.append("")
    lines.append(_decision_call(b_hit5))
    lines.append("")

    # Run metadata
    lines.append("## Run metadata")
    lines.append("")
    lines.append(f"- **Generated**: {now}")
    lines.append(f"- **Git commit**: `{git_sha}`")
    lines.append(
        f"- **Golden set**: `{golden_path}` (version `{golden.version}`, n={golden.total_items})"
    )
    lines.append(f"- **top_k (eval)**: {top_k}")
    lines.append(f"- **Collection**: `{COLLECTION}` (Contextual Retrieval, rag-day-16)")
    lines.append(
        "- **Fixed knobs**: `rerank=False`, `expand_parents=True`, "
        "`expand_pali=True`, `glossary_max_meanings=1`"
    )
    lines.append(f"- **Platform**: {platform.platform()} / Python {platform.python_version()}")
    lines.append("")

    # Configuration table
    lines.append("## Configurations")
    lines.append("")
    lines.append("| Cell | expand_pali | expand_definitional | foundational_boost | bm25_aliases |")
    lines.append("|---|:--:|:--:|:--:|:--:|")
    lines.append("| **A** pre-28 baseline | ✓ | — | — | — |")
    lines.append("| **B** post-30 stack | ✓ | ✓ | ✓ | ✓ |")
    lines.append("")

    # Headline metrics
    lines.append("## Headline metrics")
    lines.append("")
    lines.append("| metric | A baseline | B stack | Δ | Δ pp |")
    lines.append("|---|---:|---:|---:|---:|")
    for k in (1, 5, 10, 20):
        av = a.ref_hit_at_k.get(k, 0.0)
        bv = b.ref_hit_at_k.get(k, 0.0)
        lines.append(
            f"| ref_hit@{k} | {av:.3f} | {bv:.3f} | {bv - av:+.3f} | {(bv - av) * 100:+.1f} |"
        )
    lines.append(
        f"| MRR | {a.mrr:.3f} | {b.mrr:.3f} | {b.mrr - a.mrr:+.3f} | "
        f"{(b.mrr - a.mrr) * 100:+.1f} |"
    )
    lines.append("")

    # By-language breakdown
    sa = summaries["A_pre28_baseline"]
    sb = summaries["B_post30_stack"]
    lines.append("## Breakdown by language")
    lines.append("")
    lines.append("| language | n | A ref_hit@5 | B ref_hit@5 | Δ | A MRR | B MRR |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    languages = sorted(set(sa.by_language) | set(sb.by_language))
    for lang in languages:
        am = sa.by_language.get(lang)
        bm = sb.by_language.get(lang)
        if am is None or bm is None:
            continue
        a5 = am.ref_hit_at_k.get(5, 0.0)
        b5 = bm.ref_hit_at_k.get(5, 0.0)
        lines.append(
            f"| {lang} | {am.n} | {a5:.3f} | {b5:.3f} | {b5 - a5:+.3f} | "
            f"{am.mrr:.3f} | {bm.mrr:.3f} |"
        )
    lines.append("")

    # By-difficulty
    lines.append("## Breakdown by difficulty")
    lines.append("")
    lines.append("| difficulty | n | A ref_hit@5 | B ref_hit@5 | Δ |")
    lines.append("|---|---:|---:|---:|---:|")
    difficulties = sorted(set(sa.by_difficulty) | set(sb.by_difficulty))
    for diff in difficulties:
        am = sa.by_difficulty.get(diff)
        bm = sb.by_difficulty.get(diff)
        if am is None or bm is None:
            continue
        a5 = am.ref_hit_at_k.get(5, 0.0)
        b5 = bm.ref_hit_at_k.get(5, 0.0)
        lines.append(f"| {diff} | {am.n} | {a5:.3f} | {b5:.3f} | {b5 - a5:+.3f} |")
    lines.append("")

    # Fixed/regressed
    lines.append("## Fixed / regressed at top-5")
    lines.append("")
    lines.append(f"- Fixed by stack: **{len(fixed)}**")
    lines.append(f"- Regressed: **{len(regressed)}**")
    lines.append("")
    if fixed:
        lines.append("### Fixed (B found, A missed)")
        lines.append("")
        lines.append("| id | query | expected | A top-5 | B top-5 |")
        lines.append("|---|---|---|---|---|")
        for f in fixed[:30]:
            q = f["query"].replace("|", "\\|")[:80]
            lines.append(
                f"| {f['id']} | {q} | {f['expected']} | " f"{f['base_top5']} | {f['cand_top5']} |"
            )
        if len(fixed) > 30:
            lines.append(f"| … | _({len(fixed) - 30} more)_ | | | |")
        lines.append("")
    if regressed:
        lines.append("### Regressed (A found, B missed)")
        lines.append("")
        lines.append("| id | query | expected | A top-5 | B top-5 |")
        lines.append("|---|---|---|---|---|")
        for f in regressed[:30]:
            q = f["query"].replace("|", "\\|")[:80]
            lines.append(
                f"| {f['id']} | {q} | {f['expected']} | " f"{f['base_top5']} | {f['cand_top5']} |"
            )
        if len(regressed) > 30:
            lines.append(f"| … | _({len(regressed) - 30} more)_ | | | |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Regenerate with `python scripts/eval_rag_day_32.py` ")
    lines.append("(needs Qdrant + Postgres + GPU, ~2 min wallclock).")
    return "\n".join(lines) + "\n"


async def _amain(args: argparse.Namespace) -> int:  # noqa: PLR0915
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

    glossary: Glossary | None = None
    try:
        glossary = load_glossary()
    except FileNotFoundError:
        print("⚠ Pāli glossary not found — both cells will run without expansion")
    foundational: FoundationalMatcher | None = None
    try:
        foundational = load_foundational_matcher(
            default_boost=settings.glossary_foundational_boost_factor,
        )
        print(f"  foundational entries: {len(foundational.entries)}")
    except FileNotFoundError:
        print("⚠ foundational.yaml not found — cell B will be incomplete")

    print("Warming up models…")
    _ = encoder.device
    print(f"  encoder:  device={encoder.device} fp16={encoder.uses_fp16}")
    _ = reranker.device
    print(f"  reranker: device={reranker.device} fp16={reranker.uses_fp16}")
    print()

    cells = _cells()
    raw_results: dict[str, list[PerQueryResult]] = {}
    summaries: dict[str, EvalSummary] = {}

    try:
        async with session_maker() as session:
            for i, c in enumerate(cells, start=1):
                print(f"\nCell {i}/{len(cells)}: {c.label}")
                print(f"  {c.description}")
                results = await run_eval(
                    golden=golden,
                    encoder=encoder,
                    qdrant_client=qdrant,
                    db_session=session,
                    reranker=reranker,
                    rerank=False,
                    top_k=args.top_k,
                    collection_name=COLLECTION,
                    expand_parents=True,
                    glossary=glossary,
                    glossary_max_meanings=1,
                    foundational_matcher=foundational if c.use_foundational else None,
                    expand_definitional=c.expand_definitional,
                )
                raw_results[c.label] = results
                summaries[c.label] = summarise(results, label=c.label)
                _print_summary(summaries[c.label])
    finally:
        qdrant.close()
        await engine.dispose()

    fixed, regressed = _failures_top5(
        base_results=raw_results["A_pre28_baseline"],
        cand_results=raw_results["B_post30_stack"],
    )

    md = _render_md(
        golden=golden,
        summaries=summaries,
        fixed=fixed,
        regressed=regressed,
        git_sha=_git_commit(),
        top_k=args.top_k,
        golden_path=args.golden,
    )
    out_path = Path(args.out)
    out_path.write_text(md, encoding="utf-8")
    print(f"\nWrote {out_path} ({len(md):,} chars)")
    print(f"Cumulative effect: fixed={len(fixed)}, regressed={len(regressed)}")
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
