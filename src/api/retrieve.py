"""POST /api/retrieve — first user-facing retrieval endpoint.

Wraps :func:`src.retrieval.hybrid.hybrid_search` behind a stable JSON
contract so a developer can ``curl`` the corpus today, before the
LLM-generation layer lands in Phase 3.

Design
------
* **Singleton encoder.** BGE-M3 weights are 2.3 GB; loading them per
  request is unworkable. We instantiate one :class:`BGEM3Encoder` at
  app startup (lazy: actual model load deferred to the first
  ``encode`` call) and reuse it for every request.
* **One Qdrant client per app, not per request.** ``QdrantClient``
  manages its own connection pool — sharing it is the documented
  pattern.
* **DB session per request via dependency injection.** Each request
  gets a fresh :class:`AsyncSession` from
  :func:`src.db.session.get_session`; SQLAlchemy handles pooling
  underneath.
* **No body validation beyond a non-empty query.** The hybrid layer
  already short-circuits empty / whitespace-only queries.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings
from src.embeddings.bge_m3 import BGEM3Encoder
from src.retrieval.hybrid import (
    DEFAULT_PER_CHANNEL_LIMIT,
    DEFAULT_RERANK,
    DEFAULT_TOP_K,
    hybrid_search,
)
from src.retrieval.reranker import BGEReranker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class RetrieveRequest(BaseModel):
    """Body of POST /api/retrieve."""

    query: str = Field(..., min_length=1, max_length=2000, description="User query")
    top_k: int = Field(
        DEFAULT_TOP_K,
        ge=1,
        le=100,
        description=(
            "Final number of results to return. With rerank=True this is the "
            "reranker's output size; without rerank, it's the RRF top-N. "
            "Default 8."
        ),
    )
    per_channel_limit: int = Field(
        DEFAULT_PER_CHANNEL_LIMIT,
        ge=1,
        le=200,
        description=(
            "Top-N pulled from each individual channel (dense, sparse, BM25) "
            "before RRF fusion. With rerank=True this is also the reranker's "
            "input pool size."
        ),
    )
    rerank: bool = Field(
        DEFAULT_RERANK,
        description=(
            "Run the cross-encoder reranker over the RRF candidates. True by "
            "default. Set False for the bi-encoder-only baseline (faster, "
            "lower precision) or for A/B comparisons."
        ),
    )


class RetrieveResultItem(BaseModel):
    """One entry in the response ``results`` array."""

    chunk_id: str
    work_canonical_id: str
    segment_id: str | None
    parent_chunk_id: str | None
    is_parent: bool
    text: str
    rrf_score: float
    per_channel_rank: dict[str, int | None]
    rerank_score: float | None = Field(
        default=None,
        description="Cross-encoder score (None if rerank=false on this request).",
    )
    rrf_rank: int | None = Field(
        default=None,
        description="Position in the RRF list before reranking (None if no rerank).",
    )


class RetrieveResponse(BaseModel):
    """Body of the response. ``latency_ms`` is wall-clock end-to-end."""

    query: str
    results: list[RetrieveResultItem]
    latency_ms: float
    timings: dict[str, float] = Field(
        ..., description="Per-stage timings in seconds (encode, channels, fusion, enrich)."
    )


# ---------------------------------------------------------------------------
# Lifespan-tied resources (encoder + Qdrant client + DB engine)
# ---------------------------------------------------------------------------


class RetrievalResources:
    """Singletons created once per app, reused across requests."""

    def __init__(self) -> None:
        settings = get_settings()
        # device="auto" uses CUDA when available and falls back to CPU
        # otherwise — keeps the API runnable on CI/laptop without
        # special-casing device selection per environment.
        self.encoder = BGEM3Encoder(device="auto", use_fp16=True)
        # Lazy-loaded reranker (1.1 GB BGE-reranker-v2-m3). Weights tug
        # only on the first ``rerank()`` call, so tests and rerank=false
        # requests never pay for it.
        self.reranker = BGEReranker(device="auto", use_fp16=True)
        self.qdrant = QdrantClient(url=settings.qdrant_url)
        self.engine = create_async_engine(settings.database_url, future=True, echo=False)
        self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)

    async def close(self) -> None:
        try:
            self.qdrant.close()
        finally:
            await self.engine.dispose()


# Module-level placeholder; populated by :func:`install_router`. Holding
# the resources on the FastAPI app's ``state`` would be more idiomatic,
# but a module-level singleton keeps the dependency function below
# trivial and avoids pulling Request into every dependency signature.
_resources: RetrievalResources | None = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an async session per request."""
    if _resources is None:
        raise RuntimeError("Retrieval resources not initialised — call install_router(app).")
    async with _resources.session_maker() as session:
        yield session


# ---------------------------------------------------------------------------
# Router + endpoint
# ---------------------------------------------------------------------------


router = APIRouter(prefix="/api", tags=["retrieval"])


@router.post(
    "/retrieve",
    response_model=RetrieveResponse,
    summary="Hybrid retrieval (dense + sparse + BM25, RRF fusion)",
)
async def retrieve(
    body: RetrieveRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> RetrieveResponse:
    if _resources is None:
        # Should be unreachable in normal operation — the get_session
        # dependency already raises. Belt-and-braces for direct calls.
        raise HTTPException(status_code=503, detail="Service initialising.")

    hits, timings = await hybrid_search(
        query=body.query,
        encoder=_resources.encoder,
        qdrant_client=_resources.qdrant,
        db_session=session,
        reranker=_resources.reranker,
        top_k=body.top_k,
        per_channel_limit=body.per_channel_limit,
        rerank=body.rerank,
    )

    return RetrieveResponse(
        query=body.query,
        results=[
            RetrieveResultItem(
                chunk_id=str(h.chunk_id),
                work_canonical_id=h.work_canonical_id,
                segment_id=h.segment_id,
                parent_chunk_id=str(h.parent_chunk_id) if h.parent_chunk_id else None,
                is_parent=h.is_parent,
                text=h.text,
                rrf_score=h.rrf_score,
                per_channel_rank=h.per_channel_rank,
                rerank_score=h.rerank_score,
                rrf_rank=h.rrf_rank,
            )
            for h in hits
        ],
        latency_ms=timings.total_s * 1000.0,
        timings={
            "encode_s": timings.encode_s,
            "channels_s": timings.channels_s,
            "fusion_s": timings.fusion_s,
            "enrich_s": timings.enrich_s,
            "rerank_s": timings.rerank_s,
        },
    )


# ---------------------------------------------------------------------------
# Wiring helpers
# ---------------------------------------------------------------------------


def install_router(app: FastAPI) -> None:
    """Attach the retrieval router and resources to ``app``.

    Call from :mod:`src.api.app` after the FastAPI instance is created.
    Resources are torn down via the existing lifespan shutdown hook.
    """
    global _resources
    if _resources is None:
        _resources = RetrievalResources()
    app.include_router(router)


async def shutdown_resources() -> None:
    """Release Qdrant + DB pool. Called from app lifespan teardown."""
    global _resources
    if _resources is not None:
        await _resources.close()
        _resources = None
