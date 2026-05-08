"""POST /api/query — stable production retrieval endpoint.

Sibling of :mod:`src.api.retrieve` but with a frozen contract: only
*semantic* parameters are accepted and only the public source shape
is returned. Use this from the LLM service, frontend, and
Telegram bot. Use ``/api/retrieve`` from eval scripts and the smoke
tools where the diagnostic surface matters.

Two backends behind the same router:

* ``real`` — :class:`src.rag.service.RAGService`, sharing the
  singleton :class:`src.api.retrieve.RetrievalResources` (encoder,
  Qdrant, reranker, DB pool). Used in production / GPU dev.
* ``stub`` — :class:`src.api._rag_stub.StubRAGService`, fixture
  data, no infrastructure. Used by frontend / CI / fresh clones.

Selection happens via ``settings.rag_backend`` and is wired through
:func:`src.rag.factory.get_rag_service`.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, FastAPI, HTTPException

from src.config import get_settings
from src.rag.factory import get_rag_service
from src.rag.protocol import RAGServiceProtocol
from src.rag.schemas import QueryRequest, QueryResponse

logger = logging.getLogger(__name__)


# Module-level singleton populated by :func:`install_router`. Same
# pattern as :mod:`src.api.retrieve` — keeps the dependency function
# trivial without pulling Request through every signature.
_service: RAGServiceProtocol | None = None


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

    In ``real`` mode this must run *after*
    :func:`src.api.retrieve.install_router` because we reuse its
    shared resources. In ``stub`` mode no resources are needed; the
    factory builds an in-memory :class:`StubRAGService`.
    """
    global _service
    if _service is None:
        settings = get_settings()
        if settings.rag_backend == "stub":
            _service = get_rag_service(settings=settings)
        else:
            # Local import — avoids loading retrieve.py (and its heavy
            # qdrant_client / encoder hooks) when running in stub mode.
            from src.api.retrieve import get_resources

            resources = get_resources()
            _service = get_rag_service(
                settings=settings,
                encoder=resources.encoder,
                qdrant_client=resources.qdrant,
                reranker=resources.reranker,
                session_maker=resources.session_maker,
            )
    app.include_router(router)


def shutdown_service() -> None:
    """Tear down the service handle. In ``real`` mode the underlying
    resources are released by
    :func:`src.api.retrieve.shutdown_resources` (single ownership);
    the stub holds no resources."""
    global _service
    _service = None
