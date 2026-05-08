"""Abstract contract for the RAG service.

Decouples the public ``POST /api/query`` and ``GET /api/sources/{uid}``
endpoints from any specific backend. Two implementations live under
:mod:`src.rag.service` (real, day-19 + app-day-21) and
:mod:`src.api._rag_stub` (in-memory fixtures, day-02 + app-day-21).

The split lets a frontend developer run

    RAG_BACKEND=stub uvicorn src.api.app:app --reload

without spinning up Postgres, Qdrant, BGE-M3 (2.3 GB), or the
reranker (1.1 GB). The HTTP shape stays identical thanks to the
shared :mod:`src.rag.schemas` types.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.rag.schemas import (
    QueryRequest,
    QueryResponse,
    SourceDocument,
    ThreadRequest,
    ThreadResponse,
)


@runtime_checkable
class RAGServiceProtocol(Protocol):
    """Anything that can serve the RAG public surface.

    Implementations are responsible for resource lifecycle (encoder,
    DB pool, etc). Callers see three coroutines: ``query`` for the
    LLM-grounded retrieval, ``thread_next`` for the LLM-free «infinite
    thread» rotation (rag-day-36), and ``get_source`` for the Reading
    Room.
    """

    async def query(self, request: QueryRequest) -> QueryResponse: ...

    async def thread_next(self, request: ThreadRequest) -> ThreadResponse:
        """Return the next batch of canonical passages for ``request.query``.

        Stateless: the client passes back its own list of already-shown
        ``chunk_id``s in ``request.excluded_chunk_ids`` and gets fresh
        cards. Empty ``cards`` + ``exhausted=True`` signals end of the
        retrieval pool — see :class:`src.rag.schemas.ThreadResponse`.
        """
        ...

    async def get_source(self, canonical_id: str) -> SourceDocument | None:
        """Return the full document for ``canonical_id`` (e.g. ``mn10``).

        ``None`` signals "not found" so the router can map it to a
        clean 404 without raising. Anything else is a real error and
        should propagate.
        """
        ...


__all__ = ["RAGServiceProtocol"]
