"""Day-16 industrial run: generate Contextual Retrieval contexts for the corpus.

Workflow
--------
1. Pull every child chunk from Postgres along with its parent text.
2. For each child not already contextualized at the current
   ``PROMPT_VERSION_V2``, call OpenRouter (default Anthropic Haiku 3.5)
   with ``cache_control: {"type": "ephemeral"}`` on the parent block.
3. Persist the result back to ``chunk.context_text`` /
   ``context_version`` / ``context_model`` immediately — so a crash
   midway is recoverable: re-run skips chunks already populated.
4. Track running token usage + cost; abort if the user-set
   ``--cost-cap-usd`` is breached.

Smoke vs industrial
-------------------
* ``--limit N`` runs only the first N children (5-10 is the typical
  smoke). Output is printed to stdout so the user can eyeball quality
  before committing to the full corpus.
* No flag → industrial run on all eligible children.
* ``--dry-run`` skips the API entirely; uses ``len(child) ≈ tokens``
  heuristic to project total cost. Useful before spending real money.

GPU note
--------
This script only calls the LLM API and writes Postgres. **No GPU
needed.** The downstream re-embed (``scripts/reindex_qdrant_v2.py``,
day-16 step 2) is what wants free GPU.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from uuid import UUID

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import aliased  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.contextual.contextualizer import PROMPT_VERSION_V2  # noqa: E402
from src.contextual.providers.openrouter import (  # noqa: E402
    OpenRouterProvider,
    estimate_cost_usd,
)
from src.db.models.frbr import Chunk  # noqa: E402

logger = logging.getLogger(__name__)


async def _fetch_pending(
    session_maker: async_sessionmaker,
    *,
    prompt_version: str,
    force: bool,
    limit: int | None,
) -> list[tuple[UUID, UUID, str, str]]:
    """Return ``(child_id, parent_id, parent_text, child_text)`` rows.

    Skips child chunks already contextualized at the current
    ``prompt_version`` unless ``force=True``. Children with no parent
    (rare — only if rechunk produced orphans) are dropped silently.
    """
    parent = aliased(Chunk)
    stmt = (
        select(
            Chunk.id.label("child_id"),
            parent.id.label("parent_id"),
            parent.text.label("parent_text"),
            Chunk.text.label("child_text"),
        )
        .select_from(Chunk)
        .join(parent, parent.id == Chunk.parent_chunk_id)
        .where(Chunk.is_parent.is_(False))
        .where(Chunk.parent_chunk_id.is_not(None))
        # Order by parent so all children of one parent process back-to-
        # back. With concurrent workers + Anthropic's 5-minute ephemeral
        # cache, this lets the cache fire when parents exceed the 2048-
        # token threshold (most don't, but the larger ones benefit).
        .order_by(Chunk.parent_chunk_id, Chunk.sequence)
    )
    if not force:
        stmt = stmt.where(
            (Chunk.context_version.is_(None)) | (Chunk.context_version != prompt_version)
        )
    if limit is not None:
        stmt = stmt.limit(limit)

    async with session_maker() as session:
        rows = (await session.execute(stmt)).all()
    return [(r.child_id, r.parent_id, r.parent_text, r.child_text) for r in rows]


async def _persist(
    session_maker: async_sessionmaker,
    *,
    child_id: UUID,
    context_text: str,
    prompt_version: str,
    model_id: str,
) -> None:
    """Write one context back to Postgres in its own short transaction."""
    async with session_maker() as session:
        await session.execute(
            update(Chunk)
            .where(Chunk.id == child_id)
            .values(
                context_text=context_text,
                context_version=prompt_version,
                context_model=model_id,
            )
        )
        await session.commit()


def _approx_tokens(text: str) -> int:
    """Rough token count (chars/4) for dry-run cost projection."""
    return max(1, len(text) // 4)


def _print_progress(
    *,
    idx: int,
    total: int,
    last_latency_s: float,
    snap: dict,
) -> None:
    """One-line status update during the run."""
    pct = 100 * idx / total if total else 0
    cost = snap["estimated_cost_usd"]
    print(
        f"  [{idx:>5}/{total}] {pct:5.1f}%  "
        f"last={last_latency_s:.1f}s  "
        f"calls={snap['calls']}  "
        f"in={snap['input_tokens']:,}  "
        f"out={snap['output_tokens']:,}  "
        f"cache_w={snap['cache_write_tokens']:,}  "
        f"cache_r={snap['cache_read_tokens']:,}  "
        f"cost=${cost:.4f}",
        flush=True,
    )


async def _amain(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = get_settings()
    if not settings.openrouter_api_key:
        print("ERROR: OPENROUTER_API_KEY is not set in .env", file=sys.stderr)
        return 2

    model = args.model or settings.context_model
    print(f"Provider: openrouter/{model}")
    print(f"Prompt version: {PROMPT_VERSION_V2}")

    engine = create_async_engine(settings.database_url, future=True, echo=False)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    rows = await _fetch_pending(
        sm, prompt_version=PROMPT_VERSION_V2, force=args.force, limit=args.limit
    )
    print(f"Pending chunks: {len(rows)} (force={args.force}, limit={args.limit})")
    if not rows:
        print("Nothing to do — corpus already at this prompt_version.")
        await engine.dispose()
        return 0

    # Dry-run: project cost via char/4 heuristic.
    if args.dry_run:
        # Group by parent to count writes vs reads.
        per_parent: dict[UUID, list[tuple[str, str]]] = {}
        for _cid, pid, ptxt, ctxt in rows:
            per_parent.setdefault(pid, []).append((ptxt, ctxt))
        total_input = 0
        total_cache_write = 0
        total_cache_read = 0
        total_output = 0
        for _parent_id, group in per_parent.items():
            ptxt = group[0][0]
            ptokens = _approx_tokens(ptxt)
            # First call: cache write on parent + base input on child.
            ctokens_first = _approx_tokens(group[0][1])
            total_cache_write += ptokens
            total_input += ctokens_first
            total_output += 75  # target context length
            # Remaining calls: cache read on parent + base on child.
            for _, ctxt in group[1:]:
                total_cache_read += ptokens
                total_input += _approx_tokens(ctxt)
                total_output += 75
        projected = estimate_cost_usd(
            input_tokens=total_input,
            output_tokens=total_output,
            cache_write_tokens=total_cache_write,
            cache_read_tokens=total_cache_read,
        )
        print("\nDry-run projection (heuristic chars/4 token count):")
        print(f"  parents:           {len(per_parent):>10,}")
        print(f"  children:          {len(rows):>10,}")
        print(f"  input tokens:      {total_input:>10,}")
        print(f"  output tokens:     {total_output:>10,}")
        print(f"  cache write toks:  {total_cache_write:>10,}")
        print(f"  cache read toks:   {total_cache_read:>10,}")
        print(f"  projected cost:    ${projected:>9.2f}")
        print(f"  cost cap:          ${args.cost_cap_usd:>9.2f}")
        if projected > args.cost_cap_usd:
            print(
                f"  ⚠ Projected cost EXCEEDS cap. Re-run with --cost-cap-usd >={projected:.2f} "
                f"to permit."
            )
            await engine.dispose()
            return 3
        await engine.dispose()
        return 0

    # Real run with bounded concurrency. The OpenRouter SDK call is sync,
    # so we run each via asyncio.to_thread; a semaphore caps concurrency
    # to avoid hitting OpenRouter rate limits and to keep memory bounded.
    provider = OpenRouterProvider(api_key=settings.openrouter_api_key, model=model)
    print(f"Cost cap: ${args.cost_cap_usd:.2f}")
    print(f"Concurrency: {args.concurrency} parallel workers")
    print()

    semaphore = asyncio.Semaphore(args.concurrency)
    completed_count = 0
    completed_lock = asyncio.Lock()
    abort_event = asyncio.Event()
    progress_every = max(1, len(rows) // 50)
    t_start = time.perf_counter()
    first_few_outputs: list[tuple[int, UUID, str]] = []

    async def _process_one(
        child_id: UUID,
        parent_text: str,
        child_text: str,
    ) -> None:
        nonlocal completed_count
        if abort_event.is_set():
            return
        async with semaphore:
            if abort_event.is_set():
                return
            t0 = time.perf_counter()
            try:
                context = await asyncio.to_thread(
                    provider.generate_context,
                    parent_text=parent_text,
                    child_text=child_text,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed on child %s: %s", child_id, exc)
                print(f"\nABORT on child {child_id}: {exc}", file=sys.stderr)
                abort_event.set()
                return

            await _persist(
                sm,
                child_id=child_id,
                context_text=context,
                prompt_version=PROMPT_VERSION_V2,
                model_id=provider.model_id,
            )
            latency = time.perf_counter() - t0
            snap = provider.usage.snapshot()

            async with completed_lock:
                completed_count += 1
                local_idx = completed_count

            if local_idx <= 10:
                first_few_outputs.append((local_idx, child_id, context))
            elif args.verbose or local_idx % progress_every == 0:
                _print_progress(idx=local_idx, total=len(rows), last_latency_s=latency, snap=snap)

            if snap["estimated_cost_usd"] > args.cost_cap_usd:
                print(
                    f"\nCOST CAP REACHED at child {local_idx}: "
                    f"${snap['estimated_cost_usd']:.4f} > ${args.cost_cap_usd:.2f}",
                    file=sys.stderr,
                )
                abort_event.set()

    tasks = [_process_one(cid, ptxt, ctxt) for cid, _pid, ptxt, ctxt in rows]
    await asyncio.gather(*tasks)
    aborted = abort_event.is_set()

    if first_few_outputs:
        print("\n--- First contexts (sample for eyeball check) ---")
        for local_idx, child_id, context in sorted(first_few_outputs):
            print(f"\n[{local_idx}/{len(rows)}] child={child_id}")
            print(f"  context: {context}")

    elapsed = time.perf_counter() - t_start
    final = provider.usage.snapshot()
    print()
    print(f"=== Done {'(ABORTED)' if aborted else ''} ===")
    print(f"  elapsed:            {elapsed:.1f}s")
    print(f"  calls:              {final['calls']:,}")
    print(f"  input tokens:       {final['input_tokens']:,}")
    print(f"  output tokens:      {final['output_tokens']:,}")
    print(f"  cache write tokens: {final['cache_write_tokens']:,}")
    print(f"  cache read tokens:  {final['cache_read_tokens']:,}")
    print(f"  spent:              ${final['estimated_cost_usd']:.4f}")

    await engine.dispose()
    return 1 if aborted else 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N pending children (smoke run)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Estimate cost via char/4 heuristic without calling API",
    )
    p.add_argument(
        "--cost-cap-usd",
        type=float,
        default=20.0,
        help="Hard ceiling on accumulated cost. Run aborts when exceeded.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Re-contextualize even chunks already at the current prompt_version",
    )
    p.add_argument(
        "--model",
        default=None,
        help="Override OpenRouter model (default: settings.context_model)",
    )
    p.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Number of parallel API calls (default: 5; set 1 for sequential)",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print every chunk's progress line (default: first 10 + every Nth)",
    )
    return p.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_amain(_parse_args())))
