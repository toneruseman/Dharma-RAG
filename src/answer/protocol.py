"""Abstract contract for the answer service.

Mirrors :mod:`src.rag.protocol` — same stub/real seam pattern. The
protocol decouples ``POST /api/answer`` from any specific LLM
implementation so a fresh clone can run the endpoint without an
OpenRouter API key (stub mode) and production runs the real
``AnswerService``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from src.answer.schemas import AnswerRequest, AnswerResponse
from src.answer.stream_schemas import (
    CitationEvent,
    DoneEvent,
    ErrorEvent,
    RetrievalDoneEvent,
    TokenEvent,
)

# All event types the streaming endpoint can emit. Kept as a sum type
# rather than a base class so each event stays a plain Pydantic model
# (cleaner OpenAPI registration than discriminated unions in this case).
StreamEvent = RetrievalDoneEvent | TokenEvent | CitationEvent | DoneEvent | ErrorEvent


@runtime_checkable
class AnswerServiceProtocol(Protocol):
    """Anything that can answer an :class:`AnswerRequest`.

    Implementations are responsible for the retrieval + LLM lifecycle
    (RAGService dependency, OpenRouter client, model selection).
    Callers see two coroutines: ``answer`` for the buffered endpoint
    and ``stream_answer`` for the SSE endpoint.
    """

    async def answer(self, request: AnswerRequest) -> AnswerResponse: ...

    def stream_answer(self, request: AnswerRequest) -> AsyncIterator[StreamEvent]:
        """Yield events as retrieval and LLM-generation progress.

        Implementations decide event ordering — the wire contract is:
        one ``RetrievalDoneEvent`` (always first), zero or more
        ``TokenEvent`` and ``CitationEvent`` interleaved, and exactly
        one terminal event (``DoneEvent`` on success or ``ErrorEvent``
        on failure).
        """
        ...


__all__ = ["AnswerServiceProtocol", "StreamEvent"]
