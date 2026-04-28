"""RAG service — wraps hybrid retrieval behind the ``/api/query`` contract.

Responsibilities:

* Resolve server-side defaults (``settings.retrieval_collection``,
  ``retrieval_rerank_default``, ``retrieval_expand_parents_default``)
  so callers never see them.
* Apply post-RRF filters (``forbidden_works``).
* Map :class:`HybridHit` to the public :class:`Source` shape, dropping
  internal diagnostic fields.
* Normalise the relevance score to ``[0, 1]``.
* Build the :class:`PipelineMetadata` so consumers can reason about
  which pipeline produced the answer.

Why a class rather than a free function:

* The encoder, Qdrant client, reranker, and DB session-maker are
  long-lived resources. Holding them on a service instance keeps the
  endpoint signature small and matches the layering on the retrieval
  side (resources owned by ``RetrievalResources``).
* When app-day-02 freezes ``src/rag/schemas.py`` for App-track, the
  RAGService class is the natural protocol-implementation point.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import Settings, get_settings
from src.embeddings.bge_m3 import BGEM3Encoder
from src.rag.schemas import PipelineMetadata, QueryRequest, QueryResponse, Source
from src.retrieval.hybrid import hybrid_search
from src.retrieval.reranker import BGEReranker
from src.retrieval.schemas import HybridHit

logger = logging.getLogger(__name__)


def _normalise_score(hit: HybridHit, top_rrf_score: float) -> float:
    """Map an internal hit score onto ``[0, 1]`` for the public contract.

    * Reranker scores: BGE-reranker emits raw cross-encoder logits in a
      wide unbounded range. Sigmoid is the standard mapping (matches
      what BGE-reranker scripts use for cosine-like display).
    * RRF scores: bounded above by the sum of ``1/(k+rank)`` across
      channels, but the practical maximum is query-dependent. Scaling
      by the top hit's RRF score gives a within-response 0-1 ranking
      and avoids exposing the tuning constant ``k``.

    Either way, the normalised score is a *within-response* relative
    measure, not a calibrated probability. The Source.score docstring
    spells this out for clients.
    """
    if hit.rerank_score is not None:
        return 1.0 / (1.0 + math.exp(-hit.rerank_score))
    if top_rrf_score <= 0:
        return 0.0
    return min(1.0, max(0.0, hit.rrf_score / top_rrf_score))


def _build_version_string(*, collection: str, rerank: bool, expand_parents: bool) -> str:
    """Compose the pipeline version label embedded in PipelineMetadata.

    Compact format chosen so logs and Phoenix span attributes stay
    grep-able. Example: ``dharma_v2-rerank0-parents1``.
    """
    return f"{collection}-rerank{int(rerank)}-parents{int(expand_parents)}"


def _hit_to_source(hit: HybridHit, *, score: float) -> Source:
    """Drop diagnostic fields, keep only what the public contract exposes."""
    snippet = hit.child_text if hit.child_text is not None else hit.text
    return Source(
        work_canonical_id=hit.work_canonical_id,
        segment_id=hit.segment_id,
        text=hit.text,
        snippet=snippet,
        score=score,
    )


class RAGService:
    """Production retrieval entrypoint.

    Owns no per-request state — safe to share one instance across all
    requests (the underlying resources are themselves shared).
    """

    def __init__(
        self,
        *,
        encoder: BGEM3Encoder,
        qdrant_client: QdrantClient,
        reranker: BGEReranker,
        session_maker: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
    ) -> None:
        self._encoder = encoder
        self._qdrant = qdrant_client
        self._reranker = reranker
        self._session_maker = session_maker
        self._settings = settings or get_settings()

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[AsyncSession]:
        async with self._session_maker() as session:
            yield session

    async def query(self, request: QueryRequest) -> QueryResponse:
        """Run the full RAG retrieval pipeline and return the public response."""
        start = time.perf_counter()
        settings = self._settings
        collection = settings.retrieval_collection
        rerank = settings.retrieval_rerank_default
        expand_parents = settings.retrieval_expand_parents_default

        async with self._session() as session:
            hits, _timings = await hybrid_search(
                query=request.query,
                encoder=self._encoder,
                qdrant_client=self._qdrant,
                db_session=session,
                reranker=self._reranker,
                top_k=request.top_k,
                rerank=rerank,
                collection_name=collection,
                expand_parents=expand_parents,
            )

        n_candidates = len(hits)
        if request.forbidden_works:
            forbidden = set(request.forbidden_works)
            hits = [h for h in hits if h.work_canonical_id not in forbidden]

        top_rrf_score = max((h.rrf_score for h in hits), default=0.0)
        sources = [_hit_to_source(h, score=_normalise_score(h, top_rrf_score)) for h in hits]

        latency_ms = (time.perf_counter() - start) * 1000.0
        return QueryResponse(
            query=request.query,
            sources=sources,
            latency_ms=latency_ms,
            metadata=PipelineMetadata(
                version=_build_version_string(
                    collection=collection,
                    rerank=rerank,
                    expand_parents=expand_parents,
                ),
                collection=collection,
                rerank=rerank,
                expand_parents=expand_parents,
                n_candidates=n_candidates,
            ),
        )
