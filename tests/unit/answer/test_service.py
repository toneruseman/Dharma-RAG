"""Unit tests for :class:`src.answer.service.AnswerService`.

We stub both the retrieval side (``RAGServiceProtocol``) and the LLM
side (``AsyncOpenRouterLLM``) so the service is exercised in
isolation — no encoder, no Qdrant, no OpenRouter."""

from __future__ import annotations

from typing import Any

import pytest

from src.answer.llm import LLMResult
from src.answer.schemas import AnswerRequest
from src.answer.service import (
    AnswerService,
    _build_user_message,
    _extract_citations,
    build_system_prompt,
)
from src.config import Settings
from src.rag.schemas import (
    PipelineMetadata,
    QueryRequest,
    QueryResponse,
    Source,
)


def _make_source(
    *,
    work: str = "mn10",
    segment: str | None = "mn10:8.1",
    text: str = "passage text",
) -> Source:
    return Source(
        work_canonical_id=work,
        segment_id=segment,
        text=text,
        snippet=text[:30],
        score=0.9,
    )


def _make_metadata(version: str = "dharma_v2-rerank0-parents1-pali1") -> PipelineMetadata:
    return PipelineMetadata(
        version=version,
        collection="dharma_v2",
        rerank=False,
        expand_parents=True,
        expand_pali=True,
        n_candidates=2,
    )


class _StubRAG:
    """In-memory RAGServiceProtocol implementation."""

    def __init__(self, *, sources: list[Source], metadata: PipelineMetadata | None = None) -> None:
        self._sources = sources
        self._metadata = metadata or _make_metadata()
        self.last_request: QueryRequest | None = None

    async def query(self, request: QueryRequest) -> QueryResponse:
        self.last_request = request
        return QueryResponse(
            query=request.query,
            sources=list(self._sources),
            latency_ms=42.0,
            metadata=self._metadata,
        )


class _StubLLM:
    """Replacement for :class:`AsyncOpenRouterLLM` that records calls."""

    def __init__(
        self,
        *,
        text: str = "Mindfulness is taught in [mn10]. Not-self in [sn56.11].",
        tokens_in: int = 120,
        tokens_out: int = 30,
        default_model: str = "anthropic/claude-haiku-4.5",
    ) -> None:
        self._text = text
        self._tokens_in = tokens_in
        self._tokens_out = tokens_out
        self.default_model = default_model
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> LLMResult:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_message": user_message,
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        chosen = model or self.default_model
        return LLMResult(
            text=self._text,
            tokens_in=self._tokens_in,
            tokens_out=self._tokens_out,
            model=f"openrouter/{chosen}",
        )


class TestBuildUserMessage:
    def test_includes_each_source_with_id_and_segment(self) -> None:
        sources = [
            _make_source(work="mn10", segment="mn10:1.1", text="A"),
            _make_source(work="sn56.11", segment="sn56.11:5.2", text="B"),
        ]
        msg = _build_user_message("what is X?", sources)
        assert "Source 1 [mn10]" in msg
        assert "(mn10:1.1)" in msg
        assert "Source 2 [sn56.11]" in msg
        assert "(sn56.11:5.2)" in msg
        assert "User question: what is X?" in msg
        assert "A" in msg and "B" in msg

    def test_handles_missing_segment(self) -> None:
        sources = [_make_source(segment=None, text="text only")]
        msg = _build_user_message("q?", sources)
        assert "Source 1 [mn10]" in msg
        # No `()` block when segment_id is None.
        assert "[mn10] ---" in msg or "[mn10]\n" in msg

    def test_no_sources_includes_disclaimer(self) -> None:
        msg = _build_user_message("q?", [])
        assert "User question: q?" in msg
        assert "No source passages were retrieved" in msg


