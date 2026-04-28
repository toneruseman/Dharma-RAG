"""Day-23 mini-eval: Pāli glossary on/off on production cell.

Two configurations against ``golden_v0.0_extended.yaml`` (n=100):

* baseline:    ``v2_norerank_expand`` (current production defaults), no
               glossary.
* candidate:   same cell + Pāli glossary expansion (rag-day-23). The
               query goes through ``Glossary.expand_query`` before
               encoding — same code path :class:`RAGService` uses when
               ``expand_pali=True``.

Produces a side-by-side report at ``docs/EVAL_PALI_GLOSSARY.md`` with
overall metrics, language breakdown (where the Pāli glossary should
matter most: Pāli-input + RU-input), and a per-query "fixed vs
regressed" failure analysis.

GPU
---
Encoder on GPU. Reranker is **not** in the production cell, so this is
fast: 100 × 2 × ~80 ms ≈ 16 s wallclock per cell, ~30 s total. Free the
GPU from Whisper if it's running.

Authoritative-ness
------------------
RELATIVE ONLY (synthetic). Useful for ranking glossary on/off against
each other; absolute claims need v0.1_authoritative.
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

DEFAULT_GOLDEN_PATH: Path = Path("docs/eval/golden_v0.0_extended.yaml")
DEFAULT_OUT_PATH: Path = Path("docs/EVAL_PALI_GLOSSARY.md")
PRODUCTION_COLLECTION: str = "dharma_v2"


@dataclass(frozen=True, slots=True)
class _Cell:
    label: str
    use_glossary: bool


_CELLS: tuple[_Cell, ...] = (
    _Cell(label="baseline_no_glossary", use_glossary=False),
    _Cell(label="candidate_with_glossary", use_glossary=True),
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
            "language": r.item.language,
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
    fixed: list[dict[str, str]],
    regressed: list[dict[str, str]],
    glossary_size: dict[str, int],
    git_sha: str,
    top_k: int,
    golden_path: Path,
) -> str:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    base = summaries["baseline_no_glossary"].overall
    cand = summaries["candidate_with_glossary"].overall
    delta_h5 = cand.ref_hit_at_k.get(5, 0) - base.ref_hit_at_k.get(5, 0)
    delta_mrr = cand.mrr - base.mrr

    lines: list[str] = []
    lines.append("# Pāli glossary mini-eval — rag-day-23 (synthetic golden v0.0-extended, n=100)")
    lines.append("")
    lines.append("> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers below come from")
    lines.append("> ``golden_v0.0_extended.yaml`` (100 синтетических QA). Абсолютные")
    lines.append("> утверждения о качестве требуют валидации буддологом — см. B-001 в")
    lines.append("> ``docs/STATUS.md``. Дельты между конфигурациями остаются валидными")
    lines.append("> на синтетических данных — ровно для этого файл и сделан.")
    lines.append("")
    lines.append("## Метаданные")
    lines.append("")
    lines.append(f"- **Generated**: {now}")
    lines.append(f"- **Git commit**: `{git_sha}`")
    lines.append(
        f"- **Golden set**: `{golden_path}` (version `{golden.version}`, n={golden.total_items})"
    )
    lines.append(f"- **top_k (eval)**: {top_k}")
    lines.append(f"- **Production cell**: `{PRODUCTION_COLLECTION}` + rerank=False + expand=True")
    lines.append(
        f"- **Glossary**: {glossary_size['dpd_lemmas']:,} DPD лемм + "
        f"{glossary_size['cyrillic_variants']} кириллических вариантов"
    )
    lines.append(f"- **Platform**: {platform.platform()} / Python {platform.python_version()}")
    lines.append("")

    # ---- Headline ----
    lines.append("## Главный результат")
    lines.append("")
    lines.append("| cell | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR | latency_s |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for label in ("baseline_no_glossary", "candidate_with_glossary"):
        s = summaries[label]
        o = s.overall
        lines.append(
            f"| {label} | {o.ref_hit_at_k.get(1, 0):.3f} | "
            f"{o.ref_hit_at_k.get(5, 0):.3f} | {o.ref_hit_at_k.get(10, 0):.3f} | "
            f"{o.ref_hit_at_k.get(20, 0):.3f} | {o.mrr:.3f} | "
            f"{s.total_latency_s:.2f} |"
        )
    lines.append("")
    sign_h5 = "+" if delta_h5 >= 0 else ""
    sign_mrr = "+" if delta_mrr >= 0 else ""
    lines.append(
        f"**Δ ref_hit@5 = {sign_h5}{delta_h5*100:.1f} pp**, "
        f"**Δ MRR = {sign_mrr}{delta_mrr:.3f}**"
    )
    lines.append("")

    # ---- Verdict ----
    lines.append("## Вывод")
    lines.append("")
    if delta_h5 >= 0.02:
        lines.append(
            f"Глоссарий **улучшает** ref_hit@5 на {delta_h5*100:.1f} pp на "
            f"n=100. Положительный сигнал. Рекомендуется флипнуть "
            f"`glossary_expand_pali_default=True` в `src/config.py` "
            f"в follow-up коммите."
        )
    elif delta_h5 <= -0.02:
        lines.append(
            f"Глоссарий **ухудшает** ref_hit@5 на {abs(delta_h5)*100:.1f} pp. "
            f"Default остаётся `False`. Расследовать какие категории "
            f"запросов регрессируют (см. таблицы ниже) перед следующей "
            f"итерацией."
        )
    else:
        lines.append(
            f"Глоссарий **нейтрален** на overall (Δ={delta_h5*100:.1f} pp). "
            f"Default остаётся `False` — не флипаем без явного выигрыша. "
            f"Возможно есть локальный лифт на bare-Pāli/RU подмножестве — "
            f"см. breakdown по языку ниже."
        )
    lines.append("")

    # ---- Per-language breakdown ----
    for label in ("baseline_no_glossary", "candidate_with_glossary"):
        s = summaries[label]
        lines.append(f"### {label} — по языку")
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

    # ---- Diff per language (focused on where glossary should matter) ----
    lines.append("### Δ ref_hit@5 по языку")
    lines.append("")
    lines.append("| language | n | baseline | candidate | Δ pp |")
    lines.append("|---|---:|---:|---:|---:|")
    base_by_lang = summaries["baseline_no_glossary"].by_language
    cand_by_lang = summaries["candidate_with_glossary"].by_language
    for lang in sorted(set(base_by_lang) | set(cand_by_lang)):
        b = base_by_lang.get(lang)
        c = cand_by_lang.get(lang)
        if b is None or c is None:
            continue
        b5 = b.ref_hit_at_k.get(5, 0)
        c5 = c.ref_hit_at_k.get(5, 0)
        d5 = (c5 - b5) * 100
        sign = "+" if d5 >= 0 else ""
        lines.append(f"| {lang} | {c.n} | {b5:.3f} | {c5:.3f} | {sign}{d5:.1f} |")
    lines.append("")

    # ---- Failure analysis ----
    lines.append("## Failure-анализ (top-5)")
    lines.append("")
    lines.append(f"Глоссарий **починил** {len(fixed)} запросов, **сломал** {len(regressed)}.")
    lines.append("")
    if fixed:
        lines.append("### Fixed by glossary")
        lines.append("")
        lines.append("| id | lang | query | expected | candidate top-5 |")
        lines.append("|---|---|---|---|---|")
        for row in fixed[:25]:
            lines.append(
                f"| {row['id']} | {row['language']} | {row['query'][:60]} "
                f"| {row['expected']} | {row['cand_top5']} |"
            )
        if len(fixed) > 25:
            lines.append(f"| … | | _and {len(fixed) - 25} more_ | | |")
        lines.append("")
    if regressed:
        lines.append("### Regressed by glossary")
        lines.append("")
        lines.append("| id | lang | query | expected | baseline top-5 | candidate top-5 |")
        lines.append("|---|---|---|---|---|---|")
        for row in regressed[:25]:
            lines.append(
                f"| {row['id']} | {row['language']} | {row['query'][:50]} "
                f"| {row['expected']} | {row['base_top5']} | {row['cand_top5']} |"
            )
        if len(regressed) > 25:
            lines.append(f"| … | | _and {len(regressed) - 25} more_ | | | |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "Regenerate: `python scripts/eval_pali_glossary.py` (Qdrant + Postgres + GPU, ~30 s)."
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
    print(f"Loaded glossary: {glossary.size}")

    encoder = BGEM3Encoder(device="auto", use_fp16=True)
    reranker = BGEReranker(device="auto", use_fp16=True)
    qdrant = QdrantClient(url=settings.qdrant_url)
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    print("Warming up encoder…")
    _ = encoder.device
    print(f"  encoder: device={encoder.device} fp16={encoder.uses_fp16}\n")

    raw_results: dict[str, list[PerQueryResult]] = {}
    summaries: dict[str, EvalSummary] = {}

    try:
        async with session_maker() as session:
            for i, c in enumerate(_CELLS, start=1):
                print(f"Cell {i}/{len(_CELLS)}: {c.label}  (use_glossary={c.use_glossary})")
                results = await run_eval(
                    golden=golden,
                    encoder=encoder,
                    qdrant_client=qdrant,
                    db_session=session,
                    reranker=reranker,
                    rerank=False,
                    top_k=args.top_k,
                    collection_name=PRODUCTION_COLLECTION,
                    expand_parents=True,
                    glossary=glossary if c.use_glossary else None,
                )
                raw_results[c.label] = results
                summaries[c.label] = summarise(results, label=c.label)
                _print_summary(summaries[c.label])
    finally:
        qdrant.close()
        await engine.dispose()

    fixed, regressed = _failures_top5(
        base_results=raw_results["baseline_no_glossary"],
        cand_results=raw_results["candidate_with_glossary"],
    )

    md = _render_md(
        golden=golden,
        summaries=summaries,
        fixed=fixed,
        regressed=regressed,
        glossary_size=glossary.size,
        git_sha=_git_commit(),
        top_k=args.top_k,
        golden_path=args.golden,
    )
    out_path = Path(args.out)
    out_path.write_text(md, encoding="utf-8")
    print(f"\nWrote {out_path} ({len(md):,} chars)")
    print(f"\nGlossary impact: fixed={len(fixed)}, regressed={len(regressed)}")
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
