"""Unit tests for :class:`src.api._answer_stub.StubAnswerService`."""

from __future__ import annotations

import pytest

from src.answer.protocol import AnswerServiceProtocol
from src.answer.schemas import AnswerRequest, AnswerResponse
from src.api._answer_stub import StubAnswerService


@pytest.mark.asyncio
async def test_stub_returns_valid_response_shape() -> None:
    service = StubAnswerService()
    response = await service.answer(AnswerRequest(query="what is dukkha?", top_k=5))
    assert isinstance(response, AnswerResponse)
    assert response.query == "what is dukkha?"
    assert response.answer  # non-empty stub answer
    assert 0 < len(response.sources) <= 5
    assert response.metadata.pipeline_version == "stub-v1"
    assert response.metadata.llm_model == "stub/static"
    assert response.metadata.retrieval_metadata.collection == "stub"


@pytest.mark.asyncio
async def test_stub_clips_to_top_k() -> None:
    service = StubAnswerService()
    response = await service.answer(AnswerRequest(query="x", top_k=2))
    assert len(response.sources) == 2


@pytest.mark.asyncio
async def test_stub_citations_match_returned_sources() -> None:
    """The hardcoded answer mentions [mn10], [sn56.11], [dn22]. With
    top_k=5 (or default 5) all three fixture sources are returned, so
    citations should include all three."""
    service = StubAnswerService()
    response = await service.answer(AnswerRequest(query="x", top_k=5))
    assert "mn10" in response.citations
    assert "sn56.11" in response.citations
    assert "dn22" in response.citations


@pytest.mark.asyncio
async def test_stub_filters_citations_by_forbidden_works() -> None:
    """If the user forbids one of the fixture works, that work_id
    should disappear both from sources AND from the citation list."""
    service = StubAnswerService()
    response = await service.answer(AnswerRequest(query="x", forbidden_works=["mn10"]))
    work_ids = {s.work_canonical_id for s in response.sources}
    assert "mn10" not in work_ids
    assert "mn10" not in response.citations


@pytest.mark.asyncio
async def test_stub_empty_when_all_sources_forbidden() -> None:
    """Forbidding everything yields an empty answer + empty citations,
    matching the real service's no-source behaviour."""
    service = StubAnswerService()
    response = await service.answer(
        AnswerRequest(query="x", forbidden_works=["mn10", "sn56.11", "dn22"])
    )
    assert response.sources == []
    assert response.answer == ""
    assert response.citations == []


@pytest.mark.asyncio
async def test_stub_satisfies_protocol() -> None:
    """Static check: ``StubAnswerService`` is a structural subtype
    of :class:`AnswerServiceProtocol`."""
    service = StubAnswerService()
    assert isinstance(service, AnswerServiceProtocol)
