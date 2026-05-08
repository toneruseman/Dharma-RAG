"""ORM models for the ``app`` Postgres schema.

The ``app`` schema holds runtime application data (feedback, in the
future audit_log, sessions, rate limit buckets) and is kept separate
from ``public`` where the corpus FRBR tables live. Keeping app and
corpus tables in distinct schemas means database review scripts, dump
exports, and DDL migrations can target one without dragging the other
along.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PgUUID  # noqa: N811 — SQLAlchemy class
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Feedback(Base):
    """One 👍/👎 vote on a single answer.

    Keyed by ``trace_id`` so a re-vote upserts in place. Snapshot columns
    (``query_text``, ``answer_text``, ``llm_model``, ``style`` …) are
    intentionally redundant with the logs / Phoenix spans — they let
    feedback review run through plain ``psql`` without an audit_log
    join (audit_log lands in app-day-49).
    """

    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("thumb IN (-1, 1)", name="ck_feedback_thumb"),
        Index("idx_feedback_ts", text("ts DESC")),
        Index("idx_feedback_thumb_ts", "thumb", text("ts DESC")),
        Index("idx_feedback_llm_model", "llm_model"),
        {"schema": "app"},
    )

    trace_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True)

    ts: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    thumb: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)

    pipeline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(128), nullable=False)
    style: Mapped[str] = mapped_column(String(16), nullable=False)

    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    llm_tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    llm_tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)


__all__ = ["Feedback"]
