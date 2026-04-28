"""Re-encode contextualized chunks and write to Qdrant ``dharma_v2``.

Day-16 step 2: takes the ``context_text`` produced by
``scripts/contextualize_corpus.py``, prepends it to each child chunk's
text, runs the result through BGE-M3, and upserts into a *new* Qdrant
collection so the existing ``dharma_v1`` (no context) stays untouched.
Day-17's A/B eval queries both collections side by side.

GPU note
--------
**This script wants a free GPU.** BGE-M3 forward pass on the prefixed
text is the expensive bit — about 5-10 minutes on a free 1080 Ti for
6,478 chunks at fp16. Free the GPU from Whisper transcription before
running.

Usage::

    # First run: create dharma_v2, encode everything, upsert
    python scripts/reindex_qdrant_v2.py --recreate

    # Re-run after iteration: keep collection, replace points by ID
    python scripts/reindex_qdrant_v2.py

    # Smoke on a slice
    python scripts/reindex_qdrant_v2.py --limit 100 --recreate

Only chunks where ``context_text IS NOT NULL`` are indexed — running
this before ``contextualize_corpus.py`` finishes is safe (just less
useful). Re-running is idempotent: Qdrant upserts by chunk UUID.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sqlalchemy as sa  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from src.config import get_settings  # noqa: E402
from src.contextual.contextualizer import format_prefixed_chunk  # noqa: E402
from src.db.models.frbr import Chunk, Expression, Instance, Work  # noqa: E402
from src.embeddings.bge_m3 import BGEM3Encoder  # noqa: E402
from src.embeddings.indexer import (  # noqa: E402
    ChunkForIndexing,
    ensure_collection,
    index_corpus,
)

COLLECTION_V2_NAME: str = "dharma_v2"
"""New collection holding the contextualized embeddings.

