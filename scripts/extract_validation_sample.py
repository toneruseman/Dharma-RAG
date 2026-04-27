"""Extract a 50-chunk stratified sample for prompt-design validation.

Day-15 workflow uses Claude in-chat to generate sample contextual outputs
(no Anthropic API call yet — that comes on day 16 for the industrial run).
This script pulls a representative sample of (parent, child) pairs into
``docs/contextual/validation_input.md`` so the assistant can read it and
produce contexts inline.

Sample composition (target = 50 child chunks)
---------------------------------------------
* 10 **easy / canonical** — child chunks of well-known suttas: MN 118,
  SN 56.11, DN 22, MN 143, DN 16, MN 22, MN 21, DN 31, SN 45.8, AN 4.41.
  These are textbook examples, contexts must be perfect.
* 20 **medium / random** — randomly sampled child chunks from MN + SN.
  Stress-tests the prompt on chunks the assistant doesn't immediately
  recognise from training.
* 10 **day-14 known misses** — chunks of suttas that day-14 retrieval
  missed despite being in corpus (sn56.11, etc.). The whole point of
  Contextual Retrieval is to fix exactly these.
* 10 **AN / minor** — chunks from less-famous Aṅguttara collections, to
  test whether the prompt holds up on non-canonical material.

Output format is one ``Sample N:`` block per chunk with ``parent_text``
and ``child_text`` clearly labelled. The assistant reads the file and
emits contexts in matching ``Sample N:`` order.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.orm import aliased  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.db.models.frbr import Chunk, Expression, Instance, Work  # noqa: E402

DEFAULT_OUT = Path("docs/contextual/validation_input.md")
SEED = 20260427

CANONICAL_EASY = [
    "mn118",
    "sn56.11",
    "dn22",
    "mn143",
    "dn16",
    "mn22",
    "mn21",
    "dn31",
    "sn45.8",
    "an4.41",
]

DAY14_MISSES = [
    "sn56.11",
    "mn22",
    "mn143",
    "sn45.8",
    "mn9",
    "mn117",
    "sn22.59",
    "an5.38",
    "mn70",
    "an4.94",
    "mn39",
]


async def _fetch_chunks_for_works(
    session_maker: async_sessionmaker,
    canonical_ids: list[str],
    *,
    one_per_work: bool = True,
) -> list[dict]:
    """Pick 1 child chunk per requested work (random within the work).

    Returns dicts with: ``canonical_id``, ``segment_id``, ``child_text``,
    ``parent_text`` (joined via parent_chunk_id), ``chunk_id``.
    """
    out: list[dict] = []
    parent = aliased(Chunk)
    async with session_maker() as session:
        for cid in canonical_ids:
            stmt = (
                select(
                    Chunk.id.label("chunk_id"),
                    Chunk.text.label("child_text"),
                    Chunk.segment_id,
                    Work.canonical_id,
                    parent.text.label("parent_text"),
                )
                .select_from(Chunk)
                .join(Instance, Instance.id == Chunk.instance_id)
                .join(Expression, Expression.id == Instance.expression_id)
                .join(Work, Work.id == Expression.work_id)
                .join(parent, parent.id == Chunk.parent_chunk_id, isouter=True)
                .where(Work.canonical_id == cid)
                .where(Chunk.is_parent.is_(False))
                .order_by(Chunk.segment_id)
            )
            rows = (await session.execute(stmt)).all()
            if not rows:
                print(f"  [skip] {cid}: no child chunks")
                continue
            picked = (
                random.choice(rows)  # noqa: S311 — sampling, not crypto
                if not one_per_work
                else rows[len(rows) // 2]
            )
            out.append(
                {
                    "canonical_id": picked.canonical_id,
                    "segment_id": picked.segment_id or "",
                    "child_text": picked.child_text,
                    "parent_text": picked.parent_text or "(no parent)",
                    "chunk_id": str(picked.chunk_id),
                }
            )
    return out


async def _fetch_random_chunks(
    session_maker: async_sessionmaker,
    *,
    n: int,
    work_prefix: tuple[str, ...] | None = None,
    exclude_ids: set[str],
) -> list[dict]:
    """Random child chunks across the corpus (optionally filtered by prefix).

    ``work_prefix`` like ``("mn", "sn")`` keeps only those collections.
    ``exclude_ids`` lets the caller drop chunks already picked by other
    strata (avoid duplicates).
    """
    out: list[dict] = []
    parent = aliased(Chunk)
    async with session_maker() as session:
        stmt = (
            select(
                Chunk.id.label("chunk_id"),
                Chunk.text.label("child_text"),
                Chunk.segment_id,
                Work.canonical_id,
                parent.text.label("parent_text"),
            )
            .select_from(Chunk)
            .join(Instance, Instance.id == Chunk.instance_id)
            .join(Expression, Expression.id == Instance.expression_id)
            .join(Work, Work.id == Expression.work_id)
            .join(parent, parent.id == Chunk.parent_chunk_id, isouter=True)
            .where(Chunk.is_parent.is_(False))
        )
        rows = (await session.execute(stmt)).all()
        if work_prefix:
            rows = [r for r in rows if any(r.canonical_id.startswith(p) for p in work_prefix)]
        rows = [r for r in rows if str(r.chunk_id) not in exclude_ids]
        random.shuffle(rows)
        picked = rows[:n]
        for r in picked:
            out.append(
                {
                    "canonical_id": r.canonical_id,
                    "segment_id": r.segment_id or "",
                    "child_text": r.child_text,
                    "parent_text": r.parent_text or "(no parent)",
                    "chunk_id": str(r.chunk_id),
                }
            )
    return out


def _render(samples: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# Contextual Retrieval — validation input (50 sample chunks)")
    lines.append("")
    lines.append(
        "This file is fed to the in-chat assistant for prompt-design validation. "
        "The assistant reads each `Sample N` block and produces a 50-100 token "
        "context describing where the child chunk lives, then we eyeball the result."
    )
    lines.append("")
    lines.append(f"**Generated**: deterministic with seed={SEED}, n={len(samples)}")
    lines.append("")
    for i, s in enumerate(samples, 1):
        cat = s.get("_category", "")
        lines.append(
            f"## Sample {i:02d}: `{s['canonical_id']}` / `{s['segment_id'] or '-'}` ({cat})"
        )
        lines.append("")
        lines.append("**Parent text** (for context, may span the whole passage):")
        lines.append("")
        lines.append("```")
        lines.append((s["parent_text"] or "(no parent)").strip())
        lines.append("```")
        lines.append("")
        lines.append("**Child chunk to contextualize**:")
        lines.append("")
        lines.append("```")
        lines.append(s["child_text"].strip())
        lines.append("```")
        lines.append("")
    return "\n".join(lines) + "\n"


async def _amain(args: argparse.Namespace) -> int:
    random.seed(SEED)
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    print(f"Extracting validation sample → {args.out}")
    print("Stratum 1/4: 10 easy/canonical")
    easy = await _fetch_chunks_for_works(sm, CANONICAL_EASY)
    for s in easy:
        s["_category"] = "easy / canonical"

    picked_ids = {s["chunk_id"] for s in easy}
    print(f"  picked {len(easy)}, excluding from later strata")

    print("Stratum 2/4: 11 day-14 known misses")
    misses = await _fetch_chunks_for_works(sm, [m for m in DAY14_MISSES if m not in CANONICAL_EASY])
    for s in misses:
        s["_category"] = "day-14 known miss"
    picked_ids.update({s["chunk_id"] for s in misses})
    print(f"  picked {len(misses)}")

    print("Stratum 3/4: 20 medium MN/SN random")
    medium = await _fetch_random_chunks(sm, n=20, work_prefix=("mn", "sn"), exclude_ids=picked_ids)
    for s in medium:
        s["_category"] = "medium / random MN-SN"
    picked_ids.update({s["chunk_id"] for s in medium})
    print(f"  picked {len(medium)}")

    print("Stratum 4/4: AN minor random (fill to 50)")
    n_remaining = max(0, 50 - len(easy) - len(misses) - len(medium))
    minor = await _fetch_random_chunks(
        sm, n=n_remaining, work_prefix=("an", "ud"), exclude_ids=picked_ids
    )
    for s in minor:
        s["_category"] = "minor / AN-Ud"
    print(f"  picked {len(minor)}")

    samples = easy + misses + medium + minor
    print(f"Total samples: {len(samples)}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_render(samples), encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
    await engine.dispose()
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return p.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_amain(_parse_args())))
