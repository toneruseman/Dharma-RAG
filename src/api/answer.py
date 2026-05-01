"""POST /api/answer — LLM-grounded answer endpoint.

Layer above :mod:`src.api.query`: takes the same retrieval pool and
asks an LLM to synthesise a single answer with inline citations. Same
stub/real backend selection as :mod:`src.api.query` — controlled by
``Settings.rag_backend``.

Two endpoints share the same ``AnswerServiceProtocol``:

* ``POST /api/answer`` — buffered single response (existing).
* ``POST /api/answer/stream`` — Server-Sent Events stream (app-day-25).

The streaming endpoint emits typed events: ``retrieval_done``,
``token``, ``citation``, ``done``, ``error``. See
:mod:`src.answer.stream_schemas` for payload schemas.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, FastAPI, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.answer.factory import get_answer_service
from src.answer.protocol import AnswerServiceProtocol
from src.answer.schemas import AnswerRequest, AnswerResponse
from src.answer.stream_schemas import (
    CitationEvent,
    DoneEvent,
    ErrorEvent,
    RetrievalDoneEvent,
    TokenEvent,
)
from src.config import get_settings

logger = logging.getLogger(__name__)


# Module-level singleton populated by :func:`install_router`. Same
# pattern as ``src.api.query`` and ``src.api.retrieve`` — keeps the
# dependency function trivial.
_service: AnswerServiceProtocol | None = None


router = APIRouter(prefix="/api", tags=["answer"])


# Map Pydantic event class → SSE ``event:`` line value. Keeping the
# wire-level event name as a class attribute would couple schema to
# transport; an external table is clearer.
_EVENT_TYPE: dict[type, str] = {
    RetrievalDoneEvent: "retrieval_done",
    TokenEvent: "token",
    CitationEvent: "citation",
    DoneEvent: "done",
    ErrorEvent: "error",
}


@router.post(
    "/answer",
    response_model=AnswerResponse,
    summary="LLM-grounded answer with inline citations",
)
async def answer(body: AnswerRequest) -> AnswerResponse:
    if _service is None:
        raise HTTPException(status_code=503, detail="Answer service initialising.")
    return await _service.answer(body)


@router.post(
    "/answer/stream",
    summary="LLM-grounded answer streamed as Server-Sent Events",
    responses={
        200: {
            "description": (
                "An ``text/event-stream`` connection. Each event is one of: "
                "``retrieval_done``, ``token``, ``citation``, ``done``, "
                "``error``. See :mod:`src.answer.stream_schemas` for payloads."
            ),
            "content": {"text/event-stream": {}},
        }
    },
)
async def answer_stream(body: AnswerRequest) -> EventSourceResponse:
    if _service is None:
        raise HTTPException(status_code=503, detail="Answer service initialising.")

    service = _service

    async def event_generator() -> object:
        async for event in service.stream_answer(body):
            yield {
                "event": _EVENT_TYPE[type(event)],
                "data": event.model_dump_json(),
            }

    return EventSourceResponse(event_generator(), ping=15)


def install_router(app: FastAPI) -> None:
    """Attach the answer router to ``app``.

    In ``real`` mode this must run *after*
    :func:`src.api.query.install_router` because we reuse its
    ``RAGService``. In ``stub`` mode the answer stub builds its own
    retrieval stub internally — no ordering required.
    """
    global _service
    if _service is None:
        settings = get_settings()
        if settings.rag_backend == "stub":
            _service = get_answer_service(settings=settings)
        else:
            # Local import — keeps the answer endpoint decoupled from
            # the query module's loading order in stub mode.
            from src.api.query import _service as rag_service  # noqa: PLC0415

            if rag_service is None:
                raise RuntimeError(
                    "Answer router needs the query router installed first "
                    "(rag_backend='real'). Check src.api.app lifespan order."
                )
            _service = get_answer_service(settings=settings, rag_service=rag_service)
    app.include_router(router)


def shutdown_service() -> None:
    """Tear down the service handle. Underlying retrieval resources
    are released by :func:`src.api.retrieve.shutdown_resources`."""
    global _service
    _service = None
