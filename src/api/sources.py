"""GET /api/sources/{canonical_id} — Reading Room source endpoint.

Returns the full document for a canonical work ID (e.g. ``mn10``,
``sn56.11``). Drives the ``/read/[uid]`` Next.js page; deliberately
separate from ``POST /api/query`` because the intent is "show me this
sutta" rather than "rank passages for this query".

Same stub/real backend selection as :mod:`src.api.query` — controlled
by ``Settings.rag_backend``. Reuses the singleton ``RAGServiceProtocol``
already installed by :func:`src.api.query.install_router`.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, FastAPI, HTTPException, Path

from src.rag.protocol import RAGServiceProtocol
from src.rag.schemas import SourceDocument

logger = logging.getLogger(__name__)


# Module-level singleton populated by :func:`install_router`. Same
# pattern as ``src.api.query`` and ``src.api.answer``.
_service: RAGServiceProtocol | None = None


router = APIRouter(prefix="/api", tags=["sources"])


@router.get(
    "/sources/{canonical_id}",
    response_model=SourceDocument,
    summary="Full document body for the Reading Room",
    responses={404: {"description": "Work not found in the corpus."}},
)
async def get_source(
    canonical_id: str = Path(
        ...,
        min_length=1,
        max_length=64,
        description="Canonical work ID (e.g. ``mn10``, ``sn56.11``, ``dn22``).",
        examples=["mn10"],
    ),
) -> SourceDocument:
    if _service is None:
        raise HTTPException(status_code=503, detail="RAG service initialising.")
    document = await _service.get_source(canonical_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"No source with canonical_id={canonical_id!r} in the corpus.",
        )
    return document


def install_router(app: FastAPI) -> None:
    """Attach the sources router to ``app``.

    Reuses the ``RAGServiceProtocol`` already installed by
    :func:`src.api.query.install_router` — must run after it. In
    ``stub`` mode the singleton is the same :class:`StubRAGService`
    that handles ``/api/query``; in ``real`` mode it's the
    :class:`RAGService` with the live retrieval resources.
    """
    global _service
    if _service is None:
        # Local import — by the time this function runs, the query
        # router has already populated its module-level _service.
        from src.api.query import _service as rag_service  # noqa: PLC0415

        if rag_service is None:
            raise RuntimeError(
                "Sources router needs the query router installed first. "
                "Check src.api.app for install order."
            )
        _service = rag_service
    app.include_router(router)


def shutdown_service() -> None:
    """Tear down the service handle. Underlying retrieval resources
    are released by :func:`src.api.retrieve.shutdown_resources` (real
    mode) or held by :func:`src.api.query.shutdown_service` (stub)."""
    global _service
    _service = None
