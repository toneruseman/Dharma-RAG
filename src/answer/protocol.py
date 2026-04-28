"""Abstract contract for the answer service.

Mirrors :mod:`src.rag.protocol` — same stub/real seam pattern. The
protocol decouples ``POST /api/answer`` from any specific LLM
implementation so a fresh clone can run the endpoint without an
OpenRouter API key (stub mode) and production runs the real
``AnswerService``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.answer.schemas import AnswerRequest, AnswerResponse


@runtime_checkable
class AnswerServiceProtocol(Protocol):
    """Anything that can answer an :class:`AnswerRequest`.

    Implementations are responsible for the retrieval + LLM lifecycle
    (RAGService dependency, OpenRouter client, model selection).
    Callers see a single ``answer`` coroutine.
    """

    async def answer(self, request: AnswerRequest) -> AnswerResponse: ...


__all__ = ["AnswerServiceProtocol"]
