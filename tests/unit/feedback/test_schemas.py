"""Validation tests for :mod:`src.feedback.schemas`.

Pydantic does most of the heavy lifting — we only need to confirm the
guard rails that we care about (``thumb`` is exactly ±1, comment length
cap, snapshot fields required).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.feedback.schemas import AnswerSnapshot, FeedbackRequest


def _snapshot(**overrides: object) -> AnswerSnapshot:
    base: dict[str, object] = {
        "query_text": "what is dukkha?",
        "answer_text": "dukkha is the first noble truth [sn56.11].",
        "pipeline_version": "stub-v1",
        "llm_model": "stub/static",
        "style": "auto",
        "latency_ms": 12,
        "llm_tokens_in": 0,
        "llm_tokens_out": 0,
    }
    base.update(overrides)
    return AnswerSnapshot.model_validate(base)


class TestFeedbackRequest:
    def test_thumb_plus_one_accepted(self) -> None:
        req = FeedbackRequest(
            trace_id=uuid4(),
            thumb=1,
            comment=None,
            answer_snapshot=_snapshot(),
        )
        assert req.thumb == 1

    def test_thumb_minus_one_accepted(self) -> None:
        req = FeedbackRequest(
            trace_id=uuid4(),
            thumb=-1,
            comment="too short",
            answer_snapshot=_snapshot(),
        )
        assert req.thumb == -1
        assert req.comment == "too short"

    def test_thumb_other_value_rejected(self) -> None:
        """``thumb=5`` is the canonical "what if a client sends a 1-5
        rating instead of ±1" mistake. Pydantic must reject it."""
        with pytest.raises(ValidationError):
            FeedbackRequest(
                trace_id=uuid4(),
                thumb=5,  # type: ignore[arg-type]
                comment=None,
                answer_snapshot=_snapshot(),
            )

    def test_thumb_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRequest(
                trace_id=uuid4(),
                thumb=0,  # type: ignore[arg-type]
                comment=None,
                answer_snapshot=_snapshot(),
            )

    def test_comment_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FeedbackRequest(
                trace_id=uuid4(),
                thumb=1,
                comment="x" * 2001,
                answer_snapshot=_snapshot(),
            )

    def test_snapshot_required(self) -> None:
        """A request without snapshot can't satisfy the NOT NULL columns
        in app.feedback — fail fast at the API boundary."""
        with pytest.raises(ValidationError):
            FeedbackRequest.model_validate({"trace_id": str(uuid4()), "thumb": 1, "comment": None})