Kept distinct from ``dharma_v1`` so day-17 can A/B them without any
code branching — just point :func:`hybrid_search` at the desired
collection name. When v2 wins decisively in day-17 we may eventually
deprecate v1, but during Phase 1 both live in parallel."""

logger = logging.getLogger("reindex_qdrant_v2")


async def _stream_contextualized(
    session_maker: async_sessionmaker[sa.ext.asyncio.AsyncSession],
    *,
    batch_size: int,
    limit: int | None,
) -> AsyncIterator[list[ChunkForIndexing]]:
    """Yield batches of child chunks with ``context_text`` populated.

    Filters out:
    * Parent chunks (``is_parent=true``) — retrieval indexes children only.
    * Children with NULL ``context_text`` — those would degrade to
      day-12 behaviour, defeating the whole point.

    Each yielded :class:`ChunkForIndexing.text` is the **prefixed**
    text (context + chunk), so the encoder sees what we want indexed,
    not the raw chunk.
    """
    last_id: UUID | None = None
    chunks_yielded = 0

    async with session_maker() as session:
        while True:
            stmt = (
                sa.select(
                    Chunk.id,
                    Chunk.text,
                    Chunk.context_text,
                    Chunk.parent_chunk_id,
                    Chunk.instance_id,
                    Chunk.sequence,
                    Chunk.is_parent,
                    Chunk.token_count,
                    Chunk.segment_id,
                    Chunk.pericope_id,
                    Work.canonical_id.label("work_canonical_id"),
                )
                .select_from(Chunk)
                .join(Instance, Instance.id == Chunk.instance_id)
                .join(Expression, Expression.id == Instance.expression_id)
                .join(Work, Work.id == Expression.work_id)
                .where(Chunk.is_parent.is_(False))
                .where(Chunk.context_text.is_not(None))
                .order_by(Chunk.id)
                .limit(batch_size)
            )
            if last_id is not None:
                stmt = stmt.where(Chunk.id > last_id)

            rows = (await session.execute(stmt)).all()
            if not rows:
                return

            batch = [
                ChunkForIndexing(
                    chunk_id=row.id,
                    text=format_prefixed_chunk(context=row.context_text, child_text=row.text),
                    parent_chunk_id=row.parent_chunk_id,
                    instance_id=row.instance_id,
                    work_canonical_id=row.work_canonical_id,
                    segment_id=row.segment_id,
                    sequence=row.sequence,
                    is_parent=row.is_parent,
                    token_count=row.token_count,
                    pericope_id=row.pericope_id,
                )
                for row in rows
            ]

            if limit is not None and chunks_yielded + len(batch) > limit:
                batch = batch[: limit - chunks_yielded]
                if batch:
                    yield batch
                    chunks_yielded += len(batch)
                return

            yield batch
            chunks_yielded += len(batch)
            last_id = rows[-1].id

            if len(rows) < batch_size:
                return


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, future=True, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    # Sanity check: count how many chunks have context_text before we
    # spin up the model. Useful when running reindex while
    # contextualize_corpus.py is still in flight.
    async with session_maker() as session:
        ready = (
            await session.execute(
                sa.select(sa.func.count())
                .select_from(Chunk)
                .where(Chunk.is_parent.is_(False))
                .where(Chunk.context_text.is_not(None))
            )
        ).scalar_one()
        total = (
            await session.execute(
                sa.select(sa.func.count()).select_from(Chunk).where(Chunk.is_parent.is_(False))
            )
        ).scalar_one()
    print(f"Children with context_text: {ready:,} / {total:,}")
    if ready == 0:
        print("Nothing to index — run scripts/contextualize_corpus.py first.")
        await engine.dispose()
        return 1

    client = QdrantClient(url=settings.qdrant_url)
    logger.info(
        "Ensuring collection %r exists (recreate=%s)",
        COLLECTION_V2_NAME,
        args.recreate,
    )
    ensure_collection(client, collection_name=COLLECTION_V2_NAME, recreate=args.recreate)

    logger.info(
        "Building encoder (device=%s, fp16=%s, model=BAAI/bge-m3)",
        args.device,
        args.use_fp16,
    )
    encoder = BGEM3Encoder(
        device=args.device,
        use_fp16=None if args.use_fp16 == "auto" else args.use_fp16 == "true",
    )
    _ = encoder.device
    logger.info("Encoder ready: device=%s fp16=%s", encoder.device, encoder.uses_fp16)

    start = time.monotonic()
    try:
        stats = await index_corpus(
            client=client,
            encoder=encoder,
            batches=_stream_contextualized(
                session_maker, batch_size=args.batch_size, limit=args.limit
            ),
            encoder_batch_size=args.encoder_batch_size,
            encoder_max_length=args.encoder_max_length,
            collection_name=COLLECTION_V2_NAME,
        )
        elapsed = time.monotonic() - start
        count = client.count(COLLECTION_V2_NAME, exact=True)
    finally:
        await engine.dispose()
        client.close()

    print(
        "\n=== Indexing summary ===\n"
        f"  collection:        {COLLECTION_V2_NAME}\n"
        f"  batches processed: {stats.batches_processed:>6}\n"
        f"  chunks encoded:    {stats.chunks_encoded:>6}\n"
        f"  points upserted:   {stats.points_upserted:>6}\n"
        f"  skipped empty:     {stats.skipped_empty:>6}\n"
        f"  failed batches:    {len(stats.failed_batches):>6}"
        f"{'  ' + str(stats.failed_batches) if stats.failed_batches else ''}\n"
        f"  collection size:   {count.count:>6} (after run)\n"
        f"  elapsed:           {elapsed:>6.1f}s"
    )
    return 0 if not stats.failed_batches else 1


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Rows per Postgres fetch and per Qdrant upsert (default: 64)",
    )
    parser.add_argument(
        "--encoder-batch-size",
        type=int,
        default=12,
        help="BGE-M3 forward-pass batch (default: 12, safe for 11 GB VRAM)",
    )
    parser.add_argument(
        "--encoder-max-length",
        type=int,
        default=2048,
        help="BGE-M3 max_length token budget (default: 2048)",
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="Where to run BGE-M3 (default: auto = CUDA if available)",
    )
    parser.add_argument(
        "--use-fp16",
        default="auto",
        choices=["auto", "true", "false"],
        help="fp16 precision (default: auto = fp16 on CUDA, fp32 on CPU)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate dharma_v2 before indexing",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after N chunks (smoke run)",
    )
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
