"""Backfill ``chunk.text_ascii_fold`` (and normalise ``text``) in place.

Why a separate script: the day-4 ingest ran before the cleaner existed,
so live rows carry raw bilara text and a NULL fold. Re-running the
loader is a no-op because the content hash matches. This script reads
every chunk row, applies the cleaner, and updates the two text columns
via an UPDATE — no data loss, no FK disruption.

Idempotent: running twice is fine; chunks that already match their
canonical form are a no-op row-wise.
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
from src.db.models.frbr import Chunk  # noqa: E402
from src.processing.cleaner import to_ascii_fold, to_canonical  # noqa: E402


async def _run(batch_size: int) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    updated = 0
    unchanged = 0
    total = 0
    try:
        async with session_maker() as session:
            start = time.monotonic()
            offset = 0
            while True:
                rows = (
                    await session.execute(
                        sa.select(Chunk.id, Chunk.text, Chunk.text_ascii_fold)
                        .order_by(Chunk.id)
                        .limit(batch_size)
                        .offset(offset)
                    )
                ).all()
                if not rows:
                    break
                for chunk_id, text, fold in rows:
                    total += 1
                    canonical = to_canonical(text)
                    target_fold = to_ascii_fold(canonical) if canonical else None
                    if canonical == text and fold == target_fold:
                        unchanged += 1
                        continue
                    await session.execute(
                        sa.update(Chunk)
                        .where(Chunk.id == chunk_id)
                        .values(text=canonical, text_ascii_fold=target_fold)
                    )
                    updated += 1
                await session.commit()
                offset += batch_size
                print(f"  ... {total} chunks scanned, {updated} updated")
        elapsed = time.monotonic() - start
    finally:
        await engine.dispose()

    print(
        "\n=== Reclean summary ===\n"
        f"  chunks scanned:  {total:>7}\n"
        f"  chunks updated:  {updated:>7}\n"
        f"  chunks unchanged:{unchanged:>7}\n"
        f"  elapsed:         {elapsed:>7.1f}s"
    )
    return 0


def main() -> int:
    return asyncio.run(_run(batch_size=2000))


if __name__ == "__main__":
    raise SystemExit(main())
