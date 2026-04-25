"""Unit tests for the dense + sparse Qdrant channel wrappers.

Both functions are thin pass-throughs over ``client.query_points``, so
the tests focus on argument plumbing and edge cases (empty input, ID
coercion, the ``response.points`` attribute fallback). The real Qdrant
behaviour is exercised in ``tests/integration/test_qdrant_indexer.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from src.embeddings.indexer import DENSE_VECTOR_NAME, SPARSE_VECTOR_NAME
from src.retrieval.dense import dense_search
from src.retrieval.schemas import ChannelHit
from src.retrieval.sparse import sparse_search

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakePoint:
    id: str
    score: float


@dataclass
class FakeResponse:
    """Mirrors Qdrant 1.17's QueryResponse shape: ``.points`` attribute."""

    points: list[FakePoint] = field(default_factory=list)


@dataclass
class FakeClient:
    """Records query_points calls and returns a configured response."""

    response: Any = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    def query_points(
        self,
        collection_name: str,
        query: Any,
        *,
        using: str | None = None,
        limit: int = 10,
        **kwargs: Any,
    ) -> Any:
        self.calls.append(
            {
                "collection_name": collection_name,
                "query": query,
                "using": using,
                "limit": limit,
                "kwargs": kwargs,
            }
        )
        return self.response if self.response is not None else FakeResponse()


# ---------------------------------------------------------------------------
# dense_search
# ---------------------------------------------------------------------------


def test_dense_search_passes_through_vector_and_named_head() -> None:
    point_id = uuid4()
    client = FakeClient(response=FakeResponse(points=[FakePoint(id=str(point_id), score=0.9)]))
    vector = [0.1, 0.2, 0.3]

    hits = dense_search(client, vector, limit=5)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["query"] == [0.1, 0.2, 0.3]
    assert call["using"] == DENSE_VECTOR_NAME
    assert call["limit"] == 5
    assert hits == [ChannelHit(chunk_id=point_id, score=0.9)]


def test_dense_search_empty_vector_returns_empty_without_hitting_client() -> None:
    client = FakeClient()
    hits = dense_search(client, [])
    assert hits == []
    assert client.calls == []


def test_dense_search_coerces_string_id_to_uuid() -> None:
    real_uuid = uuid4()
    client = FakeClient(response=FakeResponse(points=[FakePoint(id=str(real_uuid), score=0.5)]))
    hits = dense_search(client, [0.1])
    assert isinstance(hits[0].chunk_id, UUID)
    assert hits[0].chunk_id == real_uuid


def test_dense_search_handles_response_without_points_attr() -> None:
    """Older qdrant-client versions return a plain list. The fallback
    ``getattr(response, "points", response)`` keeps us compatible.
    """
    client = FakeClient(response=[FakePoint(id=str(uuid4()), score=0.7)])
    hits = dense_search(client, [0.1])
    assert len(hits) == 1


def test_dense_search_default_collection_is_dharma_v1() -> None:
    client = FakeClient()
    dense_search(client, [0.1])
    assert client.calls[0]["collection_name"] == "dharma_v1"


def test_dense_search_with_payload_disabled_to_save_bandwidth() -> None:
    """We do not need payload from Qdrant — orchestrator joins Postgres
    instead. Disabling ``with_payload`` reduces round-trip size.
    """
    client = FakeClient()
    dense_search(client, [0.1])
    assert client.calls[0]["kwargs"].get("with_payload") is False
    assert client.calls[0]["kwargs"].get("with_vectors") is False


# ---------------------------------------------------------------------------
# sparse_search
# ---------------------------------------------------------------------------


def test_sparse_search_passes_through_indices_values_and_named_head() -> None:
    point_id = uuid4()
    client = FakeClient(response=FakeResponse(points=[FakePoint(id=str(point_id), score=0.42)]))

    hits = sparse_search(client, {"100": 0.8, "200": 0.5}, limit=7)

    assert len(client.calls) == 1
    call = client.calls[0]
    # The query argument is a SparseVector(indices=..., values=...)
    sparse = call["query"]
    assert sparse.indices == [100, 200]
    assert sparse.values == [0.8, 0.5]
    assert call["using"] == SPARSE_VECTOR_NAME
    assert call["limit"] == 7
    assert hits == [ChannelHit(chunk_id=point_id, score=0.42)]


def test_sparse_search_empty_dict_returns_empty_without_hitting_client() -> None:
    client = FakeClient()
    hits = sparse_search(client, {})
    assert hits == []
    assert client.calls == []


def test_sparse_search_coerces_string_id_to_uuid() -> None:
    real_uuid = uuid4()
    client = FakeClient(response=FakeResponse(points=[FakePoint(id=str(real_uuid), score=0.3)]))
    hits = sparse_search(client, {"1": 0.5})
    assert isinstance(hits[0].chunk_id, UUID)
    assert hits[0].chunk_id == real_uuid


def test_sparse_search_handles_response_without_points_attr() -> None:
    client = FakeClient(response=[FakePoint(id=str(uuid4()), score=0.4)])
    hits = sparse_search(client, {"1": 0.5})
    assert len(hits) == 1


def test_sparse_search_default_collection_and_payload_off() -> None:
    client = FakeClient()
    sparse_search(client, {"1": 0.5})
    assert client.calls[0]["collection_name"] == "dharma_v1"
    assert client.calls[0]["kwargs"].get("with_payload") is False
