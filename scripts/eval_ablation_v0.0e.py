"""Day-22 ablation matrix on synthetic golden v0.0-extended (100 QA).

Eight configurations, full crossing of three axes:

* collection: ``dharma_v1`` (no Contextual Retrieval) vs ``dharma_v2``
  (Contextual Retrieval, day-16 industrial run).
* rerank: ``False`` vs ``True`` — the BGE-reranker-v2-m3 cross-encoder
  pass.
* expand_parents: ``False`` vs ``True`` — day-18 small-to-big retrieval.

Why all eight (and not just the 4-cell day-17 matrix): day-17 confirmed
``dharma_v2 + rerank=False`` won, day-18 added parent expansion as a
separate knob and flipped production defaults to it. Until now we
*assumed* expansion was a strict win; the 8-cell run measures the
marginal contribution of every knob holding the others fixed, on a
larger sample (n=100 vs n=30) where the dispersion bound is tighter.

GPU
---
Encoder + reranker on GPU. Wallclock estimate on a free 1080 Ti:
  - 4 no-rerank cells:  100 × 4 × ~80 ms      ≈   30 s
  - 4 rerank cells:     100 × 4 × ~7 s        ≈ 47 min
  - encode/Qdrant share for both              negligible
  - **total**:                                 ≈ 50 min wallclock

Free the GPU from Whisper before running.

Output
------
``docs/EVAL_ABLATION_v0.0e.md`` — 8-row headline table, marginal-effect
tables (collection / rerank / expand), production-best vs day-13
baseline failure list, breakdowns.

Authoritative-ness
------------------
RELATIVE ONLY (synthetic). v0.0-extended is built from sutta knowledge
by the project's AI assistant — *not* a buddhologist (B-001 still open).
Useful for ranking pipeline configurations against each other; absolute
quality claims need v0.1_authoritative.
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
from src.retrieval.reranker import BGEReranker  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_GOLDEN_PATH: Path = Path("docs/eval/golden_v0.0_extended.yaml")
DEFAULT_OUT_PATH: Path = Path("docs/EVAL_ABLATION_v0.0e.md")
COLLECTION_V1: str = "dharma_v1"
COLLECTION_V2: str = "dharma_v2"


@dataclass(frozen=True, slots=True)
class _Cell:
    """One of the eight ablation configurations."""

    label: str
    collection: str
    rerank: bool
    expand_parents: bool


def _all_cells() -> list[_Cell]:
    """Generate the full 8-cell crossing — names like ``v2_rerank_expand``."""
    cells: list[_Cell] = []
    for coll, ctag in ((COLLECTION_V1, "v1"), (COLLECTION_V2, "v2")):
        for rerank in (False, True):
            for expand in (False, True):
                tag_rr = "rerank" if rerank else "norerank"
                tag_ex = "expand" if expand else "child"
                cells.append(
                    _Cell(
                        label=f"{ctag}_{tag_rr}_{tag_ex}",
                        collection=coll,
                        rerank=rerank,
                        expand_parents=expand,
                    )
                )
    return cells


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
    print(
        f"n={s.overall.n}  total_latency={s.total_latency_s:.2f}s  "
        f"rerank_total={s.total_rerank_s:.2f}s"
    )
    for k, v in sorted(s.overall.ref_hit_at_k.items()):
        print(f"  ref_hit@{k:<3}: {v:.3f}")
    print(f"  MRR     : {s.overall.mrr:.3f}")


def _failures_top5(
    *,
    base_results: list[PerQueryResult],
    cand_results: list[PerQueryResult],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return (fixed-by-cand, regressed-vs-base) at top-5 cut-off."""
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


