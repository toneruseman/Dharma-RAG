"""POST /api/feedback — 👍/👎 vote endpoint.

Stub/real selection mirrors :mod:`src.api.answer` and :mod:`src.api.query`.
Idempotent by design: repeat POSTs with the same ``trace_id`` upsert the
row (see :mod:`src.feedback.service`).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, FastAPI, HTTPException

from src.feedback.factory import get_feedback_service
from src.feedback.protocol import FeedbackServiceProtocol
from src.feedback.schemas import FeedbackRequest, FeedbackResponse

logger = logging.getLogger(__name__)


# Module-level singleton populated by :func:`install_router`. Same
# pattern as ``src.api.query`` / ``src.api.answer``.
_service: FeedbackServiceProtocol | None = None


router = APIRouter(prefix="/api", tags=["feedback"])


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="Record a 👍/👎 vote on a previous answer",
)
async def submit_feedback(body: FeedbackRequest) -> FeedbackResponse:
    if _service is None:
        raise HTTPException(status_code=503, detail="Feedback service initialising.")
    return await _service.submit(body)


def install_router(app: FastAPI) -> None:
    """Attach the feedback router to ``app``.

    Independent of the query/answer routers — the feedback service has
    no shared resources. Safe to install in any order.
    """
    global _service
    if _service is None:
        _service = get_feedback_service()
    app.include_router(router)


def shutdown_service() -> None:
    """Tear down the service handle. The Postgres pool used in real mode
    is released by SQLAlchemy when the process exits."""
    global _service
    _service = None
