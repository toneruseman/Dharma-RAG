"""Abstract contract for the RAG service.

Decouples the public ``POST /api/query`` endpoint from any specific
backend. Two implementations live under :mod:`src.rag.service` (real,
day-19) and :mod:`src.api._rag_stub` (in-memory fixtures, day-02 of
the App track).

The split lets a frontend developer run

    RAG_BACKEND=stub uvicorn src.api.app:app --reload

without spinning up Postgres, Qdrant, BGE-M3 (2.3 GB), or the
reranker (1.1 GB). The HTTP shape stays identical thanks to the
shared :mod:`src.rag.schemas` types.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.rag.schemas import QueryRequest, QueryResponse


@runtime_checkable
class RAGServiceProtocol(Protocol):
    """Anything that can answer a :class:`QueryRequest`.

    Implementations are responsible for resource lifecycle (encoder,
    DB pool, etc). Callers see a single ``query`` coroutine.
    """

    async def query(self, request: QueryRequest) -> QueryResponse: ...


__all__ = ["RAGServiceProtocol"]
