"""Qdrant indexer — writes BGE-M3 vectors into the ``dharma_v1`` collection.

Role in the stack
-----------------
Postgres is the source of truth for text; Qdrant is a *derivative* index
that must be reproducible from Postgres alone. This module is the only
thing that writes into Qdrant; anything that reads (retrieval endpoint,
eval scripts) goes through a separate module in ``src/retrieval/`` that
lands on day 11.

Collection layout
-----------------
Collection name: ``dharma_v1``. The ``v1`` suffix is the embedding-model
generation, not a code version — when we upgrade the encoder in Phase 2
we build ``dharma_v2`` alongside, run A/B, then drop the old one. The
code version (``src.__version__``) is stamped into collection metadata
for traceability but does not drive the name.

Named vectors per point:

* ``bge_m3_dense`` — 1024-dim cosine-similarity vector (BGE-M3 dense head)
* ``bge_m3_sparse`` — learned-weight sparse vector (BGE-M3 lexical head)

Payload per point (everything needed for citations and filtering without
joining back to Postgres on every query):

* ``chunk_id`` — UUID string, duplicates ``point.id`` for non-ID filters
* ``parent_chunk_id`` — UUID of the parent chunk (or ``None`` for parents
  themselves, which we don't index by default)
* ``instance_id`` — UUID of the Instance this chunk belongs to
* ``work_canonical_id`` — e.g. ``mn10`` — the human-readable citation key
* ``segment_id`` — e.g. ``mn10:12.3`` — SuttaCentral segment reference
* ``sequence`` — integer index within the Instance (debugging/citation)
* ``is_parent`` — redundant with ``parent_chunk_id`` but makes filters
  trivial (``filter: is_parent == false``)
* ``token_count`` — cheap to have around for stats / filtering long chunks
* ``pericope_id`` — optional, for dedup of recurring formulas

Text is NOT in the payload: it lives in Postgres and gets joined back
server-side when the retrieval endpoint returns citations.

Design
------
* **Pure dependency injection.** Both the Qdrant client and the encoder
  are passed in by the caller (FastAPI startup or CLI). Tests inject
  in-memory fakes without ever loading the real 2.3 GB BGE-M3 weights or
  spinning up a Qdrant container.
* **Batch-level idempotency.** Point IDs are derived from the chunk
  UUID, so ``upsert`` on the same chunk is a no-op update. Re-running
  the indexer is safe; interrupted runs can resume.
* **No implicit reads from Postgres.** The orchestrator takes an
  ``AsyncIterator[list[ChunkForIndexing]]`` — the CLI wires that up from
  SQLAlchemy, but a test can feed a hand-crafted list. The indexer does
  not know what a Session is.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from src.embeddings.bge_m3 import DENSE_DIM, EncodedBatch

logger = logging.getLogger(__name__)

COLLECTION_NAME: str = "dharma_v1"
DENSE_VECTOR_NAME: str = "bge_m3_dense"
SPARSE_VECTOR_NAME: str = "bge_m3_sparse"


# ---------------------------------------------------------------------------
# Data shape crossing the indexer boundary
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChunkForIndexing:
    """Plain value-object representing one chunk ready to be embedded.

    Decouples the indexer from the SQLAlchemy ORM. The CLI maps from
    ``Chunk`` + ``Instance`` + ``Expression`` + ``Work`` rows to this
    shape; unit tests construct it directly.
    """

    chunk_id: UUID
    text: str
    parent_chunk_id: UUID | None
    instance_id: UUID
    work_canonical_id: str
    segment_id: str | None
    sequence: int
    is_parent: bool
    token_count: int
    pericope_id: str | None = None


@dataclass(slots=True)
class IndexerStats:
    """Running counters for a single ``index_corpus`` invocation.

    Mutable because the orchestrator accumulates as it streams batches;
    callers treat it as read-only after ``index_corpus`` returns.
    """

    batches_processed: int = 0
    chunks_encoded: int = 0
    points_upserted: int = 0
    skipped_empty: int = 0
    # Batch IDs that failed to upsert — the orchestrator continues past
    # transient errors so one bad batch does not lose 9,000 good ones.
    failed_batches: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Protocols for DI (we duck-type the real clients so tests run bare)
# ---------------------------------------------------------------------------


class EncoderProtocol(Protocol):
    """Subset of :class:`src.embeddings.bge_m3.BGEM3Encoder` we use.

    Declaring a Protocol rather than importing the concrete class lets
    the test suite inject a fake that does not need torch at all.
    """

    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int = ...,
        max_length: int = ...,
    ) -> EncodedBatch: ...


class QdrantClientProtocol(Protocol):
    """Structural type matching the slice of ``qdrant_client.QdrantClient``
    we actually call. Covers both the sync and thin-async wrapper.

    We accept the untyped ``Any`` for model arguments because the real
    ``qdrant_client.models`` classes are pydantic models and importing
    them here would drag the entire client into every test module.
    """

    def collection_exists(self, collection_name: str) -> bool: ...

    def create_collection(
        self,
        collection_name: str,
        vectors_config: Any,
        sparse_vectors_config: Any,
        **kwargs: Any,
    ) -> Any: ...

    def delete_collection(self, collection_name: str) -> Any: ...

    def upsert(
        self,
        collection_name: str,
        points: list[Any],
        **kwargs: Any,
    ) -> Any: ...

    def count(self, collection_name: str, exact: bool = ...) -> Any: ...


# ---------------------------------------------------------------------------
# Collection management
# ---------------------------------------------------------------------------


def ensure_collection(
    client: QdrantClientProtocol,
    *,
    collection_name: str = COLLECTION_NAME,
    dense_dim: int = DENSE_DIM,
    recreate: bool = False,
) -> bool:
    """Create the collection if it is missing (or recreate on demand).

    Returns ``True`` if a collection was created (or recreated),
    ``False`` if it already existed and was left alone. The boolean is
    handy for the CLI to print a one-line status and for tests to
    assert on a fresh-vs-existing branch.

    ``recreate=True`` drops the existing collection first. Use it for
    schema changes — e.g. adding a new named vector — where the payload
    format itself is incompatible. Outside of those cases, prefer
    idempotent upserts over recreation.
    """
    from qdrant_client.models import (  # noqa: PLC0415 — defer heavy import
        Distance,
        SparseVectorParams,
        VectorParams,
    )

    exists = client.collection_exists(collection_name)
    if exists and not recreate:
        logger.info("Collection %r already exists; skipping create.", collection_name)
        return False
    if exists and recreate:
        logger.warning("Recreating collection %r (--recreate).", collection_name)
        client.delete_collection(collection_name)

    client.create_collection(
        collection_name=collection_name,
        # Cosine is the standard for normalised sentence embeddings;
        # BGE-M3 already L2-normalises dense outputs internally, so
        # cosine and dot-product give identical rankings — we keep
        # cosine because Qdrant's UI and metrics treat it as default.
        vectors_config={
            DENSE_VECTOR_NAME: VectorParams(size=dense_dim, distance=Distance.COSINE),
        },
        sparse_vectors_config={
            SPARSE_VECTOR_NAME: SparseVectorParams(),
        },
    )
    logger.info("Collection %r created (dense=%dd cosine, sparse=1).", collection_name, dense_dim)
    return True


# ---------------------------------------------------------------------------
# Point construction
# ---------------------------------------------------------------------------


def build_point(chunk: ChunkForIndexing, dense: list[float], sparse: dict[str, float]) -> Any:
    """Assemble a Qdrant ``PointStruct`` for one chunk.

    Split out as a pure function so tests can assert on the exact
    payload shape without spinning up a Qdrant client, and so the
    orchestrator stays small.

    ``sparse`` arrives as ``{token_id_str: weight}`` — BGE-M3 emits
    keys as strings (FlagEmbedding's convention). Qdrant's
    ``SparseVector`` wants parallel int indices + float values, so we
    convert here. Empty sparse maps are valid: BGE-M3 produces them on
    rare-token-only inputs.
    """
    from qdrant_client.models import PointStruct, SparseVector  # noqa: PLC0415

    indices: list[int] = []
    values: list[float] = []
    for token_id_str, weight in sparse.items():
        indices.append(int(token_id_str))
        values.append(float(weight))

    payload: dict[str, Any] = {
        "chunk_id": str(chunk.chunk_id),
        "parent_chunk_id": str(chunk.parent_chunk_id) if chunk.parent_chunk_id else None,
        "instance_id": str(chunk.instance_id),
        "work_canonical_id": chunk.work_canonical_id,
        "segment_id": chunk.segment_id,
        "sequence": chunk.sequence,
        "is_parent": chunk.is_parent,
        "token_count": chunk.token_count,
    }
    if chunk.pericope_id is not None:
        payload["pericope_id"] = chunk.pericope_id

    return PointStruct(
        id=str(chunk.chunk_id),
        vector={
            DENSE_VECTOR_NAME: dense,
            SPARSE_VECTOR_NAME: SparseVector(indices=indices, values=values),
        },
        payload=payload,
    )


def build_points(
    chunks: list[ChunkForIndexing],
    encoded: EncodedBatch,
) -> list[Any]:
    """Zip a chunk batch with its encoded vectors into Qdrant points.

    The encoder contract guarantees ``len(chunks) == len(dense) ==
    len(sparse)`` — we still assert that here because silent misalignment
    between text and vector is the worst class of bug in a RAG pipeline
    (the retrieval still returns something plausible, just wrong).
    """
    if len(chunks) != len(encoded.dense) or len(chunks) != len(encoded.sparse):
        raise RuntimeError(
            "Misaligned batch: "
            f"{len(chunks)} chunks, {len(encoded.dense)} dense, "
            f"{len(encoded.sparse)} sparse."
        )
    return [
        build_point(chunk, dense, sparse)
        for chunk, dense, sparse in zip(chunks, encoded.dense, encoded.sparse, strict=True)
    ]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def index_corpus(
    *,
    client: QdrantClientProtocol,
    encoder: EncoderProtocol,
    batches: AsyncIterator[list[ChunkForIndexing]],
    collection_name: str = COLLECTION_NAME,
    encoder_batch_size: int = 12,
    encoder_max_length: int = 2048,
    continue_on_error: bool = True,
) -> IndexerStats:
    """Stream chunk batches through encoder → Qdrant, accumulate stats.

    The caller is responsible for:

    * Making the collection exist (``ensure_collection`` on the same
      ``client``).
    * Producing ``batches`` — typically pulled from Postgres in
      ``batch_size``-sized chunks, but the indexer doesn't care.

    On per-batch errors: we log and continue when ``continue_on_error``
    is True (the common case for a 10k-point run) so a flaky point
    doesn't lose the rest. Batch indices of failures are captured in
    ``IndexerStats.failed_batches``; the CLI prints them at the end and
    exits non-zero if the list is non-empty.
    """
    stats = IndexerStats()

    async for batch in batches:
        batch_index = stats.batches_processed
        stats.batches_processed += 1
        if not batch:
            stats.skipped_empty += 1
            continue

        texts = [c.text for c in batch]
        try:
            encoded = encoder.encode(
                texts,
                batch_size=encoder_batch_size,
                max_length=encoder_max_length,
            )
        except Exception as exc:  # noqa: BLE001 — orchestrator must keep going
            logger.exception(
                "Encoder failed on batch %d (%d chunks): %s", batch_index, len(batch), exc
            )
            stats.failed_batches.append(batch_index)
            if not continue_on_error:
                raise
            continue

        stats.chunks_encoded += len(batch)

        try:
            points = build_points(batch, encoded)
            client.upsert(collection_name=collection_name, points=points)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Qdrant upsert failed on batch %d: %s", batch_index, exc)
            stats.failed_batches.append(batch_index)
            if not continue_on_error:
                raise
            continue

        stats.points_upserted += len(batch)
        if stats.batches_processed % 10 == 0:
            logger.info(
                "Indexed %d chunks across %d batches (failed: %d)",
                stats.points_upserted,
                stats.batches_processed,
                len(stats.failed_batches),
            )

    logger.info(
        "Indexing complete: %d chunks upserted in %d batches (empty: %d, failed: %d)",
        stats.points_upserted,
        stats.batches_processed,
        stats.skipped_empty,
        len(stats.failed_batches),
    )
    return stats


# ---------------------------------------------------------------------------
# Convenience: synchronous iterable → async batches adapter
# ---------------------------------------------------------------------------


async def batches_from_iterable(
    source: Iterable[list[ChunkForIndexing]],
) -> AsyncIterator[list[ChunkForIndexing]]:
    """Adapt a plain sync iterable of batches to the async contract.

    Makes tests straightforward: the caller builds a list of batches
    in a fixture and wraps it here without touching asyncio.
    """
    for batch in source:
        yield batch
