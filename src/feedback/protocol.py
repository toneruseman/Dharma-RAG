"""Abstract contract for the feedback service.

Mirrors :mod:`src.rag.protocol` and :mod:`src.answer.protocol` — same
stub/real seam pattern. The protocol decouples ``POST /api/feedback``
from any specific storage so a fresh clone can run the endpoint
without Postgres (stub mode = in-memory list) and production hits the
``app.feedback`` table.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.feedback.schemas import FeedbackRequest, FeedbackResponse


@runtime_checkable
class FeedbackServiceProtocol(Protocol):
    """Anything that can store a :class:`FeedbackRequest` durably enough."""

    async def submit(self, request: FeedbackRequest) -> FeedbackResponse: ...


__all__ = ["FeedbackServiceProtocol"]
