"""Unit tests for streaming bits of :mod:`src.answer.service`.

Covers:
* :class:`IncrementalCitationScanner` — pure stateful helper.
* :meth:`AnswerService.stream_answer` — happy path, empty sources,
  LLM failure, partial-bracket detection.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from src.answer.llm import StreamChunk
from src.answer.schemas import AnswerRequest
from src.answer.service import (
    AnswerService,
    CitationFound,
    IncrementalCitationScanner,
)
from src.answer.stream_schemas import (
    CitationEvent,
    DoneEvent,
    ErrorEvent,
    RetrievalDoneEvent,
    TokenEvent,
)
from src.rag.schemas import (
    PipelineMetadata,
    QueryRequest,
    QueryResponse,
    Source,
)

# ---------------------------------------------------------------------------
# IncrementalCitationScanner — pure helper, no async.
# ---------------------------------------------------------------------------


def _scan_all(scanner: IncrementalCitationScanner, *deltas: str) -> list[CitationFound]:
    """Feed every delta and accumulate found citations."""
    out: list[CitationFound] = []
    for delta in deltas:
        out.extend(scanner.feed(delta))
    return out


class TestIncrementalCitationScanner:
    def test_emits_each_unique_id_once(self) -> None:
        scanner = IncrementalCitationScanner({"mn10", "sn56.11"})
        found = _scan_all(scanner, "See [mn10] and [mn10] then [sn56.11].")
        ids = [f.id for f in found]
        # Same work_id twice → emitted only once, in first-appearance order.
        assert ids == ["mn10", "sn56.11"]

    def test_partial_bracket_across_chunks(self) -> None:
        """The bracket is split: ``[mn`` arrives in chunk 1, ``10]`` in chunk 2.
        Citation must fire after chunk 2, not chunk 1."""
        scanner = IncrementalCitationScanner({"mn10"})
        first = scanner.feed("Mindfulness is taught [mn")
        assert first == []  # bracket not yet closed

        second = scanner.feed("10] in the Pāli Canon.")
        assert len(second) == 1
        assert second[0].id == "mn10"

    def test_unknown_id_skipped(self) -> None:
        """Hallucinated work_id (not in ``valid_ids``) leaves no event."""
        scanner = IncrementalCitationScanner({"mn10"})
        found = _scan_all(scanner, "[mn99] and [mn10]")
        assert [f.id for f in found] == ["mn10"]

    def test_comma_separated_multi_citation(self) -> None:
        scanner = IncrementalCitationScanner({"mn39", "dn10"})
        found = _scan_all(scanner, "Both [mn39, dn10] cover this.")
        assert [f.id for f in found] == ["mn39", "dn10"]

    def test_freeform_brackets_ignored(self) -> None:
        """``[Stub answer — RAG_BACKEND=stub.]`` looks like a citation
        wrapper but the inner text is not a valid work_id."""
        scanner = IncrementalCitationScanner({"mn10"})
        found = _scan_all(
            scanner,
            "[Stub answer — RAG_BACKEND=stub.] Then [mn10].",
        )
        assert [f.id for f in found] == ["mn10"]

    def test_buffer_and_citations_accumulate(self) -> None:
        scanner = IncrementalCitationScanner({"mn10", "dn22"})
        scanner.feed("Foundation [mn10]. ")
        scanner.feed("Longer parallel [dn22].")
        assert scanner.text == "Foundation [mn10]. Longer parallel [dn22]."
        assert scanner.citations == ["mn10", "dn22"]


# ---------------------------------------------------------------------------
# stream_answer — exercised against a stub RAG and stub streaming LLM.
# ---------------------------------------------------------------------------


def _make_source(work: str = "mn10") -> Source:
    return Source(
        work_canonical_id=work,
        segment_id=f"{work}:1.1",
        text=f"{work} passage text",
        snippet=f"{work} snippet",
        score=0.9,
    )


def _make_metadata() -> PipelineMetadata:
    return PipelineMetadata(
        version="dharma_v2-rerank0-parents1-pali1",
        collection="dharma_v2",
        rerank=False,
        expand_parents=True,
        expand_pali=True,
        n_candidates=2,
    )


class _StubRAG:
    def __init__(self, sources: list[Source], *, raise_exc: Exception | None = None) -> None:
        self._sources = sources
        self._raise = raise_exc

    async def query(self, request: QueryRequest) -> QueryResponse:
        if self._raise is not None:
            raise self._raise
        return QueryResponse(
            query=request.query,
            sources=list(self._sources),
            latency_ms=42.0,
            metadata=_make_metadata(),
        )


class _StubStreamLLM:
    """Streaming-only stub. Records calls; yields a configured chunk list."""

    def __init__(
        self,
        *,
        deltas: list[str],
        raise_at: int | None = None,
        tokens_in: int = 100,
        tokens_out: int = 30,
        default_model: str = "stub/streaming",
    ) -> None:
        self._deltas = deltas
        self._raise_at = raise_at
        self._tokens_in = tokens_in
        self._tokens_out = tokens_out
        self.default_model = default_model
        self.calls: list[dict[str, Any]] = []

    async def stream(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> AsyncIterator[StreamChunk]:
        # Async generator: yields directly so callers can ``async for``
        # the returned object without an extra await. Matches the shape
        # of :meth:`AsyncOpenRouterLLM.stream`.
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_message": user_message,
                "model": model,
                "max_tokens": max_tokens,
            }
        )
        for i, delta in enumerate(self._deltas):
            if self._raise_at is not None and i == self._raise_at:
                raise RuntimeError("upstream LLM blew up")
            yield StreamChunk(delta=delta)
        chosen = model or self.default_model
        yield StreamChunk(
            delta="",
            finish_reason="stop",
            tokens_in=self._tokens_in,
            tokens_out=self._tokens_out,
            model=f"openrouter/{chosen}",
        )


@pytest.mark.asyncio
async def test_stream_answer_happy_path() -> None:
    """Full sequence: retrieval_done → tokens → citations → done.

    DoneEvent.answer must equal concatenation of all token deltas.
    """
    rag = _StubRAG(sources=[_make_source("mn10"), _make_source("sn56.11")])
    llm = _StubStreamLLM(
        deltas=[
            "Mindfulness ",
            "is taught in [mn10]. ",
            "First Noble Truth in [sn56.11].",
        ],
    )
    service = AnswerService(rag_service=rag, llm=llm)  # type: ignore[arg-type]

    events: list[Any] = []
    async for event in service.stream_answer(AnswerRequest(query="x", top_k=2)):
        events.append(event)

    # First event always retrieval_done with the sources.
    assert isinstance(events[0], RetrievalDoneEvent)
    assert {s.work_canonical_id for s in events[0].sources} == {"mn10", "sn56.11"}

    # Last event is done — exactly one terminal event.
    assert isinstance(events[-1], DoneEvent)
    assert sum(isinstance(e, DoneEvent) for e in events) == 1
    assert sum(isinstance(e, ErrorEvent) for e in events) == 0

    # Tokens concatenate to the full answer recorded in DoneEvent.
    tokens = [e.delta for e in events if isinstance(e, TokenEvent)]
    assert "".join(tokens) == events[-1].answer
    assert "[mn10]" in events[-1].answer
    assert "[sn56.11]" in events[-1].answer

    # Citations fired in first-appearance order.
    citation_events = [e for e in events if isinstance(e, CitationEvent)]
    assert [e.id for e in citation_events] == ["mn10", "sn56.11"]
    assert events[-1].citations == ["mn10", "sn56.11"]

    # Token usage made it through to DoneEvent.metadata.
    assert events[-1].metadata.llm_tokens_in == 100
    assert events[-1].metadata.llm_tokens_out == 30


@pytest.mark.asyncio
async def test_stream_answer_empty_sources_skips_llm() -> None:
    """No retrieval hits → emit retrieval_done + done immediately,
    do not call the LLM at all (saves tokens, honest empty answer)."""
    rag = _StubRAG(sources=[])
    llm = _StubStreamLLM(deltas=["should not be used"])
    service = AnswerService(rag_service=rag, llm=llm)  # type: ignore[arg-type]

    events: list[Any] = []
    async for event in service.stream_answer(AnswerRequest(query="x", top_k=5)):
        events.append(event)

    # Two events total: retrieval_done (empty sources) + done (empty answer).
    assert len(events) == 2
    assert isinstance(events[0], RetrievalDoneEvent)
    assert events[0].sources == []
    assert isinstance(events[1], DoneEvent)
    assert events[1].answer == ""
    assert events[1].citations == []

    # LLM was not invoked.
    assert llm.calls == []


@pytest.mark.asyncio
async def test_stream_answer_llm_failure_emits_error() -> None:
    """LLM raises mid-stream → events so far + ErrorEvent, no DoneEvent.

    The generator must NOT propagate the exception — that would close
    the SSE response with a generic network error and surface as a
    confusing browser failure. Yielding a structured ErrorEvent lets
    the frontend display a clear message.
    """
    rag = _StubRAG(sources=[_make_source("mn10")])
    # Two deltas come through, then exception on the third yield (index 2).
    llm = _StubStreamLLM(deltas=["First. ", "Second. ", "third"], raise_at=2)
    service = AnswerService(rag_service=rag, llm=llm)  # type: ignore[arg-type]

    events: list[Any] = []
    async for event in service.stream_answer(AnswerRequest(query="x", top_k=1)):
        events.append(event)

    # Sequence: retrieval_done, token, token, error.
    assert isinstance(events[0], RetrievalDoneEvent)
    tokens = [e for e in events if isinstance(e, TokenEvent)]
    assert len(tokens) == 2
    assert isinstance(events[-1], ErrorEvent)
    assert events[-1].code == "llm_failed"
    assert "blew up" in events[-1].message
    # No DoneEvent on failure path.
    assert all(not isinstance(e, DoneEvent) for e in events)


@pytest.mark.asyncio
async def test_stream_answer_partial_bracket_across_chunks() -> None:
    """Bracket arriving split across deltas — citation fires after the
    second delta closes the bracket, not after the first opens it."""
    rag = _StubRAG(sources=[_make_source("mn10")])
    llm = _StubStreamLLM(
        deltas=[
            "Mindfulness is taught [mn",  # opens bracket
            "10] in the Pāli Canon.",  # closes it
        ],
    )
    service = AnswerService(rag_service=rag, llm=llm)  # type: ignore[arg-type]

    events: list[Any] = []
    async for event in service.stream_answer(AnswerRequest(query="x", top_k=1)):
        events.append(event)

    citation_events = [e for e in events if isinstance(e, CitationEvent)]
    assert len(citation_events) == 1
    assert citation_events[0].id == "mn10"

    # Citation event must come AFTER the second token event (the one
    # that closed the bracket), not after the first.
    second_token_idx = -1
    citation_idx = -1
    seen_tokens = 0
    for i, event in enumerate(events):
        if isinstance(event, TokenEvent):
            seen_tokens += 1
            if seen_tokens == 2:
                second_token_idx = i
        if isinstance(event, CitationEvent):
            citation_idx = i
    assert second_token_idx > 0
    assert citation_idx > second_token_idx
