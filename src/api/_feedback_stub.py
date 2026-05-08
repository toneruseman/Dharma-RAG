"""In-memory ``StubFeedbackService`` for development without Postgres.

Used when ``RAG_BACKEND=stub`` (see ``Settings.rag_backend``). Stores
votes in a process-local dict keyed by ``trace_id`` — frontend dev
can exercise the disabled-after-submit and idempotent re-vote flows
without a database.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from src.feedback.protocol import FeedbackServiceProtocol
from src.feedback.schemas import FeedbackRequest, FeedbackResponse

logger = logging.getLogger(__name__)


class StubFeedbackService(FeedbackServiceProtocol):
    """In-memory dict[trace_id] = stored row. Wiped on process exit."""

    def __init__(self) -> None:
        self._store: dict[UUID, dict[str, object]] = {}

    async def submit(self, request: FeedbackRequest) -> FeedbackResponse:
        snapshot = request.answer_snapshot
        self._store[request.trace_id] = {
            "trace_id": request.trace_id,
            "ts": datetime.now(UTC),
            "thumb": request.thumb,
            "comment": request.comment,
            "query_text": snapshot.query_text,
            "answer_text": snapshot.answer_text,
            "pipeline_version": snapshot.pipeline_version,
            "llm_model": snapshot.llm_model,
            "style": snapshot.style,
            "latency_ms": snapshot.latency_ms,
            "llm_tokens_in": snapshot.llm_tokens_in,
            "llm_tokens_out": snapshot.llm_tokens_out,
        }
        logger.info(
            "feedback.submit.stub",
            extra={
                "trace_id": str(request.trace_id),
                "thumb": request.thumb,
                "has_comment": request.comment is not None,
            },
        )
        return FeedbackResponse(saved=True)

    @property
    def store(self) -> dict[UUID, dict[str, object]]:
        """Test-only view into the in-memory store."""
        return self._store


__all__ = ["StubFeedbackService"]