def _render_md(  # noqa: PLR0915 — long but linear; report rendering
    *,
    golden: GoldenSet,
    summaries: dict[str, EvalSummary],
    fixed_prod: list[dict[str, str]],
    regressed_prod: list[dict[str, str]],
    git_sha: str,
    top_k: int,
    golden_path: Path,
) -> str:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    lines: list[str] = []
    lines.append("# Ablation matrix — Phase 2 day-22 (synthetic golden v0.0-extended, n=100)")
    lines.append("")
    lines.append("> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers below come from")
    lines.append("> ``golden_v0.0_extended.yaml`` (100 synthetic QA). Absolute quality")
    lines.append("> claims require a buddhologist-curated v0.1 — see B-001 in")
    lines.append("> ``docs/STATUS.md``. Deltas between configurations remain valid even")
    lines.append("> on synthetic data; this is the use case the file was built for.")
    lines.append("")
    lines.append("## Run metadata")
    lines.append("")
    lines.append(f"- **Generated**: {now}")
    lines.append(f"- **Git commit**: `{git_sha}`")
    lines.append(
        f"- **Golden set**: `{golden_path}` (version `{golden.version}`, n={golden.total_items})"
    )
    lines.append(f"- **top_k (eval)**: {top_k}")
    lines.append(f"- **Platform**: {platform.platform()} / Python {platform.python_version()}")
    lines.append("")

    # ---- Headline 8-cell table ----
    lines.append("## Headline — 8-cell matrix")
    lines.append("")
    lines.append(
        "| collection | rerank | expand | ref_hit@1 | ref_hit@5 | ref_hit@10 "
        "| ref_hit@20 | MRR | latency_s | rerank_s |"
    )
    lines.append("|---|:--:|:--:|---:|---:|---:|---:|---:|---:|---:|")
    cells = _all_cells()
    for c in cells:
        s = summaries[c.label]
        o = s.overall
        rr = "✓" if c.rerank else "—"
        ex = "✓" if c.expand_parents else "—"
        coll_short = c.collection.replace("dharma_", "")
        lines.append(
            f"| {coll_short} | {rr} | {ex} | {o.ref_hit_at_k.get(1, 0):.3f} | "
            f"{o.ref_hit_at_k.get(5, 0):.3f} | {o.ref_hit_at_k.get(10, 0):.3f} | "
            f"{o.ref_hit_at_k.get(20, 0):.3f} | {o.mrr:.3f} | "
            f"{s.total_latency_s:.2f} | {s.total_rerank_s:.2f} |"
        )
    lines.append("")

    # ---- Best config ----
    best_label, best_h5 = max(
        ((lbl, s.overall.ref_hit_at_k.get(5, 0.0)) for lbl, s in summaries.items()),
        key=lambda x: x[1],
    )
    prod_h5 = summaries["v2_norerank_expand"].overall.ref_hit_at_k.get(5, 0.0)
    baseline_h5 = summaries["v1_rerank_expand"].overall.ref_hit_at_k.get(5, 0.0)
    lines.append("## Best configuration")
    lines.append("")
    lines.append(f"- **Best on `ref_hit@5`**: `{best_label}` ({best_h5:.3f})")
    lines.append(
        f"- **Current production** (`v2_norerank_expand`): {prod_h5:.3f}, "
        f"Δ={prod_h5 - baseline_h5:+.3f} vs day-13 baseline (`v1_rerank_expand` {baseline_h5:.3f})"
    )
    if best_label != "v2_norerank_expand":
        lines.append(
            f"- **Note**: a different cell (`{best_label}`) outperforms current production. "
            "Consider the latency / cost tradeoff before changing defaults."
        )
    else:
        lines.append("- Current production is best on `ref_hit@5`. No change recommended.")
    lines.append("")

    # ---- Marginal effects ----
    lines.append("## Marginal effects (Δ on `ref_hit@5`)")
    lines.append("")
    lines.append("Each row holds two of {collection, rerank, expand} fixed and reports the third.")
    lines.append("")

    # Collection effect: v1 → v2, holding rerank, expand fixed
    lines.append("### Effect of Contextual Retrieval (v1 → v2)")
    lines.append("")
    lines.append("| rerank | expand | v1 ref_hit@5 | v2 ref_hit@5 | Δ |")
    lines.append("|:--:|:--:|---:|---:|---:|")
    for rerank in (False, True):
        for expand in (False, True):
            tag_rr = "rerank" if rerank else "norerank"
            tag_ex = "expand" if expand else "child"
            v1 = summaries[f"v1_{tag_rr}_{tag_ex}"].overall.ref_hit_at_k.get(5, 0.0)
            v2 = summaries[f"v2_{tag_rr}_{tag_ex}"].overall.ref_hit_at_k.get(5, 0.0)
            rr = "✓" if rerank else "—"
            ex = "✓" if expand else "—"
            lines.append(f"| {rr} | {ex} | {v1:.3f} | {v2:.3f} | {v2 - v1:+.3f} |")
    lines.append("")

    # Rerank effect
    lines.append("### Effect of cross-encoder reranker (off → on)")
    lines.append("")
    lines.append("| collection | expand | no-rerank ref_hit@5 | rerank ref_hit@5 | Δ |")
    lines.append("|:--:|:--:|---:|---:|---:|")
    for ctag in ("v1", "v2"):
        for expand in (False, True):
            tag_ex = "expand" if expand else "child"
            nr = summaries[f"{ctag}_norerank_{tag_ex}"].overall.ref_hit_at_k.get(5, 0.0)
            r = summaries[f"{ctag}_rerank_{tag_ex}"].overall.ref_hit_at_k.get(5, 0.0)
            ex = "✓" if expand else "—"
            lines.append(f"| {ctag} | {ex} | {nr:.3f} | {r:.3f} | {r - nr:+.3f} |")
    lines.append("")

    # Expand effect
    lines.append("### Effect of parent expansion (child → parent)")
    lines.append("")
    lines.append("| collection | rerank | child-only ref_hit@5 | parent-expanded ref_hit@5 | Δ |")
    lines.append("|:--:|:--:|---:|---:|---:|")
    for ctag in ("v1", "v2"):
        for rerank in (False, True):
            tag_rr = "rerank" if rerank else "norerank"
            ch = summaries[f"{ctag}_{tag_rr}_child"].overall.ref_hit_at_k.get(5, 0.0)
            ex_ = summaries[f"{ctag}_{tag_rr}_expand"].overall.ref_hit_at_k.get(5, 0.0)
            rr = "✓" if rerank else "—"
            lines.append(f"| {ctag} | {rr} | {ch:.3f} | {ex_:.3f} | {ex_ - ch:+.3f} |")
    lines.append("")

    # Note: ref_hit metrics are evaluated on retrieved_works, which is
    # the same set of chunk-IDs regardless of expand_parents (expansion
    # only changes the *text* attached to each hit, not which hits were
    # selected). expand may still move metrics if it changes reranker
    # input — when rerank=True, scoring is on child_text either way per
    # day-18 design, so expand should be neutral when rerank=True; under
    # rerank=False expand is *strictly* a no-op for ref_hit. The table
    # above will show that explicitly. Useful sanity check.

    # ---- Production-best vs day-13 baseline failure analysis ----
    lines.append(
        "## Production-best vs day-13 baseline — top-5 failure analysis "
        "(`v2_norerank_expand` vs `v1_rerank_expand`)"
    )
    lines.append("")
    lines.append(f"- Fixed by production: **{len(fixed_prod)}**")
    lines.append(f"- Regressed: **{len(regressed_prod)}**")
    lines.append("")
    if fixed_prod:
        lines.append("### Fixed (production found, baseline missed)")
        lines.append("")
        lines.append("| id | query | expected | baseline top-5 | production top-5 |")
        lines.append("|---|---|---|---|---|")
        for f in fixed_prod[:20]:
            q = f["query"].replace("|", "\\|")
            lines.append(
                f"| {f['id']} | {q} | {f['expected']} | {f['base_top5']} | {f['cand_top5']} |"
            )
        if len(fixed_prod) > 20:
            lines.append(f"| … | _({len(fixed_prod) - 20} more)_ | | | |")
        lines.append("")
    if regressed_prod:
        lines.append("### Regressed (baseline found, production missed)")
        lines.append("")
        lines.append("| id | query | expected | baseline top-5 | production top-5 |")
        lines.append("|---|---|---|---|---|")
        for f in regressed_prod[:20]:
            q = f["query"].replace("|", "\\|")
            lines.append(
                f"| {f['id']} | {q} | {f['expected']} | {f['base_top5']} | {f['cand_top5']} |"
            )
        if len(regressed_prod) > 20:
            lines.append(f"| … | _({len(regressed_prod) - 20} more)_ | | | |")
        lines.append("")

    # ---- Production-best breakdown by difficulty / language ----
    s = summaries["v2_norerank_expand"]
    lines.append("## Production-best breakdown (`v2_norerank_expand`)")
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

    lines.append("---")
    lines.append("")
    lines.append("Regenerate with `python scripts/eval_ablation_v0.0e.py` ")
    lines.append("(needs Qdrant + Postgres + GPU, ~50 min wallclock).")
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

    cells = _all_cells()
    raw_results: dict[str, list[PerQueryResult]] = {}
    summaries: dict[str, EvalSummary] = {}

    try:
        async with session_maker() as session:
            for i, c in enumerate(cells, start=1):
                print(
                    f"Cell {i}/{len(cells)}: {c.label}  "
                    f"(collection={c.collection} rerank={c.rerank} expand={c.expand_parents})"
                )
                results = await run_eval(
                    golden=golden,
                    encoder=encoder,
                    qdrant_client=qdrant,
                    db_session=session,
                    reranker=reranker,
                    rerank=c.rerank,
                    top_k=args.top_k,
                    collection_name=c.collection,
                    expand_parents=c.expand_parents,
                )
                raw_results[c.label] = results
                summaries[c.label] = summarise(results, label=c.label)
                _print_summary(summaries[c.label])
    finally:
        qdrant.close()
        await engine.dispose()

    fixed_prod, regressed_prod = _failures_top5(
        base_results=raw_results["v1_rerank_expand"],
        cand_results=raw_results["v2_norerank_expand"],
    )

    md = _render_md(
        golden=golden,
        summaries=summaries,
        fixed_prod=fixed_prod,
        regressed_prod=regressed_prod,
        git_sha=_git_commit(),
        top_k=args.top_k,
        golden_path=args.golden,
    )
    out_path = Path(args.out)
    out_path.write_text(md, encoding="utf-8")
    print(f"\nWrote {out_path} ({len(md):,} chars)")
    print(
        f"\nProduction-best vs baseline: fixed={len(fixed_prod)}, regressed={len(regressed_prod)}"
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
