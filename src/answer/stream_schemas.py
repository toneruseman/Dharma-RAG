"""SSE event payload schemas for ``POST /api/answer/stream``.

The streaming endpoint emits a sequence of typed events. Each Pydantic
model below corresponds to one SSE event name (carried in the wire-level
``event:`` line) — the JSON body of that event is the model's
``model_dump_json()``. Frontend dispatches on the SSE event name and
parses the payload into the matching typed object.

Event sequence (happy path):

  retrieval_done   ← sources retrieved (fired once, early)
  token            ← LLM delta (many events)
  citation         ← bracket [work_id] closed in the buffer (zero or
                     more, fired as soon as detected)
  done             ← full final state (fired once, terminal)

On error the sequence terminates with:

  error            ← structured failure (fired once, replaces ``done``)

Why typed Pydantic models rather than free-form dicts: the streaming
endpoint can't describe its body in OpenAPI precisely (one path → many
heterogeneous chunks), but registering these schemas lets the typegen
pipeline generate proper TypeScript types for the frontend SSE parser.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.answer.schemas import AnswerMetadata
from src.rag.schemas import Source


class RetrievalDoneEvent(BaseModel):
    """Emitted once after retrieval completes, before the LLM starts.

    Lets the frontend render the sources panel immediately — user sees
    "what we'll cite" within ~100-200 ms while the LLM is still thinking.
    """

    sources: list[Source] = Field(
        ..., description="Top-k passages that will be supplied to the LLM."
    )
    retrieval_latency_ms: float = Field(
        ..., ge=0.0, description="Wall-clock time for retrieval, in milliseconds."
    )
    pipeline_version: str = Field(
        ...,
        description=("Retrieval pipeline version string from :class:`PipelineMetadata.version`."),
    )


class TokenEvent(BaseModel):
    """One incremental LLM delta. Fires many times per stream.

    Single-field by design — token events run at high frequency and JSON
    overhead matters. Add fields here only if every consumer needs them.
    """

    delta: str = Field(..., description="Incremental text fragment from the LLM. May be empty.")


class CitationEvent(BaseModel):
    """A previously-unseen ``[work_id]`` finished closing in the answer.

    Fired once per unique work_id, in the order they first appear. The
    frontend can ignore this event if it re-parses citations from the
    accumulated buffer on each token (recommended — same logic as the
    non-streaming flow), but the event is useful for telemetry and for
    future "scroll to source" UX where the position matters.
    """

    id: str = Field(..., description="Lowercased canonical work_id (e.g. ``mn10``).")
    position: int = Field(
        ...,
        ge=0,
        description=(
            "Character offset in the accumulated answer where the bracket "
            "closed (the ``]`` character). Useful for highlighting / scroll "
            "anchors."
        ),
    )


class DoneEvent(BaseModel):
    """Terminal event for a successful stream.

    Carries the *full* final answer so the frontend can reconcile its
    own accumulated buffer (defensive against any token loss). All
    latency metadata is included for parity with the non-streaming
    ``AnswerResponse`` shape.
    """

    answer: str = Field(..., description="Full final answer text.")
    citations: list[str] = Field(
        ..., description="Final ordered, deduplicated, source-validated citation list."
    )
    latency_ms: float = Field(..., ge=0.0, description="End-to-end wall-clock time.")
    llm_latency_ms: float = Field(..., ge=0.0, description="LLM-only wall-clock time.")
    metadata: AnswerMetadata = Field(..., description="Same shape as ``AnswerResponse.metadata``.")


class ErrorEvent(BaseModel):
    """Terminal event when something went wrong during the stream.

    Replaces ``DoneEvent`` — receivers that see ``error`` should not
    expect a subsequent ``done``.
    """

    code: Literal["llm_failed", "retrieval_failed", "internal"] = Field(
        ..., description="Machine-readable failure category."
    )
    message: str = Field(..., description="Human-readable explanation for surfacing in the UI.")


__all__ = [
    "CitationEvent",
    "DoneEvent",
    "ErrorEvent",
    "RetrievalDoneEvent",
    "TokenEvent",
]
