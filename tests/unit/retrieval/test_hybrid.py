"""Unit tests for the hybrid retrieval orchestrator.

We mock the encoder, Qdrant client, and Postgres session so the suite
runs hermetically. End-to-end behaviour against the live stack is
exercised in the smoke script (``scripts/smoke_hybrid.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest

from src.embeddings.bge_m3 import DENSE_DIM, EncodedBatch
from src.retrieval.hybrid import HybridSearchTimings, hybrid_search
from src.retrieval.schemas import ChannelHit, HybridHit

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeEncoder:
    """Returns a deterministic dense + sparse for every call."""

    def __init__(self, *, sparse_for_query: dict[str, dict[str, float]] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.sparse_for_query = sparse_for_query or {}

    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int = 12,
        max_length: int = 2048,
    ) -> EncodedBatch:
        self.calls.append(list(texts))
        # One vector per text, full-zero except first dim = hash(text) % 100.
        dense = [[float(abs(hash(t)) % 100) / 100.0] + [0.0] * (DENSE_DIM - 1) for t in texts]
        sparse = [self.sparse_for_query.get(t, {"42": 0.5}) for t in texts]
        return EncodedBatch(dense=dense, sparse=sparse)


@dataclass
class FakePoint:
    id: str
    score: float


@dataclass
class FakeResponse:
    points: list[FakePoint] = field(default_factory=list)


@dataclass
class FakeQdrantClient:
    """Returns different responses based on which named vector was used.

    ``dense_hits`` and ``sparse_hits`` map to the two ``query_points``
    calls hybrid orchestrator makes (one per Qdrant channel).
    """

    dense_hits: list[FakePoint] = field(default_factory=list)
    sparse_hits: list[FakePoint] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)

    def query_points(
        self,
        collection_name: str,
        query: Any,
        *,
        using: str | None = None,
        limit: int = 10,
        **kwargs: Any,
    ) -> FakeResponse:
        self.calls.append(
            {
                "collection_name": collection_name,
                "using": using,
                "limit": limit,
            }
        )
        if using == "bge_m3_dense":
            return FakeResponse(points=list(self.dense_hits))
        if using == "bge_m3_sparse":
            return FakeResponse(points=list(self.sparse_hits))
        return FakeResponse()


# ---------------------------------------------------------------------------
# Helpers — build a minimal seeded DB session via the existing integration
# fixtures. Pure unit tests cannot exercise enrichment because that needs
# Postgres; we patch ``_enrich`` for the unit-only path and rely on the
# integration suite for the JOIN.
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_enrich(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Stub ``_enrich`` so unit tests do not need Postgres.

    Returns a list that the test can inspect to verify which fused hits
    reached enrichment. The substitute echoes them back as ``HybridHit``
    instances with placeholder text so downstream assertions work.
    """
    captured: list[dict[str, Any]] = []

    async def _stub(_session: Any, fused: list[Any]) -> list[HybridHit]:
        captured.append({"fused_count": len(fused)})
        return [
            HybridHit(
                chunk_id=f.doc_id,
                work_canonical_id="testwork",
                segment_id=f"testwork:{i}",
                parent_chunk_id=None,
                is_parent=False,
                text=f"placeholder text {i}",
                rrf_score=f.score,
                per_channel_rank=f.per_channel_rank,
            )
            for i, f in enumerate(fused)
        ]

    from src.retrieval import hybrid

    monkeypatch.setattr(hybrid, "_enrich", _stub)
    return captured


