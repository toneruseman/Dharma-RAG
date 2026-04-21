"""Rebuild chunks per Instance using the parent/child structural chunker.

The rag-day-04 loader created one flat Chunk per bilara segment.
rag-day-06 backfilled canonical text + ASCII fold on those rows. Now
rag-day-07 replaces that flat layout with parent/child: each Instance
drops its chunks and re-emits the structured version produced by
``src.processing.chunker``.

Why a separate script instead of rerunning the ingest:
* The ingest loader short-circuits on ``content_hash`` match — re-running
  it is a no-op (exactly what we want for normal use). Rechunking is a
  deliberate schema-migration-like event, so it gets its own entry point.
* It lets us stream per-Instance, commit between each, and recover from
  a crash without losing the whole batch.

Idempotent: if the rows under an Instance already look like parent/child
(i.e. contain at least one row with ``is_parent=True``), skip the
Instance.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.db.models.frbr import Chunk, Instance  # noqa: E402
from src.processing.chunker import SegmentInput, chunk_segments  # noqa: E402
from src.processing.cleaner import to_ascii_fold  # noqa: E402


async def _rechunk_one_instance(session, instance_id) -> tuple[int, int, int]:
    """Replace flat chunks for a single Instance with parent/child.

    Returns (deleted_count, inserted_count, was_already_structured).
    """
    # Fast-path: if any chunk is already a parent, assume the Instance
    # is up to date and skip. Cheaper than comparing full structure.
    already = (
        await session.execute(
            sa.select(sa.func.count())
            .select_from(Chunk)
            .where(Chunk.instance_id == instance_id, Chunk.is_parent.is_(True))
        )
    ).scalar_one()
    if already:
        return (0, 0, 1)

    # Load existing flat chunks in sequence order; they already carry
    # canonical (NFC + IAST) text from the day-6 cleaner pass.
    rows = (
        await session.execute(
            sa.select(Chunk.segment_id, Chunk.text)
            .where(Chunk.instance_id == instance_id)
            .order_by(Chunk.sequence)
        )
    ).all()
    if not rows:
        return (0, 0, 0)

    # Drop rows with missing segment_id or empty text; pre-day-6 data
    # always populated both, but staying defensive means rechunk never
    # pollutes ``metadata_json.segment_ids`` with empty strings.
    segments = [
        SegmentInput(segment_id=seg_id, text=text) for seg_id, text in rows if seg_id and text
    ]
    parents = chunk_segments(segments)

    # Delete old flat rows. ``parent_chunk_id`` FK is SET NULL so order
    # does not matter here, but staying tidy is nice.
    deleted = (
        await session.execute(sa.delete(Chunk).where(Chunk.instance_id == instance_id))
    ).rowcount or 0

    inserted = 0
    sequence = 0
    for parent in parents:
        parent_row = Chunk(
            instance_id=instance_id,
            sequence=sequence,
            text=parent.text,
            text_ascii_fold=to_ascii_fold(parent.text),
            token_count=parent.token_count,
            is_parent=True,
            segment_id=parent.segment_ids[0] if parent.segment_ids else None,
            metadata_json={
                "stage": "parent",
                "segment_ids": parent.segment_ids,
                "position": parent.position,
                "child_count": len(parent.children),
            },
        )
        session.add(parent_row)
        await session.flush()
        inserted += 1
        sequence += 1

        for child in parent.children:
            session.add(
                Chunk(
                    instance_id=instance_id,
                    parent_chunk_id=parent_row.id,
                    sequence=sequence,
                    text=child.text,
                    text_ascii_fold=to_ascii_fold(child.text),
                    token_count=child.token_count,
                    is_parent=False,
                    segment_id=child.segment_ids[0] if child.segment_ids else None,
                    metadata_json={
                        "stage": "child",
                        "segment_ids": child.segment_ids,
                        "position_in_parent": child.position_in_parent,
                    },
                )
            )
            inserted += 1
            sequence += 1
    await session.flush()
    return (deleted, inserted, 0)


async def _run() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    totals = {"instances": 0, "skipped": 0, "deleted": 0, "inserted": 0}
    try:
        async with session_maker() as session:
            start = time.monotonic()
            instance_ids = (
                (await session.execute(sa.select(Instance.id).order_by(Instance.id)))
                .scalars()
                .all()
            )
            total = len(instance_ids)
            for idx, inst_id in enumerate(instance_ids, 1):
                deleted, inserted, skipped = await _rechunk_one_instance(session, inst_id)
                totals["instances"] += 1
                totals["deleted"] += deleted
                totals["inserted"] += inserted
                totals["skipped"] += skipped
                await session.commit()
                if idx % 200 == 0 or idx == total:
                    print(
                        f"  ... {idx}/{total} instances — "
                        f"deleted {totals['deleted']:,}, inserted {totals['inserted']:,}"
                    )
        elapsed = time.monotonic() - start
    finally:
        await engine.dispose()

    print(
        "\n=== Rechunk summary ===\n"
        f"  instances scanned:  {totals['instances']:>7,}\n"
        f"  instances skipped:  {totals['skipped']:>7,} (already parent/child)\n"
        f"  chunks deleted:     {totals['deleted']:>7,}\n"
        f"  chunks inserted:    {totals['inserted']:>7,}\n"
        f"  elapsed:            {elapsed:>7.1f}s"
    )
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
