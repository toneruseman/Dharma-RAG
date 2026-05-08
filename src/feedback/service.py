"""Real ``FeedbackService`` — upserts a row into ``app.feedback``.

Composition: depends on the application sessionmaker, no other
collaborators. Stateless across calls — safe to share one instance.
"""

from __future__ import annotations

import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models.app import Feedback
from src.feedback.protocol import FeedbackServiceProtocol
from src.feedback.schemas import FeedbackRequest, FeedbackResponse

logger = logging.getLogger(__name__)


class FeedbackService(FeedbackServiceProtocol):
    """Production feedback storage backed by Postgres ``app.feedback``."""

    def __init__(self, *, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def submit(self, request: FeedbackRequest) -> FeedbackResponse:
        """Insert a new feedback row, or update if ``trace_id`` exists.

        Idempotent by design: the second POST with the same ``trace_id``
        replaces ``thumb`` / ``comment`` / snapshot fields. ``ts`` is
        also refreshed so reviewers see "last vote time" rather than
        "first vote time" — useful when iterating on the same answer.
        """
        snapshot = request.answer_snapshot
        values = {
            "trace_id": request.trace_id,
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
        stmt = pg_insert(Feedback).values(**values)
        # ON CONFLICT updates every column EXCEPT the primary key.
        # ``ts`` is intentionally refreshed to ``now()`` on each upsert
        # so the table reflects the latest vote time.
        update_cols = {
            "thumb": stmt.excluded.thumb,
            "comment": stmt.excluded.comment,
            "query_text": stmt.excluded.query_text,
            "answer_text": stmt.excluded.answer_text,
            "pipeline_version": stmt.excluded.pipeline_version,
            "llm_model": stmt.excluded.llm_model,
            "style": stmt.excluded.style,
            "latency_ms": stmt.excluded.latency_ms,
            "llm_tokens_in": stmt.excluded.llm_tokens_in,
            "llm_tokens_out": stmt.excluded.llm_tokens_out,
            "ts": stmt.excluded.ts,
        }
        stmt = stmt.on_conflict_do_update(index_elements=["trace_id"], set_=update_cols)

        async with self._sessionmaker() as session:
            await session.execute(stmt)
            await session.commit()

        return FeedbackResponse(saved=True)


__all__ = ["FeedbackService"]
