"""Factory that picks a RAG backend based on ``Settings.rag_backend``.

Dispatch lives here (not in :mod:`src.api.app`) so the FastAPI wiring
stays small: app code calls one function, gets a
:class:`RAGServiceProtocol`, and doesn't import either implementation
directly. Replacing the stub with a different fake (e.g. one that
reads from a YAML fixture) becomes a one-line change in this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.config import Settings, get_settings
from src.rag.protocol import RAGServiceProtocol

if TYPE_CHECKING:
    # qdrant_client is imported lazily below to avoid pulling its weight
    # into the stub-only path.
    from qdrant_client import QdrantClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.embeddings.bge_m3 import BGEM3Encoder
    from src.retrieval.reranker import BGEReranker


def get_rag_service(
    *,
    settings: Settings | None = None,
    encoder: BGEM3Encoder | None = None,
    qdrant_client: QdrantClient | None = None,
    reranker: BGEReranker | None = None,
    session_maker: async_sessionmaker[AsyncSession] | None = None,
) -> RAGServiceProtocol:
    """Return a real or stub :class:`RAGServiceProtocol` per env.

    Parameters
    ----------
    settings:
        Resolved :class:`Settings` (cached singleton if omitted).
    encoder, qdrant_client, reranker, session_maker:
        Heavy resources. Required when ``settings.rag_backend == "real"``;
        ignored in stub mode. Passed in by the caller (the FastAPI app's
        :class:`RetrievalResources`) so this module stays import-light
        and free of global mutable state.

    Raises
    ------
    RuntimeError
        If ``rag_backend == "real"`` but any of the required resources
        is missing — clearer than letting ``RAGService`` blow up later
        with an opaque ``NoneType`` error.
    """
    settings = settings or get_settings()

    if settings.rag_backend == "stub":
        # Local import keeps the stub module out of the real-backend
        # process unless it's actually selected.
        from src.api._rag_stub import StubRAGService

        return StubRAGService()

    # Real backend.
    missing = [
        name
        for name, val in {
            "encoder": encoder,
            "qdrant_client": qdrant_client,
            "reranker": reranker,
            "session_maker": session_maker,
        }.items()
        if val is None
    ]
    if missing:
        raise RuntimeError(
            f"rag_backend='real' requires resources, but missing: {missing}. "
            "Did the caller forget to install the retrieval router first?"
        )

    from src.rag.service import RAGService

    # Narrowed by the ``missing`` check above — none are None here.
    assert encoder is not None
    assert qdrant_client is not None
    assert reranker is not None
    assert session_maker is not None
    return RAGService(
        encoder=encoder,
        qdrant_client=qdrant_client,
        reranker=reranker,
        session_maker=session_maker,
        settings=settings,
    )


__all__ = ["get_rag_service"]
