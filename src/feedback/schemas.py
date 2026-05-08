"""Wire schemas for the feedback endpoint.

Shape note. ``FeedbackRequest`` carries an ``answer_snapshot`` of the
fields the row needs (query / answer text, model id, latency, tokens).
The frontend already received these in ``AnswerResponse`` / ``DoneEvent``
— echoing them back avoids a server-side in-memory cache keyed by
trace_id (MVP). Once the audit_log lands in app-day-49 the snapshot
will be looked up server-side and this field can be dropped or made
optional.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from src.answer.schemas import AnswerStyle


class AnswerSnapshot(BaseModel):
    """Fields of the rated answer that we persist alongside the vote.

    All fields are required so review through ``psql`` doesn't need a
    join — see ``docs/concepts/23-feedback-widget.md`` section "Схема
    таблицы". Mirrors the subset of ``AnswerMetadata`` + ``query`` /
    ``answer`` text that the frontend already has after a successful
    answer.
    """

    query_text: str = Field(..., min_length=1, max_length=2000)
    answer_text: str = Field(..., max_length=20000)
    pipeline_version: str = Field(..., min_length=1, max_length=64)
    llm_model: str = Field(..., min_length=1, max_length=128)
    style: AnswerStyle
    latency_ms: int = Field(..., ge=0)
    llm_tokens_in: int = Field(..., ge=0)
    llm_tokens_out: int = Field(..., ge=0)


class FeedbackRequest(BaseModel):
    """Body of POST /api/feedback."""

    trace_id: UUID = Field(
        ...,
        description=(
            "UUID4 of the answer being rated. Comes from "
            "``AnswerMetadata.trace_id`` in the prior /api/answer or "
            "/api/answer/stream response."
        ),
    )
    thumb: Literal[1, -1] = Field(
        ...,
        description="``+1`` for 👍 (helpful), ``-1`` for 👎 (not helpful). No neutral.",
    )
    comment: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Optional free-text comment (≤2000 chars). Guards against "
            "megabyte-sized rants without restricting genuine feedback."
        ),
    )
    answer_snapshot: AnswerSnapshot = Field(
        ...,
        description=(
            "Echo of the rated answer's metadata so the row is "
            "self-contained (no audit_log join). Removed once "
            "audit_log exists (app-day-49)."
        ),
    )


class FeedbackResponse(BaseModel):
    """Body of the response from POST /api/feedback."""

    saved: bool = Field(
        ...,
        description=(
            "Always ``true`` on a 2xx — operation is idempotent (upsert). "
            "Reserved as a non-trivial field so the response stays a JSON "
            "object even after future additions (e.g. ``echo_id``)."
        ),
    )


__all__ = ["AnswerSnapshot", "FeedbackRequest", "FeedbackResponse"]
