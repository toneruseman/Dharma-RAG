"""Behavioural tests for :class:`src.api._feedback_stub.StubFeedbackService`.

The stub mirrors the production upsert semantics — exactly the
contract the frontend developer relies on while running ``RAG_BACKEND=stub``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.api._feedback_stub import StubFeedbackService
from src.feedback.schemas import AnswerSnapshot, FeedbackRequest


def _snap(**kw: object) -> AnswerSnapshot:
    base: dict[str, object] = {
        "query_text": "q",
        "answer_text": "a [mn10]",
        "pipeline_version": "stub-v1",
        "llm_model": "stub/static",
        "style": "auto",
        "latency_ms": 1,
        "llm_tokens_in": 0,
        "llm_tokens_out": 0,
    }
    base.update(kw)
    return AnswerSnapshot.model_validate(base)


@pytest.mark.asyncio
async def test_happy_path_no_comment() -> None:
    service = StubFeedbackService()
    trace_id = uuid4()
    response = await service.submit(
        FeedbackRequest(
            trace_id=trace_id,
            thumb=1,
            comment=None,
            answer_snapshot=_snap(),
        )
    )
    assert response.saved is True
    assert trace_id in service.store
    row = service.store[trace_id]
    assert row["thumb"] == 1
    assert row["comment"] is None


@pytest.mark.asyncio
async def test_happy_path_with_comment() -> None:
    service = StubFeedbackService()
    trace_id = uuid4()
    await service.submit(
        FeedbackRequest(
            trace_id=trace_id,
            thumb=-1,
            comment="too short",
            answer_snapshot=_snap(query_text="why?"),
        )
    )
    row = service.store[trace_id]
    assert row["thumb"] == -1
    assert row["comment"] == "too short"
    assert row["query_text"] == "why?"


@pytest.mark.asyncio
async def test_idempotent_upsert() -> None:
    """Two submits with the same trace_id → one row, second wins."""
    service = StubFeedbackService()
    trace_id = uuid4()
    await service.submit(
        FeedbackRequest(
            trace_id=trace_id,
            thumb=1,
            comment="initial",
            answer_snapshot=_snap(),
        )
    )
    await service.submit(
        FeedbackRequest(
            trace_id=trace_id,
            thumb=-1,
            comment="changed my mind",
            answer_snapshot=_snap(),
        )
    )
    assert len(service.store) == 1
    row = service.store[trace_id]
    assert row["thumb"] == -1
    assert row["comment"] == "changed my mind"


@pytest.mark.asyncio
async def test_distinct_trace_ids_kept_separate() -> None:
    service = StubFeedbackService()
    a, b = uuid4(), uuid4()
    await service.submit(
        FeedbackRequest(trace_id=a, thumb=1, comment=None, answer_snapshot=_snap())
    )
    await service.submit(
        FeedbackRequest(trace_id=b, thumb=-1, comment=None, answer_snapshot=_snap())
    )
    assert len(service.store) == 2
    assert service.store[a]["thumb"] == 1
    assert service.store[b]["thumb"] == -1
