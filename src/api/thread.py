"""POST /api/thread/next — LLM-free «infinite thread» (rag-day-36).

Stateless companion to ``/api/answer``: instead of synthesising prose
from retrieved sources via an LLM, this endpoint returns a batch of
canonical chunks with their pre-baked Contextual-Retrieval prefix
(rag-day-16). Each press of «Далее» on the frontend POSTs the
accumulated ``excluded_chunk_ids`` so the server filters them out and
returns the next round.

Design notes
------------
* No streaming — payload is small (~3 cards × ~500 tokens) and one
  retrieval round is ~200 ms total. SSE would be overkill.
* Reuses the same backend resources as ``/api/query``: the router
  shares the singleton ``RAGServiceProtocol`` constructed by
  :mod:`src.api.query` (real or stub).
* No LLM = no per-round cost (free tier of Yoniso).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, FastAPI, HTTPException

from src.config import get_settings
from src.rag.factory import get_rag_service
from src.rag.protocol import RAGServiceProtocol
from src.rag.schemas import ThreadRequest, ThreadResponse

logger = logging.getLogger(__name__)


# Same module-level singleton pattern as src.api.query / src.api.answer.
_service: RAGServiceProtocol | None = None


router = APIRouter(prefix="/api", tags=["thread"])


@router.post(
    "/thread/next",
    response_model=ThreadResponse,
    summary="LLM-free passage rotation — next batch of canonical chunks",
)
async def thread_next(body: ThreadRequest) -> ThreadResponse:
    if _service is None:
        raise HTTPException(status_code=503, detail="RAG service initialising.")
    return await _service.thread_next(body)


def install_router(app: FastAPI) -> None:
    """Attach the thread router to ``app``.

    Must run after :func:`src.api.query.install_router` in real mode so
    the shared :class:`RAGServiceProtocol` resources are already built.
    In stub mode the factory short-circuits to :class:`StubRAGService`.
    """
    global _service
    if _service is None:
        settings = get_settings()
        if settings.rag_backend == "stub":
            _service = get_rag_service(settings=settings)
        else:
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
    """Drop the service handle. Underlying resources are released by
    :func:`src.api.retrieve.shutdown_resources` (single ownership)."""
    global _service
    _service = None