class TestExtractCitations:
    def test_picks_only_known_works(self) -> None:
        text = "See [mn10] and the long form [dn22]. Also [made_up_id]."
        ids = _extract_citations(text, {"mn10", "dn22"})
        assert ids == ["mn10", "dn22"]

    def test_dedup_preserves_first_appearance_order(self) -> None:
        text = "[mn10] then [sn56.11], more [mn10], then [dn22]."
        ids = _extract_citations(text, {"mn10", "sn56.11", "dn22"})
        assert ids == ["mn10", "sn56.11", "dn22"]

    def test_case_insensitive(self) -> None:
        text = "[MN10] and [Sn56.11]"
        ids = _extract_citations(text, {"mn10", "sn56.11"})
        assert "mn10" in ids
        assert "sn56.11" in ids

    def test_no_brackets_returns_empty(self) -> None:
        assert _extract_citations("plain text without citations", {"mn10"}) == []

    def test_comma_separated_multi_citation(self) -> None:
        """Real Claude output: '[mn39, dn10]' — both must be extracted.
        This is the day-24 bug spotted in production: the previous
        regex rejected the whole bracket because comma wasn't in the
        character class."""
        text = "Practice is taught [mn39, dn10] and elaborated [mn65, mn39]."
        ids = _extract_citations(text, {"mn39", "dn10", "mn65"})
        assert ids == ["mn39", "dn10", "mn65"]

    def test_comma_separated_with_unknown_filtered(self) -> None:
        """Hallucinated id inside a comma-separated bracket is
        dropped, but the valid sibling is still picked up."""
        text = "[mn39, fake99]"
        ids = _extract_citations(text, {"mn39"})
        assert ids == ["mn39"]

    def test_freeform_brackets_ignored(self) -> None:
        """Bracket-wrapped free text (stub disclaimer, footnotes)
        must not be misread as citations."""
        text = "[Stub answer — RAG_BACKEND=stub.] Foundation [mn10]."
        ids = _extract_citations(text, {"mn10"})
        assert ids == ["mn10"]

    def test_adjacent_single_brackets(self) -> None:
        """``[mn10][dn22]`` — adjacent single brackets, sometimes
        emitted by models. Both should be picked up."""
        text = "Both [mn10][dn22] discuss this."
        ids = _extract_citations(text, {"mn10", "dn22"})
        assert ids == ["mn10", "dn22"]

    def test_extra_whitespace_inside_brackets(self) -> None:
        """Loose model output with spaces — still parsed."""
        text = "[ mn10 ,  dn22 ]"
        ids = _extract_citations(text, {"mn10", "dn22"})
        assert ids == ["mn10", "dn22"]


@pytest.mark.asyncio
async def test_answer_happy_path() -> None:
    rag = _StubRAG(sources=[_make_source(work="mn10"), _make_source(work="sn56.11")])
    llm = _StubLLM(text="Mindfulness is taught in [mn10]. First Noble Truth in [sn56.11].")
    service = AnswerService(rag_service=rag, llm=llm)  # type: ignore[arg-type]

    response = await service.answer(AnswerRequest(query="what is dukkha?", top_k=3))

    assert response.query == "what is dukkha?"
    assert "[mn10]" in response.answer
    assert "[sn56.11]" in response.answer
    assert response.citations == ["mn10", "sn56.11"]
    assert len(response.sources) == 2
    assert response.metadata.llm_tokens_in == 120
    assert response.metadata.llm_tokens_out == 30
    assert response.metadata.llm_model == "openrouter/anthropic/claude-haiku-4.5"
    assert response.metadata.pipeline_version == "dharma_v2-rerank0-parents1-pali1"
    # Per-stage timings are populated and roughly consistent.
    assert response.retrieval_latency_ms >= 0
    assert response.llm_latency_ms >= 0
    assert response.latency_ms >= 0
    # Retrieval got the top_k forwarded.
    assert rag.last_request is not None
    assert rag.last_request.top_k == 3


@pytest.mark.asyncio
async def test_answer_forwards_overrides_to_retrieval() -> None:
    rag = _StubRAG(sources=[_make_source()])
    llm = _StubLLM()
    service = AnswerService(rag_service=rag, llm=llm)  # type: ignore[arg-type]

    await service.answer(
        AnswerRequest(
            query="x",
            top_k=2,
            expand_pali=False,
            forbidden_works=["foo"],
        )
    )
    assert rag.last_request is not None
    assert rag.last_request.expand_pali is False
    assert rag.last_request.forbidden_works == ["foo"]
    assert rag.last_request.top_k == 2


@pytest.mark.asyncio
async def test_answer_forwards_model_override_to_llm() -> None:
    rag = _StubRAG(sources=[_make_source()])
    llm = _StubLLM()
    service = AnswerService(rag_service=rag, llm=llm)  # type: ignore[arg-type]

    response = await service.answer(AnswerRequest(query="x", model="anthropic/claude-3.5-haiku"))
    assert llm.calls[0]["model"] == "anthropic/claude-3.5-haiku"
    assert response.metadata.llm_model == "openrouter/anthropic/claude-3.5-haiku"


