"""Hybrid retrieval orchestrator — encode → 3 channels → RRF → enrich → rerank.

End-to-end shape (after day-13)
-------------------------------
1. Encode the query once via BGE-M3 (produces dense + sparse together).
2. Dispatch three channels concurrently:
   * dense:  ``dense_search`` against Qdrant ``bge_m3_dense``
   * sparse: ``sparse_search`` against Qdrant ``bge_m3_sparse``
   * bm25:   ``bm25.search`` against Postgres FTS
3. Fuse the three ranked lists with RRF (k=60, equal weights).
4. Truncate fused list to ``per_channel_limit`` candidates if reranker
   is enabled, else to ``top_k`` directly.
5. JOIN Postgres once for ``chunk.text`` + work / segment metadata.
6. **(NEW day 13)** Optionally rerank via BGE-reranker-v2-m3
   cross-encoder, keeping ``top_k``.
7. Return ``HybridHit`` per surviving doc, with provenance.

Why a single orchestrator instead of separate calls
---------------------------------------------------
* **Encode once.** BGE-M3 is the slowest step (~30 ms GPU). Doing it
  here and feeding both Qdrant channels keeps total latency near the
  max of the three channels rather than their sum.
* **Single Postgres round-trip for enrichment.** Qdrant returns just
  IDs; BM25 already has metadata. We unify by re-fetching everything
  from Postgres in one batched ``WHERE chunk.id IN (…)`` query.
* **Reranker after enrich.** Cross-encoder needs raw chunk text — it
  must come from Postgres anyway, so we enrich first and pass texts
  straight to the reranker. Single DB trip, no extra round.
* **Single place to add concerns.** Parent-child expansion (day 18)
  plugs in here without touching the channel modules.

Defaults locked from the design discussions
-------------------------------------------
* Equal channel weights in RRF (rank-based, not score-blending).
* No query-encoding cache (deferred to day-18 semantic cache).
* Empty results return ``[]``, not 404 — the API layer translates that.
* asyncio.gather for channel parallelism.
* Reranker on by default (``rerank=True``); disable by passing False.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from typing import Protocol

import sqlalchemy as sa
from opentelemetry import trace
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.frbr import Chunk, Expression, Instance, Work
from src.embeddings.bge_m3 import EncodedBatch
from src.retrieval import bm25, dense, sparse
from src.retrieval.reranker import CandidateForRerank, RerankedHit
from src.retrieval.rrf import DEFAULT_K, FusedHit, reciprocal_rank_fusion
from src.retrieval.schemas import ChannelHit, HybridHit

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


# Per-channel candidate pool size. Plan calls for top-30 each → RRF →
# top-30 (input to reranker) → top-8 final. The 30/8 ratio gives the
# reranker plenty of recall while keeping cross-encoder forward passes
# bounded for ~50-150 ms of GPU time.
DEFAULT_PER_CHANNEL_LIMIT: int = 30
DEFAULT_TOP_K: int = 8
DEFAULT_RERANK: bool = True


class EncoderProtocol(Protocol):
    """Subset of :class:`src.embeddings.bge_m3.BGEM3Encoder` we use."""

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


class RerankerCallable(Protocol):
    """Subset of :class:`src.retrieval.reranker.BGEReranker` we call."""

    def rerank(
        self,
        query: str,
        candidates: Sequence[CandidateForRerank],
        *,
        top_k: int,
    ) -> list[RerankedHit]: ...


@dataclass(frozen=True, slots=True)
class HybridSearchTimings:
    """Per-stage wall-clock times (seconds) for observability.

    Plan target: 8 candidates with reranker in <500 ms end-to-end.
    Without reranker, we used to land at ~70-100 ms (day 12 numbers).
    """

    encode_s: float
    channels_s: float
    fusion_s: float
    enrich_s: float
    rerank_s: float
    total_s: float


async def hybrid_search(
    *,
    query: str,
    encoder: EncoderProtocol,
    qdrant_client: QdrantQueryProtocol,
    db_session: AsyncSession,
    reranker: RerankerCallable | None = None,
    top_k: int = DEFAULT_TOP_K,
    per_channel_limit: int = DEFAULT_PER_CHANNEL_LIMIT,
    rrf_k: int = DEFAULT_K,
    rerank: bool = DEFAULT_RERANK,
) -> tuple[list[HybridHit], HybridSearchTimings]:
    """Run all stages for ``query`` and return fused/enriched/(reranked) hits.

    Parameters
    ----------
    query:
        Free-form user query. Empty strings short-circuit to ``([], 0)``.
    encoder, qdrant_client, db_session:
        Shared resources, lifecycle managed by the caller (FastAPI app
        in production, fixtures in tests).
    reranker:
        Optional :class:`src.retrieval.reranker.BGEReranker` instance.
        Required when ``rerank=True``; passing ``rerank=True`` without
        a reranker raises ``ValueError``. ``rerank=False`` works without.
    top_k:
        Final number of hits to return after the reranker (or after RRF
        if reranker disabled). Default 8.
    per_channel_limit:
        Top-N pulled from each channel before fusion. Default 30 — also
        the size of the candidate pool fed to the reranker.
    rerank:
        Toggle for the cross-encoder pass. Default True. Set False for
        A/B comparisons against the bi-encoder-only baseline (day 14
        eval).
    rrf_k:
        Flattening constant for RRF. Default 60.
    """
    if rerank and reranker is None:
        raise ValueError("rerank=True requires a reranker; pass one or set rerank=False.")

    t_start = time.perf_counter()
    if not query or not query.strip():
        return [], HybridSearchTimings(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    # ------------------------------------------------------------------
    # Stage 1 — encode (BGE-M3, dense + sparse in one forward pass)
    # ------------------------------------------------------------------
    t_encode = time.perf_counter()
    with tracer.start_as_current_span("hybrid.encode") as encode_span:
        encode_span.set_attribute("hybrid.query.len_chars", len(query))
        encoded = await asyncio.to_thread(encoder.encode, [query])
    encode_s = time.perf_counter() - t_encode

    if not encoded.dense or not encoded.sparse:
        return [], HybridSearchTimings(encode_s, 0.0, 0.0, 0.0, 0.0, encode_s)
    dense_vec = encoded.dense[0]
    sparse_weights = encoded.sparse[0]

    # ------------------------------------------------------------------
    # Stage 2 — three channels in parallel
    # ------------------------------------------------------------------
    t_channels = time.perf_counter()
    with tracer.start_as_current_span("hybrid.channels") as channels_span:
        channels_span.set_attribute("hybrid.per_channel_limit", per_channel_limit)
        dense_task = asyncio.to_thread(
            dense.dense_search, qdrant_client, dense_vec, limit=per_channel_limit
        )
        sparse_task = asyncio.to_thread(
            sparse.sparse_search, qdrant_client, sparse_weights, limit=per_channel_limit
        )
        bm25_task = bm25.search(db_session, query, limit=per_channel_limit)
        dense_hits, sparse_hits, bm25_hits = await asyncio.gather(
            dense_task, sparse_task, bm25_task
        )
        channels_span.set_attribute("hybrid.dense.hits", len(dense_hits))
        channels_span.set_attribute("hybrid.sparse.hits", len(sparse_hits))
        channels_span.set_attribute("hybrid.bm25.hits", len(bm25_hits))
    channels_s = time.perf_counter() - t_channels

    # ------------------------------------------------------------------
    # Stage 3 — RRF fusion. Limit decision: if reranker will run, give
    # it a wide pool (per_channel_limit). If not, the API contract is
    # "return top_k", so truncate now.
    # ------------------------------------------------------------------
    t_fusion = time.perf_counter()
    rrf_limit = per_channel_limit if rerank else top_k
    with tracer.start_as_current_span("hybrid.rrf") as rrf_span:
        rrf_span.set_attribute("hybrid.rrf.k", rrf_k)
        rrf_span.set_attribute("hybrid.rrf.limit", rrf_limit)
        channel_results: dict[str, list[Hashable]] = {
            "dense": [h.chunk_id for h in dense_hits],
            "sparse": [h.chunk_id for h in sparse_hits],
            "bm25": [h.chunk_id for h in bm25_hits],
        }
        fused = reciprocal_rank_fusion(channel_results, k=rrf_k, limit=rrf_limit)
        rrf_span.set_attribute("hybrid.rrf.fused", len(fused))
    fusion_s = time.perf_counter() - t_fusion

    if not fused:
        total_s = time.perf_counter() - t_start
        return [], HybridSearchTimings(encode_s, channels_s, fusion_s, 0.0, 0.0, total_s)

    # ------------------------------------------------------------------
    # Stage 4 — Postgres enrichment. One JOIN for all candidates.
    # ------------------------------------------------------------------
    t_enrich = time.perf_counter()
    with tracer.start_as_current_span("hybrid.enrich") as enrich_span:
        enrich_span.set_attribute("hybrid.enrich.candidates", len(fused))
        enriched = await _enrich(db_session, fused)
    enrich_s = time.perf_counter() - t_enrich

    # ------------------------------------------------------------------
    # Stage 5 — Reranker. Optional. Reorders ``enriched`` by a
    # cross-encoder pass and truncates to ``top_k``.
    # ------------------------------------------------------------------
    rerank_s = 0.0
    if rerank and enriched:
        assert reranker is not None  # narrowed by the upfront check
        t_rerank = time.perf_counter()
        with tracer.start_as_current_span("hybrid.rerank") as rerank_span:
            rerank_span.set_attribute("hybrid.rerank.candidates", len(enriched))
            rerank_span.set_attribute("hybrid.rerank.top_k", top_k)
            candidates = [
                CandidateForRerank(chunk_id=h.chunk_id, text=h.text, rrf_rank=idx)
                for idx, h in enumerate(enriched)
            ]
            reranked = await asyncio.to_thread(reranker.rerank, query, candidates, top_k=top_k)
        rerank_s = time.perf_counter() - t_rerank

        # Map back: pull the enriched HybridHits matching the reranker's
        # chosen IDs in the reranker's order, attaching scores + ranks.
        by_id = {h.chunk_id: h for h in enriched}
        out: list[HybridHit] = []
        for rh in reranked:
            base = by_id.get(rh.chunk_id)
            if base is None:
                logger.warning(
                    "Reranker returned chunk %s not in enriched set — " "shouldn't happen.",
                    rh.chunk_id,
                )
                continue
            out.append(
                HybridHit(
                    chunk_id=base.chunk_id,
                    work_canonical_id=base.work_canonical_id,
                    segment_id=base.segment_id,
                    parent_chunk_id=base.parent_chunk_id,
                    is_parent=base.is_parent,
                    text=base.text,
                    rrf_score=base.rrf_score,
                    per_channel_rank=base.per_channel_rank,
                    rerank_score=rh.score,
                    rrf_rank=rh.rrf_rank,
                )
            )
        hits = out
    else:
        hits = enriched[:top_k]

    total_s = time.perf_counter() - t_start
    logger.info(
        "hybrid_search query=%r dense=%d sparse=%d bm25=%d fused=%d rerank=%s "
        "out=%d total=%.3fs",
        query,
        len(dense_hits),
        len(sparse_hits),
        len(bm25_hits),
        len(fused),
        rerank,
        len(hits),
        total_s,
    )
    return (
        hits,
        HybridSearchTimings(
            encode_s=encode_s,
            channels_s=channels_s,
            fusion_s=fusion_s,
            enrich_s=enrich_s,
            rerank_s=rerank_s,
            total_s=total_s,
        ),
    )


async def _enrich(
    session: AsyncSession,
    fused: list[FusedHit],
) -> list[HybridHit]:
    """Replace ``FusedHit`` with text-bearing :class:`HybridHit`.

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
                rerank_score=None,
                rrf_rank=None,
            )
        )
    return hits


__all__ = [
    "DEFAULT_PER_CHANNEL_LIMIT",
    "DEFAULT_RERANK",
    "DEFAULT_TOP_K",
    "ChannelHit",
    "EncoderProtocol",
    "HybridHit",
    "HybridSearchTimings",
    "QdrantQueryProtocol",
    "RerankerCallable",
    "hybrid_search",
]
