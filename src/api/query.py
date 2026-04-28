"""POST /api/query — stable production retrieval endpoint.

Sibling of :mod:`src.api.retrieve` but with a frozen contract: only
*semantic* parameters are accepted and only the public source shape
is returned. Use this from the LLM service, frontend, and
Telegram bot. Use ``/api/retrieve`` from eval scripts and the smoke
tools where the diagnostic surface matters.

Resources (BGE-M3 encoder, Qdrant client, reranker, DB session-maker)
are shared with the retrieval router via
:func:`src.api.retrieve.get_resources` — no second copy of the 2.3 GB
encoder weights. Must be installed *after* the retrieval router so
the singleton is already populated.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, FastAPI, HTTPException

from src.api.retrieve import get_resources
from src.config import get_settings
from src.rag.schemas import QueryRequest, QueryResponse
from src.rag.service import RAGService

logger = logging.getLogger(__name__)


# Module-level singleton populated by :func:`install_router`. Same
# pattern as :mod:`src.api.retrieve` — keeps the dependency function
# trivial without pulling Request through every signature.
_service: RAGService | None = None


router = APIRouter(prefix="/api", tags=["query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Stable production retrieval — top-k source passages",
)
async def query(body: QueryRequest) -> QueryResponse:
    if _service is None:
        raise HTTPException(status_code=503, detail="RAG service initialising.")
    return await _service.query(body)


def install_router(app: FastAPI) -> None:
    """Attach the query router to ``app``.

    Must run *after* :func:`src.api.retrieve.install_router` because
    we reuse its shared resources.
    """
    global _service
    if _service is None:
        resources = get_resources()
        _service = RAGService(
            encoder=resources.encoder,
            qdrant_client=resources.qdrant,
            reranker=resources.reranker,
            session_maker=resources.session_maker,
            settings=get_settings(),
        )
    app.include_router(router)


def shutdown_service() -> None:
    """Tear down the service handle. Underlying resources are released
    by :func:`src.api.retrieve.shutdown_resources` (single ownership)."""
    global _service
    _service = None
