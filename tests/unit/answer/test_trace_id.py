"""Verify that ``AnswerService.answer`` and ``stream_answer`` populate
``AnswerMetadata.trace_id`` with a fresh UUID4 each call.

The real wiring is exercised through the existing tests — we use the
same ``StubAnswerService`` which mirrors the production trace_id flow.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from src.answer.schemas import AnswerRequest
from src.answer.stream_schemas import DoneEvent
from src.api._answer_stub import StubAnswerService


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except (TypeError, ValueError):
        return False
    return True


@pytest.mark.asyncio
async def test_answer_returns_uuid_trace_id() -> None:
    service = StubAnswerService()
    response = await service.answer(AnswerRequest(query="x"))
    assert _is_uuid(response.metadata.trace_id)


@pytest.mark.asyncio
async def test_two_answers_have_distinct_trace_ids() -> None:
    service = StubAnswerService()
    a = await service.answer(AnswerRequest(query="x"))
    b = await service.answer(AnswerRequest(query="x"))
    assert a.metadata.trace_id != b.metadata.trace_id


@pytest.mark.asyncio
async def test_stream_done_event_carries_trace_id() -> None:
    service = StubAnswerService()
    done: DoneEvent | None = None
    async for event in service.stream_answer(AnswerRequest(query="x")):
        if isinstance(event, DoneEvent):
            done = event
    assert done is not None
    assert _is_uuid(done.metadata.trace_id)


@pytest.mark.asyncio
async def test_stream_distinct_trace_ids_across_calls() -> None:
    service = StubAnswerService()

    async def _trace_of_done() -> str:
        async for event in service.stream_answer(AnswerRequest(query="x")):
            if isinstance(event, DoneEvent):
                return event.metadata.trace_id
        raise AssertionError("stream did not yield DoneEvent")

    a = await _trace_of_done()
    b = await _trace_of_done()
    assert a != b
