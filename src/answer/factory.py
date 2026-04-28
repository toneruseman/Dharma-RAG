"""Factory that picks an answer backend based on ``Settings.rag_backend``.

Mirrors :mod:`src.rag.factory`. ``stub`` mode uses
:class:`StubAnswerService` (no OpenRouter calls). ``real`` mode
composes the production :class:`RAGService` with an
:class:`AsyncOpenRouterLLM` for synthesis.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.answer.protocol import AnswerServiceProtocol
from src.config import Settings, get_settings

if TYPE_CHECKING:
    from src.rag.protocol import RAGServiceProtocol

logger = logging.getLogger(__name__)


def get_answer_service(
    *,
    settings: Settings | None = None,
    rag_service: RAGServiceProtocol | None = None,
) -> AnswerServiceProtocol:
    """Return a real or stub answer service per env.

    Parameters
    ----------
    settings:
        Resolved :class:`Settings` (cached singleton if omitted).
    rag_service:
        The retrieval backend. Required in ``real`` mode (composition);
        ignored in ``stub`` mode (the stub builds its own
        :class:`StubRAGService` internally).

    Raises
    ------
    RuntimeError
        If ``rag_backend == "real"`` but ``rag_service`` is ``None`` or
        ``openrouter_api_key`` is empty.
    """
    settings = settings or get_settings()

    if settings.rag_backend == "stub":
        from src.api._answer_stub import StubAnswerService

        return StubAnswerService()

    if rag_service is None:
        raise RuntimeError(
            "rag_backend='real' requires a rag_service. Did the "
            "caller forget to install the query router first?"
        )
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "rag_backend='real' requires OPENROUTER_API_KEY. "
            "Set it in .env or switch to RAG_BACKEND=stub."
        )

    from src.answer.llm import AsyncOpenRouterLLM
    from src.answer.service import AnswerService

    llm = AsyncOpenRouterLLM(
        api_key=settings.openrouter_api_key,
        default_model=settings.answer_llm_model,
        base_url=settings.openrouter_base_url,
    )
    return AnswerService(rag_service=rag_service, llm=llm)


__all__ = ["get_answer_service"]
