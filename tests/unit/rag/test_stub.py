"""Unit tests for :mod:`src.api._rag_stub`."""

from __future__ import annotations

import pytest

from src.api._rag_stub import StubRAGService
from src.rag.protocol import RAGServiceProtocol
from src.rag.schemas import QueryRequest, QueryResponse, SourceDocument


@pytest.mark.asyncio
async def test_stub_returns_valid_response_shape() -> None:
    service = StubRAGService()
    response = await service.query(QueryRequest(query="what is dukkha?", top_k=5))
    assert isinstance(response, QueryResponse)
    assert response.query == "what is dukkha?"
    assert 0 < len(response.sources) <= 5
    assert response.metadata.collection == "stub"
    assert response.metadata.rerank is False
    assert response.metadata.expand_parents is False


@pytest.mark.asyncio
async def test_stub_clips_to_top_k() -> None:
    service = StubRAGService()
    response = await service.query(QueryRequest(query="x", top_k=2))
    assert len(response.sources) == 2


@pytest.mark.asyncio
async def test_stub_applies_forbidden_works() -> None:
    service = StubRAGService()
    # Filter out everything the fixture knows about → empty sources.
    response = await service.query(
        QueryRequest(
            query="x",
            forbidden_works=["mn10", "sn56.11", "dn22"],
        )
    )
    assert response.sources == []
    # n_candidates still reports the pre-filter pool size — useful
    # for the same debugging reasons as in the real pipeline.
    assert response.metadata.n_candidates == 3


@pytest.mark.asyncio
async def test_stub_satisfies_protocol() -> None:
    """Static check: ``StubRAGService`` must be a structural subtype
    of :class:`RAGServiceProtocol`. Catches accidental signature drift
    if the protocol is changed but the stub isn't updated."""
    service = StubRAGService()
    assert isinstance(service, RAGServiceProtocol)


@pytest.mark.asyncio
async def test_stub_latency_is_recorded() -> None:
    service = StubRAGService()
    response = await service.query(QueryRequest(query="x"))
    # Stub reports a constant ~1 ms; we just check the field is present
    # and non-negative so frontend code that uses it can rely on it.
    assert response.latency_ms >= 0


# ---------------------------------------------------------------------------
# Reading-Room (get_source) — app-day-21
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stub_get_source_returns_known_documents() -> None:
    """All three fixture works return non-empty SourceDocuments."""
    service = StubRAGService()
    for canonical_id in ("mn10", "sn56.11", "dn22"):
        document = await service.get_source(canonical_id)
        assert isinstance(document, SourceDocument)
        assert document.canonical_id == canonical_id
        assert document.title  # non-empty
        assert document.translation.license  # required by contract
        assert len(document.paragraphs) >= 1


@pytest.mark.asyncio
async def test_stub_get_source_paragraphs_are_ordered() -> None:
    """``sequence`` must be strictly increasing — frontend renders in order."""
    service = StubRAGService()
    document = await service.get_source("mn10")
    assert document is not None
    sequences = [p.sequence for p in document.paragraphs]
    assert sequences == sorted(sequences)


@pytest.mark.asyncio
async def test_stub_get_source_unknown_returns_none() -> None:
    """Anything outside the fixture set yields ``None`` so the router
    can map to a clean 404."""
    service = StubRAGService()
    assert await service.get_source("doesnotexist") is None
    assert await service.get_source("") is None


@pytest.mark.asyncio
async def test_stub_get_source_metadata_consistency() -> None:
    """Pāli title and tradition are populated for canonical Theravada works."""
    service = StubRAGService()
    document = await service.get_source("mn10")
    assert document is not None
    assert document.title_pali == "Satipaṭṭhāna Sutta"
    assert document.tradition_code == "theravada"
    assert document.is_restricted is False
    assert document.translation.author == "Bhikkhu Sujato"
    assert document.translation.language_code == "eng"