# Stub for bm25.search — also async, also needs no DB in unit tests.
@pytest.fixture
def fake_bm25(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    captured: dict[str, list[Any]] = {"hits": []}

    async def _stub(_session: Any, _query: str, *, limit: int = 10, **_: Any) -> list[Any]:
        return captured["hits"]

    from src.retrieval import bm25, hybrid

    # Patch the symbol the orchestrator imported (bm25 module reference).
    monkeypatch.setattr(hybrid.bm25, "search", _stub)
    # Defensive: also patch the original module so a future re-import
    # path would still see the stub.
    monkeypatch.setattr(bm25, "search", _stub)
    return captured


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_query_short_circuits_without_invoking_anyone(
    fake_enrich: list[dict[str, Any]], fake_bm25: dict[str, list[Any]]
) -> None:
    encoder = FakeEncoder()
    client = FakeQdrantClient()

    hits, timings = await hybrid_search(
        query="",
        encoder=encoder,
        qdrant_client=client,
        db_session=object(),  # type: ignore[arg-type]
    )

    assert hits == []
    assert timings == HybridSearchTimings(0.0, 0.0, 0.0, 0.0, 0.0)
    assert encoder.calls == []
    assert client.calls == []
    assert fake_enrich == []


@pytest.mark.asyncio
async def test_whitespace_only_query_treated_as_empty(
    fake_enrich: list[dict[str, Any]], fake_bm25: dict[str, list[Any]]
) -> None:
    encoder = FakeEncoder()
    client = FakeQdrantClient()
    hits, _ = await hybrid_search(
        query="   \t\n  ",
        encoder=encoder,
        qdrant_client=client,
        db_session=object(),  # type: ignore[arg-type]
    )
    assert hits == []
    assert encoder.calls == []


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_runs_all_three_channels_and_fuses(
    fake_enrich: list[dict[str, Any]], fake_bm25: dict[str, list[Any]]
) -> None:
    chunk_a = uuid4()
    chunk_b = uuid4()
    chunk_c = uuid4()

    encoder = FakeEncoder()
    client = FakeQdrantClient(
        dense_hits=[FakePoint(id=str(chunk_a), score=0.9), FakePoint(id=str(chunk_b), score=0.8)],
        sparse_hits=[FakePoint(id=str(chunk_b), score=0.5), FakePoint(id=str(chunk_c), score=0.4)],
    )
    fake_bm25["hits"] = [
        ChannelHit(chunk_id=chunk_c, score=0.7),
        ChannelHit(chunk_id=chunk_a, score=0.6),
    ]

    hits, timings = await hybrid_search(
        query="foo",
        encoder=encoder,
        qdrant_client=client,
        db_session=object(),  # type: ignore[arg-type]
    )

    # Encoder was called exactly once with the query.
    assert encoder.calls == [["foo"]]
    # Both Qdrant heads were queried.
    using_seen = sorted(c["using"] for c in client.calls)
    assert using_seen == ["bge_m3_dense", "bge_m3_sparse"]
    # Three docs flowed into enrichment.
    assert fake_enrich == [{"fused_count": 3}]
    # All three docs make it back as HybridHits.
    chunk_ids = {h.chunk_id for h in hits}
    assert chunk_ids == {chunk_a, chunk_b, chunk_c}
    # Timings are non-negative and total adds up to roughly the parts.
    assert timings.total_s >= timings.encode_s + timings.channels_s
    # Per-channel ranks survive end-to-end.
    by_id = {h.chunk_id: h for h in hits}
    assert by_id[chunk_a].per_channel_rank == {"dense": 1, "sparse": None, "bm25": 2}
    assert by_id[chunk_b].per_channel_rank == {"dense": 2, "sparse": 1, "bm25": None}
    assert by_id[chunk_c].per_channel_rank == {"dense": None, "sparse": 2, "bm25": 1}


@pytest.mark.asyncio
async def test_orchestrator_truncates_to_top_k(
    fake_enrich: list[dict[str, Any]], fake_bm25: dict[str, list[Any]]
) -> None:
    chunks = [uuid4() for _ in range(10)]
    encoder = FakeEncoder()
    client = FakeQdrantClient(
        dense_hits=[FakePoint(id=str(c), score=1.0 - i * 0.01) for i, c in enumerate(chunks)],
    )
    fake_bm25["hits"] = []

    hits, _ = await hybrid_search(
        query="foo",
        encoder=encoder,
        qdrant_client=client,
        db_session=object(),  # type: ignore[arg-type]
        top_k=3,
    )
    assert len(hits) == 3
    # The top 3 dense hits should be the first 3 in our generated list.
    assert [h.chunk_id for h in hits] == chunks[:3]


@pytest.mark.asyncio
async def test_orchestrator_passes_per_channel_limit(
    fake_enrich: list[dict[str, Any]], fake_bm25: dict[str, list[Any]]
) -> None:
    encoder = FakeEncoder()
    client = FakeQdrantClient()
    await hybrid_search(
        query="foo",
        encoder=encoder,
        qdrant_client=client,
        db_session=object(),  # type: ignore[arg-type]
        per_channel_limit=50,
    )
    for call in client.calls:
        assert call["limit"] == 50


@pytest.mark.asyncio
async def test_orchestrator_returns_empty_when_no_channel_hits(
    fake_enrich: list[dict[str, Any]], fake_bm25: dict[str, list[Any]]
) -> None:
    encoder = FakeEncoder()
    client = FakeQdrantClient()  # no hits configured
    fake_bm25["hits"] = []

    hits, timings = await hybrid_search(
        query="foo",
        encoder=encoder,
        qdrant_client=client,
        db_session=object(),  # type: ignore[arg-type]
    )
    assert hits == []
    # Encoder still ran (so timings.encode_s > 0); enrichment did not.
    assert timings.encode_s >= 0.0
    assert timings.enrich_s == 0.0
    assert fake_enrich == []
