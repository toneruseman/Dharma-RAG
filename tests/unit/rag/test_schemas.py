"""Schema-level unit tests for the public ``/api/query`` contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.rag.schemas import PipelineMetadata, QueryRequest, QueryResponse, Source


class TestQueryRequest:
    def test_minimal_valid(self) -> None:
        req = QueryRequest(query="what is dukkha?")
        assert req.query == "what is dukkha?"
        assert req.top_k == 5
        assert req.language is None
        assert req.forbidden_works is None

    def test_top_k_bounds(self) -> None:
        with pytest.raises(ValidationError):
            QueryRequest(query="x", top_k=0)
        with pytest.raises(ValidationError):
            QueryRequest(query="x", top_k=21)

    def test_query_length_bounds(self) -> None:
        with pytest.raises(ValidationError):
            QueryRequest(query="")
        with pytest.raises(ValidationError):
            QueryRequest(query="x" * 2001)

    def test_forbidden_works_optional(self) -> None:
        req = QueryRequest(query="x", forbidden_works=["mn10", "sn22.59"])
        assert req.forbidden_works == ["mn10", "sn22.59"]

    def test_expand_pali_default_none(self) -> None:
        # ``None`` is intentional — defers to server-side default.
        # ``False`` would force-disable on every request, removing the
        # operator's ability to flip the default by env var.
        req = QueryRequest(query="x")
        assert req.expand_pali is None

    def test_expand_pali_explicit_override(self) -> None:
        req = QueryRequest(query="x", expand_pali=True)
        assert req.expand_pali is True
        req2 = QueryRequest(query="x", expand_pali=False)
        assert req2.expand_pali is False


class TestSource:
    def test_score_clamped_to_unit_interval(self) -> None:
        with pytest.raises(ValidationError):
            Source(
                work_canonical_id="mn10",
                segment_id=None,
                text="t",
                snippet="t",
                score=1.5,
            )
        with pytest.raises(ValidationError):
            Source(
                work_canonical_id="mn10",
                segment_id=None,
                text="t",
                snippet="t",
                score=-0.1,
            )


class TestPipelineMetadata:
    def test_required_fields(self) -> None:
        meta = PipelineMetadata(
            version="dharma_v2-rerank0-parents1-pali0",
            collection="dharma_v2",
            rerank=False,
            expand_parents=True,
            expand_pali=False,
            n_candidates=8,
        )
        assert meta.version == "dharma_v2-rerank0-parents1-pali0"
        assert meta.n_candidates == 8
        assert meta.expand_pali is False


class TestQueryResponse:
    def test_round_trip_serialisation(self) -> None:
        resp = QueryResponse(
            query="x",
            sources=[
                Source(
                    work_canonical_id="mn10",
                    segment_id="mn10:1.1",
                    text="full passage",
                    snippet="matched fragment",
                    score=0.87,
                )
            ],
            latency_ms=42.0,
            metadata=PipelineMetadata(
                version="dharma_v2-rerank0-parents1-pali0",
                collection="dharma_v2",
                rerank=False,
                expand_parents=True,
                expand_pali=False,
                n_candidates=1,
            ),
        )
        roundtrip = QueryResponse.model_validate(resp.model_dump())
        assert roundtrip == resp
