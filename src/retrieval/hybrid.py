"""Hybrid retrieval orchestrator — encode → 3 channels in parallel → RRF → enrich.

End-to-end shape
----------------
1. Encode the query once via BGE-M3 (produces dense + sparse together).
2. Dispatch three channels concurrently:
   * dense:  ``dense_search`` against Qdrant ``bge_m3_dense``
   * sparse: ``sparse_search`` against Qdrant ``bge_m3_sparse``
   * bm25:   ``bm25.search`` against Postgres FTS
3. Fuse the three ranked lists with RRF (k=60, equal weights).
4. Truncate to the requested ``top_k`` (default 20).
5. JOIN Postgres once for ``chunk.text`` + ``work.canonical_id`` +
   ``segment_id`` + ``parent_chunk_id`` + ``is_parent``.
6. Return a ``HybridHit`` per surviving doc, with provenance.

Why a single orchestrator instead of three separate calls
---------------------------------------------------------
* **Encode once.** BGE-M3 is the slowest step (~30 ms GPU, ~200 ms CPU).
  Doing it in the orchestrator and feeding both Qdrant channels keeps
  latency near the max of the three channels rather than their sum.
* **Single Postgres round-trip for enrichment.** Qdrant returns just
  IDs; BM25 already has metadata. We unify by re-fetching everything
  from Postgres in one batched ``WHERE chunk.id IN (…)`` query, so the
  shape of what the API endpoint sees is identical regardless of which
  channel found a doc.
* **Single place to add concerns.** Reranker (day 13) and parent-child
  expansion (day 18) plug in here without touching the channel modules.

Defaults locked from the day-12 design discussion
-------------------------------------------------
* Equal channel weights (no per-channel boost). RRF on rank, not score.
* No query-encoding cache (deferred to day-18 semantic cache).
* Empty results return ``[]``, not 404 — the API layer translates that.
* asyncio.gather for channel parallelism.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Protocol

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.frbr import Chunk, Expression, Instance, Work
from src.embeddings.bge_m3 import EncodedBatch
from src.retrieval import bm25, dense, sparse
from src.retrieval.rrf import DEFAULT_K, FusedHit, reciprocal_rank_fusion
from src.retrieval.schemas import ChannelHit, HybridHit

logger = logging.getLogger(__name__)


# Per-channel candidate pool size. Plan calls for top-30 each → RRF →
# top-20 fused. The 30/20 ratio gives the union ~50-90 candidates
# depending on overlap, which is plenty of recall for downstream
# reranking on day 13.
DEFAULT_PER_CHANNEL_LIMIT: int = 30
DEFAULT_TOP_K: int = 20


class EncoderProtocol(Protocol):
    """Subset of :class:`src.embeddings.bge_m3.BGEM3Encoder` we use.

    Declaring it as a Protocol keeps the orchestrator testable without
    loading the real 2.3 GB BGE-M3 weights. Day-13 may need to extend
    the protocol with per-token attention if Contextual Retrieval grows
    a feature there; for now the simple encode signature is enough.
    """

    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int = ...,
        max_length: int = ...,
    ) -> EncodedBatch: ...


class QdrantQueryProtocol(Protocol):
    """Same shape the dense + sparse modules expect."""

    def query_points(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        ...


@dataclass(frozen=True, slots=True)
class HybridSearchTimings:
    """Per-stage wall-clock times (seconds) for observability.

    Plan target: 20 candidates in <200 ms end-to-end. These timings
    let the API layer surface a single ``latency_ms`` field while a
    smoke script can drill into where the time went.
    """

    encode_s: float
    channels_s: float
    fusion_s: float
    enrich_s: float
    total_s: float


async def hybrid_search(
    *,
    query: str,
    encoder: EncoderProtocol,
    qdrant_client: QdrantQueryProtocol,
    db_session: AsyncSession,
    top_k: int = DEFAULT_TOP_K,
    per_channel_limit: int = DEFAULT_PER_CHANNEL_LIMIT,
    rrf_k: int = DEFAULT_K,
) -> tuple[list[HybridHit], HybridSearchTimings]:
    """Run all three channels for ``query`` and return fused-and-enriched hits.

    Parameters
    ----------
    query:
        Free-form user query. Empty strings return ``([], timings)``
        without invoking the encoder or any DB call.
    encoder:
        BGE-M3 encoder. Must satisfy :class:`EncoderProtocol`.
    qdrant_client:
        QdrantClient (production) or fake (tests).
    db_session:
        Open async session for both BM25 (Postgres FTS) and the final
        enrichment JOIN. Caller-owned, no commit issued by us.
    top_k:
        Final number of fused hits to return. Default 20 matches the
        day-12 plan's gate.
    per_channel_limit:
        Top-N pulled from each individual channel before fusion.
    rrf_k:
        Flattening constant for RRF (default 60, see ``rrf.py`` for the
        rationale).
    """
    t_start = time.perf_counter()
    if not query or not query.strip():
        return [], HybridSearchTimings(0.0, 0.0, 0.0, 0.0, 0.0)

    # Stage 1: encode once. Synchronous in BGE-M3, but we wrap with
    # ``asyncio.to_thread`` so a slow encode does not block the event
    # loop (and other channels' Postgres / Qdrant calls can still
    # progress concurrently if the application has more than one
    # in-flight request).
    t_encode = time.perf_counter()
    encoded = await asyncio.to_thread(encoder.encode, [query])
    encode_s = time.perf_counter() - t_encode
    if not encoded.dense or not encoded.sparse:
        # Should not happen on a normal query, but treat defensively.
        return [], HybridSearchTimings(encode_s, 0.0, 0.0, 0.0, encode_s)
    dense_vec = encoded.dense[0]
    sparse_weights = encoded.sparse[0]

    # Stage 2: three channels in parallel. Qdrant client is sync; wrap
    # with ``to_thread`` so they run concurrently with the BM25 call.
    t_channels = time.perf_counter()
    dense_task = asyncio.to_thread(
        dense.dense_search, qdrant_client, dense_vec, limit=per_channel_limit
    )
    sparse_task = asyncio.to_thread(
        sparse.sparse_search, qdrant_client, sparse_weights, limit=per_channel_limit
    )
    bm25_task = bm25.search(db_session, query, limit=per_channel_limit)
    dense_hits, sparse_hits, bm25_hits = await asyncio.gather(dense_task, sparse_task, bm25_task)
    channels_s = time.perf_counter() - t_channels

    # Stage 3: RRF over the three ranked lists. We type the value as
    # ``list[Hashable]`` to match the fuser's signature — UUID is
    # hashable but ``dict`` is invariant in its value type, so an
    # explicit annotation avoids a mypy variance complaint.
    t_fusion = time.perf_counter()
    channel_results: dict[str, list[Hashable]] = {
        "dense": [h.chunk_id for h in dense_hits],
        "sparse": [h.chunk_id for h in sparse_hits],
        "bm25": [h.chunk_id for h in bm25_hits],
    }
    fused = reciprocal_rank_fusion(channel_results, k=rrf_k, limit=top_k)
    fusion_s = time.perf_counter() - t_fusion

    # Stage 4: enrich with Postgres metadata + text. One JOIN, batched
    # by chunk.id IN (…). Order is reapplied client-side because IN
    # does not preserve list order.
    t_enrich = time.perf_counter()
    if not fused:
        total_s = time.perf_counter() - t_start
        return [], HybridSearchTimings(encode_s, channels_s, fusion_s, 0.0, total_s)
    hits = await _enrich(db_session, fused)
    enrich_s = time.perf_counter() - t_enrich
    total_s = time.perf_counter() - t_start

    logger.info(
        "hybrid_search query=%r dense=%d sparse=%d bm25=%d fused=%d total=%.3fs",
        query,
        len(dense_hits),
        len(sparse_hits),
        len(bm25_hits),
        len(hits),
        total_s,
    )
    return hits, HybridSearchTimings(encode_s, channels_s, fusion_s, enrich_s, total_s)


async def _enrich(
    session: AsyncSession,
    fused: list[FusedHit],
) -> list[HybridHit]:
    """Replace ``FusedHit[UUID]`` with text-bearing :class:`HybridHit`.

    A single round-trip pulls every needed field; we sort the rows
    back into RRF order client-side because SQL ``IN (…)`` does not
    promise order.
    """
    chunk_ids = [h.doc_id for h in fused]
    stmt = (
        sa.select(
            Chunk.id,
            Chunk.text,
            Chunk.parent_chunk_id,
            Chunk.segment_id,
            Chunk.is_parent,
            Work.canonical_id.label("work_canonical_id"),
        )
        .select_from(Chunk)
        .join(Instance, Instance.id == Chunk.instance_id)
        .join(Expression, Expression.id == Instance.expression_id)
        .join(Work, Work.id == Expression.work_id)
        .where(Chunk.id.in_(chunk_ids))
    )
    rows = (await session.execute(stmt)).all()
    by_id = {row.id: row for row in rows}

    hits: list[HybridHit] = []
    for f in fused:
        row = by_id.get(f.doc_id)
        if row is None:
            # Qdrant has a chunk that Postgres does not. Skip and log —
            # this is a corpus-consistency bug, but failing the whole
            # query because of one stale Qdrant point is worse than
            # silently dropping it.
            logger.warning(
                "Hybrid hit %s has no Postgres row — Qdrant ahead of DB?",
                f.doc_id,
            )
            continue
        hits.append(
            HybridHit(
                chunk_id=row.id,
                work_canonical_id=row.work_canonical_id,
                segment_id=row.segment_id,
                parent_chunk_id=row.parent_chunk_id,
                is_parent=row.is_parent,
                text=row.text,
                rrf_score=f.score,
                per_channel_rank=f.per_channel_rank,
            )
        )
    return hits


# Re-exported for the API layer's convenience (it can stay un-aware of
# the rrf module's existence).
__all__ = [
    "DEFAULT_PER_CHANNEL_LIMIT",
    "DEFAULT_TOP_K",
    "ChannelHit",
    "EncoderProtocol",
    "HybridHit",
    "HybridSearchTimings",
    "QdrantQueryProtocol",
    "hybrid_search",
]
