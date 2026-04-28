"""Shared dataclasses for the retrieval layer.

Three channels (dense, sparse, BM25) feed RRF fusion (day 12). Keeping
the cross-cutting types in one module avoids circular imports and makes
the contract obvious to anyone reading ``hybrid.py`` for the first time.

* :class:`ChannelHit` — minimal ``(chunk_id, score)`` from any single
  channel. Channels do not need to return text or metadata: the
  orchestrator joins those in one Postgres round-trip after fusion.
* :class:`HybridHit` — fully enriched result returned by the API and
  the smoke tools. Carries the RRF score plus per-channel ranks for
  observability.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ChannelHit:
    """One ranked candidate from a single retrieval channel.

    Whatever the channel internally tracks (score, payload, debug
    counters) collapses to ``(chunk_id, score)`` at the boundary. RRF
    fusion only cares about rank order; everything else is enrichment
    done downstream.
    """

    chunk_id: UUID
    score: float


@dataclass(frozen=True, slots=True)
class HybridHit:
    """Final fused-and-enriched result returned by the API.

    ``per_channel_rank`` mirrors the FusedHit field — a dict like
    ``{"dense": 1, "sparse": 4, "bm25": None}`` shows where each channel
    placed this document. ``None`` means "did not appear in this
    channel's top-N" and is the diagnostic that motivated keeping the
    field.

    ``rerank_score`` is populated when the day-13 cross-encoder pass
    runs (``rerank=True`` in the API). When the request opts out, the
    field is ``None`` and the result order is RRF order. ``rrf_rank``
    likewise records the position in the RRF list, useful for noting
    "the reranker pulled this from rank 12 up to rank 2".

    ``text`` carries the **parent** chunk text when day-18 parent
    expansion is on (the standard "small-to-big" pattern: search on
    children, hand the parent to the LLM for context). ``child_text``
    is the precise child fragment that actually matched — the UI
    highlights this snippet inside the parent passage. ``expanded`` is
    True when a parent was substituted, False on top-level chunks that
    have no parent (rare; legacy ingest, or a parent matched directly).
    """

    chunk_id: UUID
    work_canonical_id: str
    segment_id: str | None
    parent_chunk_id: UUID | None
    is_parent: bool
    text: str
    rrf_score: float
    per_channel_rank: dict[str, int | None]
    rerank_score: float | None = None
    rrf_rank: int | None = None
    child_text: str | None = None
    expanded: bool = False
