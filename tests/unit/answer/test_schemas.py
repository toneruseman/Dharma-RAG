"""Schema-level unit tests for the public ``/api/answer`` contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.answer.schemas import AnswerMetadata, AnswerRequest, AnswerResponse
from src.rag.schemas import PipelineMetadata, Source


class TestAnswerRequest:
    def test_minimal_valid(self) -> None:
        req = AnswerRequest(query="what is dukkha?")
        assert req.query == "what is dukkha?"
        assert req.top_k == 5
        assert req.expand_pali is None
        assert req.forbidden_works is None
        assert req.model is None

    def test_top_k_bounds(self) -> None:
        with pytest.raises(ValidationError):
            AnswerRequest(query="x", top_k=0)
        with pytest.raises(ValidationError):
            AnswerRequest(query="x", top_k=11)

    def test_query_length_bounds(self) -> None:
        with pytest.raises(ValidationError):
            AnswerRequest(query="")
        with pytest.raises(ValidationError):
            AnswerRequest(query="x" * 2001)

    def test_overrides_pass_through(self) -> None:
        req = AnswerRequest(
            query="x",
            top_k=3,
            expand_pali=False,
            forbidden_works=["mn10"],
            model="anthropic/claude-3.5-haiku",
            style="detailed",
        )
        assert req.top_k == 3
        assert req.expand_pali is False
        assert req.forbidden_works == ["mn10"]
        assert req.model == "anthropic/claude-3.5-haiku"
        assert req.style == "detailed"

    def test_style_default_is_none(self) -> None:
        # ``None`` means "defer to server-side default" — distinct
        # from explicitly choosing ``"auto"``, even though the
        # observable behaviour is the same when default is ``"auto"``.
        req = AnswerRequest(query="x")
        assert req.style is None

    def test_style_invalid_value_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AnswerRequest(query="x", style="verbose")  # type: ignore[arg-type]


class TestAnswerResponse:
    def _meta(self) -> AnswerMetadata:
        return AnswerMetadata(
            pipeline_version="dharma_v2-rerank0-parents1-pali1",
            llm_model="openrouter/anthropic/claude-haiku-4.5",
            llm_tokens_in=120,
            llm_tokens_out=80,
            style="auto",
            retrieval_metadata=PipelineMetadata(
                version="dharma_v2-rerank0-parents1-pali1",
                collection="dharma_v2",
                rerank=False,
                expand_parents=True,
                expand_pali=True,
                n_candidates=5,
            ),
        )

    def test_round_trip_serialisation(self) -> None:
        resp = AnswerResponse(
            query="what is dukkha?",
            answer="The First Noble Truth declares dukkha [sn56.11].",
            sources=[
                Source(
                    work_canonical_id="sn56.11",
                    segment_id="sn56.11:5.1",
                    text="full passage",
                    snippet="matched fragment",
                    score=0.91,
                )
            ],
            citations=["sn56.11"],
            latency_ms=2150.4,
            retrieval_latency_ms=82.1,
            llm_latency_ms=2068.3,
            metadata=self._meta(),
        )
        roundtrip = AnswerResponse.model_validate(resp.model_dump())
        assert roundtrip == resp

    def test_empty_answer_allowed(self) -> None:
        # When retrieval returns nothing the service emits an empty
        # answer rather than calling the LLM. Schema must allow it.
        resp = AnswerResponse(
            query="nothing matches",
            answer="",
            sources=[],
            citations=[],
            latency_ms=80.0,
            retrieval_latency_ms=80.0,
            llm_latency_ms=0.0,
            metadata=self._meta(),
        )
        assert resp.answer == ""
        assert resp.citations == []
