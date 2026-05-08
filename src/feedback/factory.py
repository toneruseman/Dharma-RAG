"""Factory that picks a feedback backend based on ``Settings.rag_backend``.

Mirrors :mod:`src.answer.factory` — same stub/real seam. ``stub`` mode
uses :class:`StubFeedbackService` (in-memory list, no Postgres).
``real`` mode wires the production :class:`FeedbackService` against the
shared application sessionmaker.
"""

from __future__ import annotations

import logging

from src.config import Settings, get_settings
from src.feedback.protocol import FeedbackServiceProtocol

logger = logging.getLogger(__name__)


def get_feedback_service(*, settings: Settings | None = None) -> FeedbackServiceProtocol:
    """Return a real or stub feedback service per env."""
    settings = settings or get_settings()

    if settings.rag_backend == "stub":
        from src.api._feedback_stub import StubFeedbackService

        return StubFeedbackService()

    from src.db.session import get_sessionmaker
    from src.feedback.service import FeedbackService

    return FeedbackService(sessionmaker=get_sessionmaker())


__all__ = ["get_feedback_service"]
