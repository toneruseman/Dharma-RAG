"""Compare Contextual Retrieval models head-to-head on a sample (rag-day-35).

Picks N random child chunks from the corpus and generates contexts with two
candidate models (Haiku 3.5 baseline, DeepSeek V4 candidate). Outputs a
side-by-side markdown report for manual review.

Decision criteria (manual review):
* **Pāli term preservation** — does it spell `samādhi`/`paṭiccasamuppāda`
  with diacritics?
* **Sutta ID accuracy** — correct canonical ID, no hallucinated titles
  (the rag-day-16 smoke caught MN 118 mis-labelled as Satipaṭṭhāna Sutta).
* **Length** — 50-100 tokens (1-3 sentences) per spec.
* **Style** — single paragraph, no markdown, no quotation marks.
* **Russian handling** — Cyrillic chunks handled gracefully?

Cost estimate
-------------
N=20 chunks × 2 models × ~500 input tokens × $X/M = pennies.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.contextual.providers.openrouter import OpenRouterProvider  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_OUT_PATH = Path("docs/EVAL_CONTEXT_MODELS.md")
DEFAULT_N = 20
MODEL_BASELINE = "anthropic/claude-3.5-haiku"
MODEL_CANDIDATE = "deepseek/deepseek-v4-flash"


async def _fetch_samples(session_maker: Any, n: int) -> list[dict[str, Any]]:
    """Pull N random pairs (parent_text, child_text) from corpus.

    Mixes English Sujato + Russian SV translations to stress-test
    multilingual handling. Excludes very short (<100 chars) and very long
    (>3000 chars) chunks for predictable side-by-side reading.
    """
    async with session_maker() as session:
        rows = await session.execute(
            text(
                """
                SELECT
                    c.id AS child_id,
                    c.text AS child_text,
                    p.text AS parent_text,
                    e.language_code,
                    a.slug AS translator,
                    w.canonical_id
                FROM chunk c
                JOIN chunk p ON p.id = c.parent_chunk_id
                JOIN instance i ON i.id = c.instance_id
                JOIN expression e ON e.id = i.expression_id
                JOIN author_t a ON a.id = e.author_id
                JOIN work w ON w.id = e.work_id
                WHERE c.is_parent = false
                  AND length(c.text) BETWEEN 100 AND 3000
                  AND length(p.text) BETWEEN 100 AND 5000
                ORDER BY random()
                LIMIT :n
                """
            ),
            {"n": n},
        )
        return [dict(row._mapping) for row in rows]


def _generate_contexts(
    samples: list[dict[str, Any]],
    *,
    api_key: str,
    model: str,
) -> list[str]:
    """Run a model over every sample, returning generated contexts."""
    provider = OpenRouterProvider(
        api_key=api_key,
        model=model,
        enable_caching=False,  # straight A/B; caching skews comparison
    )
    out: list[str] = []
    for i, s in enumerate(samples, start=1):
        try:
            ctx = provider.generate_context(
                parent_text=s["parent_text"],
                child_text=s["child_text"],
            )
            print(f"  [{i}/{len(samples)}] {model} done", flush=True)
        except Exception as exc:  # noqa: BLE001 — surface any provider failure
            ctx = f"<ERROR: {exc!s}>"
            print(f"  [{i}/{len(samples)}] {model} ERROR: {exc}", flush=True)
        out.append(ctx)
    return out


def _render_md(
    samples: list[dict[str, Any]],
    contexts_a: list[str],
    contexts_b: list[str],
    *,
    model_a: str,
    model_b: str,
) -> str:
    lines: list[str] = []
    lines.append(f"# Contextual Retrieval model A/B — `{model_a}` vs `{model_b}`")
    lines.append("")
    lines.append(f"Generated for **{len(samples)} random chunks** (mixed EN/RU).")
    lines.append("")
    lines.append("Manual review checklist (per chunk):")
    lines.append("- [ ] Sutta ID correct (no hallucinated names)")
    lines.append("- [ ] Pāli diacritics preserved")
    lines.append("- [ ] 50-100 tokens length")
    lines.append("- [ ] Single paragraph, no markdown")
    lines.append("- [ ] Russian Cyrillic handled (when applicable)")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, s in enumerate(samples):
        lines.append(
            f"## #{i + 1} — `{s['canonical_id']}` ({s['language_code']}, {s['translator']})"
        )
        lines.append("")
        body_preview = s["child_text"][:200].replace("\n", " ")
        lines.append(f"**Child text** _(first 200 chars):_ {body_preview}…")
        lines.append("")
        lines.append(f"### A: `{model_a}`")
        lines.append("")
        lines.append(f"> {contexts_a[i]}")
        lines.append("")
        lines.append(f"### B: `{model_b}`")
        lines.append("")
        lines.append(f"> {contexts_b[i]}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines) + "\n"


async def _amain(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = get_settings()
    if not settings.openrouter_api_key:
        print("ERROR: OPENROUTER_API_KEY not set in .env", file=sys.stderr)
        return 1

    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        print(f"Sampling {args.n} chunks from corpus…", flush=True)
        samples = await _fetch_samples(session_maker, args.n)
        print(f"  got {len(samples)} samples")
        print()
        print(f"Running model A: {args.model_a}")
        ctxs_a = _generate_contexts(
            samples, api_key=settings.openrouter_api_key, model=args.model_a
        )
        print()
        print(f"Running model B: {args.model_b}")
        ctxs_b = _generate_contexts(
            samples, api_key=settings.openrouter_api_key, model=args.model_b
        )
    finally:
        await engine.dispose()

    md = _render_md(samples, ctxs_a, ctxs_b, model_a=args.model_a, model_b=args.model_b)
    out = Path(args.out)
    out.write_text(md, encoding="utf-8")
    print()
    print(f"Wrote {out} ({len(md):,} chars)")
    print("Open the file and review side-by-side. Pick winner manually.")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument(
        "--n", type=int, default=DEFAULT_N, help=f"Sample size (default {DEFAULT_N})"
    )
    parser.add_argument(
        "--model-a", default=MODEL_BASELINE, help=f"Baseline model (default {MODEL_BASELINE})"
    )
    parser.add_argument(
        "--model-b", default=MODEL_CANDIDATE, help=f"Candidate model (default {MODEL_CANDIDATE})"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_PATH,
        help=f"Output path (default {DEFAULT_OUT_PATH})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_amain(_parse_args())))