@pytest.mark.asyncio
async def test_answer_skips_llm_when_no_sources() -> None:
    """If retrieval returns nothing we emit an empty answer rather
    than burning an LLM call on no context — same downstream UX as
    'I don't know' but cheaper and more honest."""
    rag = _StubRAG(sources=[])
    llm = _StubLLM()
    service = AnswerService(rag_service=rag, llm=llm)  # type: ignore[arg-type]

    response = await service.answer(AnswerRequest(query="nothing relevant"))

    assert response.answer == ""
    assert response.sources == []
    assert response.citations == []
    assert response.llm_latency_ms == 0.0
    assert response.metadata.llm_tokens_in == 0
    assert response.metadata.llm_tokens_out == 0
    # LLM was not called.
    assert llm.calls == []


@pytest.mark.asyncio
async def test_answer_uses_default_style_when_request_has_none() -> None:
    """When request.style is None, server default applies. Default
    setting is ``auto`` — confirms the prompt selection picks up the
    auto guidance string."""
    rag = _StubRAG(sources=[_make_source()])
    llm = _StubLLM()
    service = AnswerService(
        rag_service=rag,  # type: ignore[arg-type]
        llm=llm,  # type: ignore[arg-type]
        settings=Settings(answer_default_style="auto"),
    )

    response = await service.answer(AnswerRequest(query="x"))
    assert response.metadata.style == "auto"
    # System prompt the LLM saw must match the auto style.
    sent_prompt = llm.calls[0]["system_prompt"]
    assert sent_prompt == build_system_prompt("auto")


@pytest.mark.asyncio
async def test_answer_request_style_overrides_server_default() -> None:
    """Per-request style wins over the server-side setting."""
    rag = _StubRAG(sources=[_make_source()])
    llm = _StubLLM()
    service = AnswerService(
        rag_service=rag,  # type: ignore[arg-type]
        llm=llm,  # type: ignore[arg-type]
        settings=Settings(answer_default_style="auto"),
    )

    response = await service.answer(AnswerRequest(query="x", style="detailed"))
    assert response.metadata.style == "detailed"
    sent_prompt = llm.calls[0]["system_prompt"]
    assert sent_prompt == build_system_prompt("detailed")
    # Sanity: the detailed prompt actually differs from auto/concise.
    assert sent_prompt != build_system_prompt("auto")
    assert sent_prompt != build_system_prompt("concise")


@pytest.mark.asyncio
async def test_answer_server_concise_default_no_request_override() -> None:
    """Operator can flip the global default to 'concise' via env;
    requests that don't specify style should pick it up."""
    rag = _StubRAG(sources=[_make_source()])
    llm = _StubLLM()
    service = AnswerService(
        rag_service=rag,  # type: ignore[arg-type]
        llm=llm,  # type: ignore[arg-type]
        settings=Settings(answer_default_style="concise"),
    )

    response = await service.answer(AnswerRequest(query="x"))
    assert response.metadata.style == "concise"
    assert llm.calls[0]["system_prompt"] == build_system_prompt("concise")


@pytest.mark.asyncio
async def test_max_tokens_scales_with_style() -> None:
    """``concise`` answers shouldn't burn detailed-style budget;
    ``detailed`` shouldn't be truncated at the auto cap. Verified on
    the 6-model comparison run that 5/6 models hit the flat 1024
    cap when style=detailed before this fix."""
    rag = _StubRAG(sources=[_make_source()])

    expected = {"concise": 512, "auto": 1024, "detailed": 3072}
    for style, max_tok in expected.items():
        llm = _StubLLM()
        service = AnswerService(rag_service=rag, llm=llm)  # type: ignore[arg-type]
        await service.answer(AnswerRequest(query="x", style=style))  # type: ignore[arg-type]
        assert llm.calls[0]["max_tokens"] == max_tok, (
            f"style={style} expected max_tokens={max_tok}, got {llm.calls[0]['max_tokens']}"
        )


@pytest.mark.asyncio
async def test_answer_drops_hallucinated_citations() -> None:
    """If the model cites a work_id that isn't in our retrieved
    sources we leave it in the answer text but DON'T return it in
    ``citations`` — the field promises 'works actually retrieved'."""
    rag = _StubRAG(sources=[_make_source(work="mn10")])
    llm = _StubLLM(text="Real cite [mn10]. Hallucinated [an99.99].")
    service = AnswerService(rag_service=rag, llm=llm)  # type: ignore[arg-type]

    response = await service.answer(AnswerRequest(query="x"))
    assert response.citations == ["mn10"]
    assert "an99.99" not in response.citations
    # Answer text preserves what the model wrote (we don't rewrite it).
    assert "[an99.99]" in response.answer
