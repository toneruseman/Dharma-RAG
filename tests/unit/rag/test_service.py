"""Unit tests for :mod:`src.rag.service`.

We stub :func:`src.retrieval.hybrid.hybrid_search` so the service is
exercised in isolation — no encoder, no Qdrant, no DB. The real
hybrid pipeline has its own integration suite under
``tests/integration``.
"""

from __future__ import annotations

import math
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import pytest

from src.config import Settings
from src.rag import service as service_module
from src.rag.schemas import QueryRequest
from src.rag.service import (
    RAGService,
    _build_version_string,
    _hit_to_source,
    _normalise_score,
)
from src.retrieval.hybrid import HybridSearchTimings
from src.retrieval.schemas import HybridHit


def _make_hit(
    *,
    work: str = "mn10",
    rrf_score: float = 0.5,
    rerank_score: float | None = None,
    text: str = "parent text",
    child_text: str | None = "child fragment",
    expanded: bool = True,
) -> HybridHit:
    return HybridHit(
        chunk_id=uuid4(),
        work_canonical_id=work,
        segment_id=f"{work}:1.1",
        parent_chunk_id=uuid4(),
        is_parent=False,
        text=text,
        rrf_score=rrf_score,
        per_channel_rank={"dense": 1, "sparse": 2, "bm25": None},
        rerank_score=rerank_score,
        rrf_rank=0,
        child_text=child_text,
        expanded=expanded,
    )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestBuildVersionString:
    def test_format(self) -> None:
        assert (
            _build_version_string(
                collection="dharma_v2",
                rerank=False,
                expand_parents=True,
                expand_pali=False,
            )
            == "dharma_v2-rerank0-parents1-pali0"
        )
        assert (
            _build_version_string(
                collection="dharma_v1",
                rerank=True,
                expand_parents=False,
                expand_pali=True,
            )
            == "dharma_v1-rerank1-parents0-pali1"
        )


class TestNormaliseScore:
    def test_rerank_score_uses_sigmoid(self) -> None:
        hit = _make_hit(rerank_score=0.0)
        # sigmoid(0) = 0.5
        assert _normalise_score(hit, top_rrf_score=999.0) == pytest.approx(0.5)

    def test_rerank_score_large_positive_approaches_one(self) -> None:
        hit = _make_hit(rerank_score=10.0)
        assert _normalise_score(hit, top_rrf_score=0.0) == pytest.approx(
            1.0 / (1.0 + math.exp(-10.0))
        )

    def test_rrf_score_scaled_by_top(self) -> None:
        top = _make_hit(rrf_score=1.0)
        mid = _make_hit(rrf_score=0.5)
        assert _normalise_score(top, top_rrf_score=1.0) == pytest.approx(1.0)
        assert _normalise_score(mid, top_rrf_score=1.0) == pytest.approx(0.5)

    def test_rrf_zero_top_returns_zero(self) -> None:
        hit = _make_hit(rrf_score=0.0)
        assert _normalise_score(hit, top_rrf_score=0.0) == 0.0


class TestHitToSource:
    def test_snippet_uses_child_text_when_present(self) -> None:
        hit = _make_hit(text="parent paragraph", child_text="precise fragment")
        source = _hit_to_source(hit, score=0.9)
        assert source.text == "parent paragraph"
        assert source.snippet == "precise fragment"
        assert source.score == 0.9
        assert source.work_canonical_id == "mn10"

    def test_snippet_falls_back_to_text_without_child(self) -> None:
        hit = _make_hit(text="self text", child_text=None)
        source = _hit_to_source(hit, score=0.0)
        assert source.text == "self text"
        assert source.snippet == "self text"


# ---------------------------------------------------------------------------
# RAGService.query — integration of the helpers + hybrid_search stub
# ---------------------------------------------------------------------------


@pytest.fixture
def patched_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings(
        retrieval_collection="dharma_v2",
        retrieval_rerank_default=False,
        retrieval_expand_parents_default=True,
    )
    return settings


