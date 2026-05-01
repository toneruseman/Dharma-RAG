"""In-memory ``StubAnswerService`` for development without an OpenRouter key.

Used when ``RAG_BACKEND=stub`` (see ``Settings.rag_backend``). Wraps
the existing :class:`StubRAGService` and returns a deterministic
fixed answer that **looks** like an LLM response — frontend code that
consumes ``AnswerResponse`` exercises the same parsing path as
production.

Why a separate stub at the answer layer
---------------------------------------
The retrieval stub already returns fixture sources, but a frontend
needs to display the *answer*, not just the sources. A separate
stub here means a fresh clone can run ``pnpm dev`` end-to-end
without touching OpenRouter at all.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator

from src.answer.protocol import AnswerServiceProtocol
from src.answer.schemas import AnswerMetadata, AnswerRequest, AnswerResponse
from src.answer.service import IncrementalCitationScanner
from src.answer.stream_schemas import (
    CitationEvent,
    DoneEvent,
    ErrorEvent,
    RetrievalDoneEvent,
    TokenEvent,
)
from src.api._rag_stub import StubRAGService
from src.rag.schemas import QueryRequest

# Deterministic stub answer with bracket-citations matching the
# fixture work_canonical_ids from StubRAGService. Mentions all three
# fixture works so the citations array in the response is non-empty.
_STUB_ANSWER: str = (
    "[Stub answer — RAG_BACKEND=stub.] Mindfulness of the body is "
    "central to liberation, taught in the Satipaṭṭhāna Sutta [mn10] "
    "and its longer parallel [dn22]. The First Noble Truth declares "
    "all five aggregates as dukkha [sn56.11]. This response is "
    "fixture data — set RAG_BACKEND=real for genuine LLM output."
)


class StubAnswerService(AnswerServiceProtocol):
    """In-memory implementation: same shape, hardcoded payload, ~2 ms."""

    def __init__(self, *, rag_stub: StubRAGService | None = None) -> None:
        self._rag = rag_stub or StubRAGService()

    async def answer(self, request: AnswerRequest) -> AnswerResponse:
        # Reuse the retrieval stub so forbidden_works / top_k filtering
        # behaves identically to production.
        rag_response = await self._rag.query(
            QueryRequest(
                query=request.query,
                top_k=request.top_k,
                expand_pali=request.expand_pali,
                forbidden_works=request.forbidden_works,
            )
        )
        sources = list(rag_response.sources)

        # If forbidden_works wiped the fixture, return an empty answer
        # rather than citing works that aren't in the response.
        answer_text = _STUB_ANSWER if sources else ""
        # Filter the static citation list to only those still present.
        present = {s.work_canonical_id for s in sources}
        citations = [w for w in ("mn10", "sn56.11", "dn22") if w in present]

        return AnswerResponse(
            query=request.query,
            answer=answer_text,
            sources=sources,
            citations=citations,
            latency_ms=2.0,
            retrieval_latency_ms=1.0,
            llm_latency_ms=0.0,
            metadata=AnswerMetadata(
                pipeline_version="stub-v1",
                llm_model="stub/static",
                llm_tokens_in=0,
                llm_tokens_out=0,
                style=request.style or "auto",
                retrieval_metadata=rag_response.metadata,
            ),
        )

    async def stream_answer(
        self,
        request: AnswerRequest,
    ) -> AsyncIterator[RetrievalDoneEvent | TokenEvent | CitationEvent | DoneEvent | ErrorEvent]:
        """Simulate streaming so frontend dev catches real bugs.

        Chunks the fixture answer into ~30-character slices with a
        small delay between them. Total simulated latency ~1.5 s — much
        faster than real OpenRouter (5-25 s) but slow enough to
        exercise frontend race conditions (incremental rendering,
        abort-on-unmount, partial-bracket citation glitches).
        """
        wall_start = time.perf_counter()

        retrieval_start = time.perf_counter()
        rag_response = await self._rag.query(
            QueryRequest(
                query=request.query,
                top_k=request.top_k,
                expand_pali=request.expand_pali,
                forbidden_works=request.forbidden_works,
            )
        )
        retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000.0
        sources = list(rag_response.sources)

        # Initial small pause so the UI gets the loading affordance.
        await asyncio.sleep(0.1)

        yield RetrievalDoneEvent(
            sources=sources,
            retrieval_latency_ms=retrieval_latency_ms,
            pipeline_version=rag_response.metadata.version,
        )

        effective_style = request.style or "auto"

        if not sources:
            total_latency_ms = (time.perf_counter() - wall_start) * 1000.0
            yield DoneEvent(
                answer="",
                citations=[],
                latency_ms=total_latency_ms,
                llm_latency_ms=0.0,
                metadata=AnswerMetadata(
                    pipeline_version="stub-v1",
                    llm_model="stub/static",
                    llm_tokens_in=0,
                    llm_tokens_out=0,
                    style=effective_style,
                    retrieval_metadata=rag_response.metadata,
                ),
            )
            return

        source_ids = {s.work_canonical_id.lower() for s in sources}
        scanner = IncrementalCitationScanner(source_ids)
        chunk_size = 30
        chunk_delay_s = 0.04
        llm_start = time.perf_counter()

        for i in range(0, len(_STUB_ANSWER), chunk_size):
            delta = _STUB_ANSWER[i : i + chunk_size]
            yield TokenEvent(delta=delta)
            for found in scanner.feed(delta):
                yield CitationEvent(id=found.id, position=found.position)
            await asyncio.sleep(chunk_delay_s)

        llm_latency_ms = (time.perf_counter() - llm_start) * 1000.0
        total_latency_ms = (time.perf_counter() - wall_start) * 1000.0

        yield DoneEvent(
            answer=scanner.text,
            citations=scanner.citations,
            latency_ms=total_latency_ms,
            llm_latency_ms=llm_latency_ms,
            metadata=AnswerMetadata(
                pipeline_version="stub-v1",
                llm_model="stub/static",
                llm_tokens_in=0,
                llm_tokens_out=0,
                style=effective_style,
                retrieval_metadata=rag_response.metadata,
            ),
        )


__all__ = ["StubAnswerService"]
