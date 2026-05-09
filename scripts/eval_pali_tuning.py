"""Day-23 tuning sweep: find the best Pāli-glossary configuration.

The first targeted eval (``docs/EVAL_PALI_GLOSSARY_TARGETED.md``)
revealed a recall/precision tradeoff at the default
``max_meanings=2`` setting: bare-Pāli ``ref_hit@20`` rose +13.3 pp
but ``ref_hit@1`` dropped 5 pp because the long synonym chains
diluted the query. Three hypotheses to test:

* **Reduce expansion volume** — ``max_meanings=1`` keeps only the
  top-1 EN + top-1 RU per term; ``max_meanings=0`` adds *only* the
  canonical Pāli lemma without any translation. Either may close
  the precision gap while preserving recall.
* **Pair with the reranker** — even if the no-rerank candidate
  loses top-1, the reranker (which scores child-text
  cross-encoder-style) should re-promote the right hit if it
  reached the top-20 pool.

Five cells against ``docs/eval/golden_pali_targeted.yaml`` (n=100,
50 ru / 30 pli / 20 mixed):

  1. baseline          (no glossary, no reranker) — control
  2. gloss-2           (glossary max_meanings=2, no reranker)  *= rerun for fresh apples-to-apples*
  3. gloss-1           (glossary max_meanings=1, no reranker)
  4. gloss-0           (glossary max_meanings=0, no reranker — lemma only)
  5. base-rerank       (no glossary, **rerank=True**)
  6. gloss-1-rerank    (glossary max=1 + rerank=True) — main candidate

GPU
---
Encoder + reranker on GPU. Reranker cells are the slow ones at this
scale: ~7 s/query × 100 ≈ 12 min per cell. Total wallclock estimate:
~3 cells no-rerank (~30 s) + ~3 cells with rerank (~36 min) ≈ 36 min
on a free 1080 Ti. Free the GPU from Whisper before running.

Output
------
``docs/EVAL_PALI_TUNING.md`` — 6-row headline + per-language
breakdowns + per-cell delta vs baseline.
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
from src.processing.glossary import load_glossary  # noqa: E402
from src.retrieval.reranker import BGEReranker  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_GOLDEN_PATH: Path = Path("docs/eval/golden_pali_targeted.yaml")
DEFAULT_OUT_PATH: Path = Path("docs/EVAL_PALI_TUNING.md")
PRODUCTION_COLLECTION: str = "dharma_v2"


@dataclass(frozen=True, slots=True)
class _Cell:
    label: str
    use_glossary: bool
    max_meanings: int  # ignored when use_glossary is False
    rerank: bool


_CELLS: tuple[_Cell, ...] = (
    _Cell(label="baseline_norerank", use_glossary=False, max_meanings=0, rerank=False),
    _Cell(label="gloss2_norerank", use_glossary=True, max_meanings=2, rerank=False),
    _Cell(label="gloss1_norerank", use_glossary=True, max_meanings=1, rerank=False),
    _Cell(label="gloss0_norerank", use_glossary=True, max_meanings=0, rerank=False),
    _Cell(label="baseline_rerank", use_glossary=False, max_meanings=0, rerank=True),
    _Cell(label="gloss1_rerank", use_glossary=True, max_meanings=1, rerank=True),
)


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


def _render_md(  # noqa: PLR0915 — long but linear; report rendering
    *,
    golden: GoldenSet,
    summaries: dict[str, EvalSummary],
    glossary_size: dict[str, int],
    git_sha: str,
    top_k: int,
    golden_path: Path,
) -> str:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    base = summaries["baseline_norerank"].overall

    lines: list[str] = []
    lines.append("# Pāli glossary tuning — rag-day-23 (targeted golden, n=100)")
    lines.append("")
    lines.append("> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers below come from")
    lines.append("> ``golden_pali_targeted.yaml`` (100 синтетических QA, специально")
    lines.append("> построенных для измерения пользы глоссария). Дельты между")
    lines.append("> конфигурациями валидны для ranking, не для абсолютных утверждений.")
    lines.append("")
    lines.append("## Что измеряем")
    lines.append("")
    lines.append("Базовый прогон (`docs/EVAL_PALI_GLOSSARY_TARGETED.md`) выявил")
    lines.append("recall/precision tradeoff: bare-Pāli `ref_hit@20` +13.3 pp, но")
    lines.append("`ref_hit@1` −5 pp при `max_meanings=2`. Здесь крутим две ручки:")
    lines.append("")
    lines.append("* **`max_meanings`**: 0 (только Pāli lemma), 1, 2 — объём")
    lines.append("  расширения. Меньше — точнее, больше — шире покрытие.")
    lines.append("* **`rerank`**: `False` (current prod default per day-22)")
    lines.append("  vs `True` — гипотеза, что реранкер восстановит precision.")
    lines.append("")
    lines.append("## Метаданные")
    lines.append("")
    lines.append(f"- **Generated**: {now}")
    lines.append(f"- **Git commit**: `{git_sha}`")
    lines.append(
        f"- **Golden set**: `{golden_path}` (version `{golden.version}`, n={golden.total_items})"
    )
    lines.append(f"- **top_k (eval)**: {top_k}")
    lines.append(f"- **Collection**: `{PRODUCTION_COLLECTION}` + expand_parents=True")
    lines.append(
        f"- **Glossary**: {glossary_size['dpd_lemmas']:,} DPD лемм + "
        f"{glossary_size['cyrillic_variants']} кириллических вариантов"
    )
    lines.append(f"- **Platform**: {platform.platform()} / Python {platform.python_version()}")
    lines.append("")

    # ---- Headline 6-cell table ----
    lines.append("## Главный результат — 6-cell tuning matrix")
    lines.append("")
    lines.append(
        "| cell | gloss | max | rerank | ref_hit@1 | ref_hit@5 | ref_hit@10 "
        "| ref_hit@20 | MRR | latency_s | rerank_s |"
    )
    lines.append("|---|:--:|:--:|:--:|---:|---:|---:|---:|---:|---:|---:|")
    for c in _CELLS:
        s = summaries[c.label]
        o = s.overall
        gl = "✓" if c.use_glossary else "—"
        mx = str(c.max_meanings) if c.use_glossary else "—"
        rr = "✓" if c.rerank else "—"
        lines.append(
            f"| {c.label} | {gl} | {mx} | {rr} | "
            f"{o.ref_hit_at_k.get(1, 0):.3f} | {o.ref_hit_at_k.get(5, 0):.3f} | "
            f"{o.ref_hit_at_k.get(10, 0):.3f} | {o.ref_hit_at_k.get(20, 0):.3f} | "
            f"{o.mrr:.3f} | {s.total_latency_s:.2f} | {s.total_rerank_s:.2f} |"
        )
    lines.append("")

    # ---- Δ vs baseline_norerank ----
    lines.append("## Δ vs baseline_norerank")
    lines.append("")
    lines.append("| cell | Δ ref_hit@1 | Δ ref_hit@5 | Δ ref_hit@10 | Δ ref_hit@20 | Δ MRR |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for c in _CELLS:
        if c.label == "baseline_norerank":
            continue
        m = summaries[c.label].overall
        d1 = (m.ref_hit_at_k.get(1, 0) - base.ref_hit_at_k.get(1, 0)) * 100
        d5 = (m.ref_hit_at_k.get(5, 0) - base.ref_hit_at_k.get(5, 0)) * 100
        d10 = (m.ref_hit_at_k.get(10, 0) - base.ref_hit_at_k.get(10, 0)) * 100
        d20 = (m.ref_hit_at_k.get(20, 0) - base.ref_hit_at_k.get(20, 0)) * 100
        dmrr = m.mrr - base.mrr

        def fmt(v: float, sign_thresh: float = 0.1) -> str:
            sign = "+" if v >= 0 else ""
            return f"{sign}{v:.1f}"

        def fmt_mrr(v: float) -> str:
            sign = "+" if v >= 0 else ""
            return f"{sign}{v:.3f}"

        lines.append(
            f"| {c.label} | {fmt(d1)} | {fmt(d5)} | {fmt(d10)} | {fmt(d20)} | {fmt_mrr(dmrr)} |"
        )
    lines.append("")

    # ---- Best cell selection ----
    best_h5 = max(
        summaries.items(),
        key=lambda kv: kv[1].overall.ref_hit_at_k.get(5, 0),
    )
    best_h1 = max(
        summaries.items(),
        key=lambda kv: kv[1].overall.ref_hit_at_k.get(1, 0),
    )
    best_mrr = max(
        summaries.items(),
        key=lambda kv: kv[1].overall.mrr,
    )
    lines.append("## Победители")
    lines.append("")
    lines.append(
        f"- **Best ref_hit@5**: `{best_h5[0]}` ({best_h5[1].overall.ref_hit_at_k.get(5, 0):.3f})"
    )
    lines.append(
        f"- **Best ref_hit@1**: `{best_h1[0]}` ({best_h1[1].overall.ref_hit_at_k.get(1, 0):.3f})"
    )
    lines.append(f"- **Best MRR**: `{best_mrr[0]}` ({best_mrr[1].overall.mrr:.3f})")
    lines.append("")

    # ---- Per-language breakdown for each cell ----
    for c in _CELLS:
        s = summaries[c.label]
        lines.append(f"### `{c.label}` — по языку")
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
    lines.append(
        "Regenerate: `python scripts/eval_pali_tuning.py` "
        "(needs Qdrant + Postgres + GPU, ~36 min wallclock for 4 rerank cells)."
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

    glossary = load_glossary()
    print(f"Loaded glossary: {glossary.size}\n")

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

    raw_results: dict[str, list[PerQueryResult]] = {}
    summaries: dict[str, EvalSummary] = {}

    try:
        async with session_maker() as session:
            for i, c in enumerate(_CELLS, start=1):
                tag = f"max={c.max_meanings}" if c.use_glossary else "no-gloss"
                print(f"Cell {i}/{len(_CELLS)}: {c.label}  ({tag}, rerank={c.rerank})")
                results = await run_eval(
                    golden=golden,
                    encoder=encoder,
                    qdrant_client=qdrant,
                    db_session=session,
                    reranker=reranker,
                    rerank=c.rerank,
                    top_k=args.top_k,
                    collection_name=PRODUCTION_COLLECTION,
                    expand_parents=True,
                    glossary=glossary if c.use_glossary else None,
                    glossary_max_meanings=c.max_meanings,
                )
                raw_results[c.label] = results
                summaries[c.label] = summarise(results, label=c.label)
                _print_summary(summaries[c.label])
    finally:
        qdrant.close()
        await engine.dispose()

    md = _render_md(
        golden=golden,
        summaries=summaries,
        glossary_size=glossary.size,
        git_sha=_git_commit(),
        top_k=args.top_k,
        golden_path=args.golden,
    )
    out_path = Path(args.out)
    out_path.write_text(md, encoding="utf-8")
    print(f"\nWrote {out_path} ({len(md):,} chars)")
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