def _make_service(
    *,
    settings: Settings,
    hybrid_stub: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> RAGService:
    """Build a RAGService whose ``query`` calls the supplied stub.

    Resources are sentinel objects — the stub never touches them.
    """
    monkeypatch.setattr(service_module, "hybrid_search", hybrid_stub)

    class _NullSessionMaker:
        @asynccontextmanager
        async def _ctx(self) -> AsyncIterator[Any]:
            yield object()

        def __call__(self) -> Any:
            return self._ctx()

    return RAGService(
        encoder=object(),  # type: ignore[arg-type]
        qdrant_client=object(),  # type: ignore[arg-type]
        reranker=object(),  # type: ignore[arg-type]
        session_maker=_NullSessionMaker(),  # type: ignore[arg-type]
        settings=settings,
    )


@pytest.mark.asyncio
async def test_query_maps_hits_and_builds_metadata(
    patched_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured_kwargs: dict[str, Any] = {}

    async def stub_hybrid(**kwargs: Any) -> tuple[list[HybridHit], HybridSearchTimings]:
        captured_kwargs.update(kwargs)
        return (
            [
                _make_hit(work="mn10", rrf_score=1.0, child_text="frag-A"),
                _make_hit(work="sn22.59", rrf_score=0.5, child_text="frag-B"),
            ],
            HybridSearchTimings(0.01, 0.02, 0.001, 0.005, 0.0, 0.04),
        )

    service = _make_service(
        settings=patched_settings, hybrid_stub=stub_hybrid, monkeypatch=monkeypatch
    )
    response = await service.query(QueryRequest(query="dukkha", top_k=5))

    assert response.query == "dukkha"
    assert len(response.sources) == 2
    assert response.sources[0].work_canonical_id == "mn10"
    assert response.sources[0].score == pytest.approx(1.0)
    assert response.sources[1].score == pytest.approx(0.5)
    assert response.metadata.collection == "dharma_v2"
    assert response.metadata.rerank is False
    assert response.metadata.expand_parents is True
    assert response.metadata.expand_pali is False  # default off, no glossary
    assert response.metadata.version == "dharma_v2-rerank0-parents1-pali0"
    assert response.metadata.n_candidates == 2
    # hybrid_search received the resolved server-side defaults, not None.
    assert captured_kwargs["collection_name"] == "dharma_v2"
    assert captured_kwargs["rerank"] is False
    assert captured_kwargs["expand_parents"] is True
    assert captured_kwargs["top_k"] == 5
    assert response.latency_ms >= 0.0


@pytest.mark.asyncio
async def test_query_filters_forbidden_works(
    patched_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def stub_hybrid(**_: Any) -> tuple[list[HybridHit], HybridSearchTimings]:
        return (
            [
                _make_hit(work="mn10", rrf_score=1.0),
                _make_hit(work="forbidden_text", rrf_score=0.8),
                _make_hit(work="sn22.59", rrf_score=0.5),
            ],
            HybridSearchTimings(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        )

    service = _make_service(
        settings=patched_settings, hybrid_stub=stub_hybrid, monkeypatch=monkeypatch
    )
    response = await service.query(QueryRequest(query="x", forbidden_works=["forbidden_text"]))

    works = [s.work_canonical_id for s in response.sources]
    assert "forbidden_text" not in works
    assert works == ["mn10", "sn22.59"]
    # n_candidates reflects the pre-filter pool — useful for debugging
    # why a query returned fewer than top_k sources.
    assert response.metadata.n_candidates == 3


@pytest.mark.asyncio
async def test_query_uses_rerank_score_when_present(
    patched_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def stub_hybrid(**_: Any) -> tuple[list[HybridHit], HybridSearchTimings]:
        return (
            [_make_hit(rerank_score=2.0, rrf_score=0.001)],
            HybridSearchTimings(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        )

    service = _make_service(
        settings=patched_settings, hybrid_stub=stub_hybrid, monkeypatch=monkeypatch
    )
    response = await service.query(QueryRequest(query="x"))
    expected = 1.0 / (1.0 + math.exp(-2.0))
    assert response.sources[0].score == pytest.approx(expected)


@pytest.mark.asyncio
async def test_query_empty_results(
    patched_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def stub_hybrid(**_: Any) -> tuple[list[HybridHit], HybridSearchTimings]:
        return ([], HybridSearchTimings(0.0, 0.0, 0.0, 0.0, 0.0, 0.0))

    service = _make_service(
        settings=patched_settings, hybrid_stub=stub_hybrid, monkeypatch=monkeypatch
    )
    response = await service.query(QueryRequest(query="nothing matches"))
    assert response.sources == []
    assert response.metadata.n_candidates == 0
