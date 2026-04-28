"""Stable contract for the LLM answer service.

``POST /api/answer`` is the layer above ``POST /api/query`` — it takes
the same retrieval pool and asks an LLM to synthesise a single
grounded answer with inline citations. The contract intentionally
mirrors :mod:`src.rag.schemas` so the response shape stays
predictable for clients that already parse ``QueryResponse``.

Why a separate module rather than extending rag.schemas
-------------------------------------------------------
``/api/query`` is the **retrieval** contract — it must stay stable
for clients that only need sources (eval scripts, debug tools, future
admin UI). ``/api/answer`` is the **end-user** contract that may
evolve faster (streaming, conversation history, model selection).
Putting them in distinct modules signals that the two have separate
backwards-compatibility lifecycles.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from src.rag.schemas import PipelineMetadata, Source

AnswerStyle = Literal["auto", "concise", "detailed"]
"""Length/depth preference for the LLM answer.

* ``auto`` (default) — model picks length to match question complexity:
  a single-fact question gets 1-2 sentences, a fundamental "what is X?"
  question gets a structured multi-paragraph explanation. No artificial
  compression, no padding.
* ``concise`` — explicit short mode: 2-4 sentences with citations only.
  Useful for chat-style Q&A or when token budget matters.
* ``detailed`` — explicit thorough mode: multi-paragraph or numbered
  structure, every claim cited. Useful for "explain to me" / learning
  use cases or when sources are rich and the user wants depth."""


class AnswerRequest(BaseModel):
    """Body of POST /api/answer."""

    query: str = Field(..., min_length=1, max_length=2000, description="User question")
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description=(
            "Number of source passages to retrieve and feed to the LLM. "
            "Tighter cap than /api/query (which allows 20) because each "
            "extra passage costs ~500-1500 input tokens — 5 parents fit "
            "comfortably in any context window without inflating the "
            "per-request bill."
        ),
    )
    expand_pali: bool | None = Field(
        default=None,
        description=(
            "Forwarded to the underlying retrieval call. ``None`` defers "
            "to the server-side ``glossary_expand_pali_default``. "
            "``True``/``False`` overrides per request — useful for "
            "side-by-side debugging on the same question."
        ),
    )
    forbidden_works: list[str] | None = Field(
        default=None,
        description=(
            "Forwarded to retrieval. Drops sources whose "
            "``work_canonical_id`` appears in this list before they "
            "reach the LLM."
        ),
    )
    model: str | None = Field(
        default=None,
        description=(
            "Optional override of the OpenRouter model id "
            "(e.g. ``anthropic/claude-haiku-4.5``). ``None`` uses the "
            "server-side ``answer_llm_model`` setting. Useful for A/B "
            "comparing models without restarting the service."
        ),
    )
    style: AnswerStyle | None = Field(
        default=None,
        description=(
            "Length/depth preference. ``None`` defers to server-side "
            "``answer_default_style`` (default ``'auto'``). "
            "Override per-request when the client UI exposes a "
            "concise/detailed toggle."
        ),
    )


class AnswerMetadata(BaseModel):
    """Diagnostic metadata for an answer call."""

    pipeline_version: str = Field(
        ...,
        description=(
            "Version label of the retrieval pipeline that produced the "
            "sources, copied from :class:`PipelineMetadata.version` "
            "(e.g. ``dharma_v2-rerank0-parents1-pali1``). Lets a client "
            "correlate answer quality with the retrieval config."
        ),
    )
    llm_model: str = Field(
        ...,
        description=(
            "OpenRouter model identifier that produced the answer. "
            "Format: ``vendor/model``, e.g. "
            "``anthropic/claude-haiku-4.5``."
        ),
    )
    llm_tokens_in: int = Field(
        ..., ge=0, description="Input tokens consumed (system + sources + query)."
    )
    llm_tokens_out: int = Field(
        ..., ge=0, description="Output tokens generated (the answer text itself)."
    )
    style: AnswerStyle = Field(
        ...,
        description=(
            "Effective answer style applied to this request "
            "(``auto`` / ``concise`` / ``detailed``). Resolved from the "
            "request override, else from the server-side default."
        ),
    )
    retrieval_metadata: PipelineMetadata = Field(
        ...,
        description=(
            "Full :class:`PipelineMetadata` from the retrieval call, "
            "embedded so consumers don't need a second round-trip to "
            "/api/query for diagnostics."
        ),
    )


class AnswerResponse(BaseModel):
    """Body of the response from POST /api/answer."""

    query: str = Field(..., description="Echo of the user's question.")
    answer: str = Field(
        ...,
        description=(
            "Synthesised answer in the language of the question. "
            "Inline citations appear as ``[work_id]``, e.g. ``[mn36]`` "
            "or ``[sn56.11]``. Empty string is returned when retrieval "
            "produced no sources — consumers should display a fallback "
            "message in that case."
        ),
    )
    sources: list[Source] = Field(
        ...,
        description=(
            "The exact sources fed to the LLM, in the same order. "
            "Useful for rendering ``[work_id]`` citation chips in the "
            "UI back to the corresponding passage."
        ),
    )
    citations: list[str] = Field(
        ...,
        description=(
            "Distinct ``work_canonical_id`` strings that the LLM "
            "actually cited (subset of ``sources``). Extracted by "
            "matching ``[work_id]`` patterns in the answer text. "
            "Empty list when the LLM declined to cite (e.g. "
            "'sources do not answer the question')."
        ),
    )
    latency_ms: float = Field(..., description="End-to-end wall-clock time (retrieval + LLM).")
    retrieval_latency_ms: float = Field(..., description="Time spent in the retrieval pipeline.")
    llm_latency_ms: float = Field(
        ..., description="Time spent in the LLM call (network + generation)."
    )
    metadata: AnswerMetadata


__all__ = [
    "AnswerMetadata",
    "AnswerRequest",
    "AnswerResponse",
    "AnswerStyle",
]
