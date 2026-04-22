"""Index chunks from Postgres into Qdrant via BGE-M3 encoding.

Usage (from repo root, with ``docker compose up -d`` running both
``dharma-db`` and ``qdrant``)::

    # Full corpus on GPU (expected ~25 min on a 1080 Ti with fp16)
    python scripts/index_qdrant.py

    # Test on 100 chunks first — good sanity check before the full run
    python scripts/index_qdrant.py --limit 100

    # Drop and recreate the collection before indexing
    python scripts/index_qdrant.py --recreate

    # Explicitly pin device (defaults to "auto")
    python scripts/index_qdrant.py --device cuda

Only **child chunks** (``is_parent=false``) are indexed by default —
retrieval is done on children, and parents are looked up via FK when
returning context to the LLM. Pass ``--include-parents`` if you want
the entire chunk table for some other experiment.

The script streams from Postgres in batches of ``--batch-size`` rows,
encodes each batch on the GPU, and upserts into Qdrant. Interrupting
and re-running is safe — upserts key by the chunk UUID.
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
from src.db.models.frbr import Chunk, Expression, Instance, Work  # noqa: E402
from src.embeddings.bge_m3 import BGEM3Encoder  # noqa: E402
from src.embeddings.indexer import (  # noqa: E402
    COLLECTION_NAME,
    ChunkForIndexing,
    ensure_collection,
    index_corpus,
)

logger = logging.getLogger("index_qdrant")


async def _stream_chunks(
    session_maker: async_sessionmaker[sa.ext.asyncio.AsyncSession],
    *,
    batch_size: int,
    include_parents: bool,
    limit: int | None,
) -> AsyncIterator[list[ChunkForIndexing]]:
    """Yield chunk batches joined with Work metadata.

    One query per batch, keyset-paginated on ``chunk.id`` for stable
    ordering regardless of insert time. An offset pagination would
    also work at our scale (~10k rows) but keyset is future-proofed
    for when the corpus hits six figures.
    """
    last_id: UUID | None = None
    chunks_yielded = 0

    async with session_maker() as session:
        while True:
            stmt = (
                sa.select(
                    Chunk.id,
                    Chunk.text,
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
                .order_by(Chunk.id)
                .limit(batch_size)
            )
            if not include_parents:
                stmt = stmt.where(Chunk.is_parent.is_(False))
            if last_id is not None:
                stmt = stmt.where(Chunk.id > last_id)

            rows = (await session.execute(stmt)).all()
            if not rows:
                return

            batch = [
                ChunkForIndexing(
                    chunk_id=row.id,
                    text=row.text,
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

            # Apply --limit *after* we've filled a batch so we still
            # emit exactly `limit` chunks across the run (modulo the
            # final batch being shorter than batch_size).
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

    # QdrantClient is sync — fine here, the embed step dominates wall
    # time and upsert is a single HTTP/gRPC round-trip. Using the async
    # client would complicate the mixed sync-encoder / sync-client path
    # for no measurable win on 10k points.
    client = QdrantClient(url=settings.qdrant_url)

    logger.info("Ensuring collection %r exists (recreate=%s)", COLLECTION_NAME, args.recreate)
    ensure_collection(client, recreate=args.recreate)

    logger.info(
        "Building encoder (device=%s, fp16=%s, model=BAAI/bge-m3)",
        args.device,
        args.use_fp16,
    )
    encoder = BGEM3Encoder(
        device=args.device,
        use_fp16=None if args.use_fp16 == "auto" else args.use_fp16 == "true",
    )

    # Eager-load so the device log line prints before the first batch.
    _ = encoder.device
    logger.info("Encoder ready: device=%s fp16=%s", encoder.device, encoder.uses_fp16)

    start = time.monotonic()
    try:
        stats = await index_corpus(
            client=client,
            encoder=encoder,
            batches=_stream_chunks(
                session_maker,
                batch_size=args.batch_size,
                include_parents=args.include_parents,
                limit=args.limit,
            ),
            encoder_batch_size=args.encoder_batch_size,
            encoder_max_length=args.encoder_max_length,
        )
        elapsed = time.monotonic() - start
        count = client.count(COLLECTION_NAME, exact=True)
    finally:
        await engine.dispose()
        client.close()

    print(
        "\n=== Indexing summary ===\n"
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
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Rows per Postgres fetch and per Qdrant upsert (default: 64).",
    )
    parser.add_argument(
        "--encoder-batch-size",
        type=int,
        default=12,
        help=(
            "Internal BGE-M3 batch size — how many texts encode() processes "
            "in one forward pass (default: 12, safe for 11 GB VRAM with fp16)."
        ),
    )
    parser.add_argument(
        "--encoder-max-length",
        type=int,
        default=2048,
        help="BGE-M3 max_length token budget (default: 2048, matches parent cap).",
    )
    parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="Where to run BGE-M3 (default: auto — CUDA if available, else CPU).",
    )
    parser.add_argument(
        "--use-fp16",
        default="auto",
        choices=["auto", "true", "false"],
        help=(
            "fp16 precision. 'auto' = fp16 on CUDA, fp32 on CPU (recommended). "
            "Forcing 'true' on CPU gives no speed-up and may hurt quality."
        ),
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the collection before indexing.",
    )
    parser.add_argument(
        "--include-parents",
        action="store_true",
        help=(
            "Index parent chunks too (default: children only). Retrieval "
            "uses children; parents are fetched via FK when returning context."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after N chunks — useful for smoke-testing on a small slice.",
    )
    args = parser.parse_args()

    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
