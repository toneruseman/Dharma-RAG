"""Integration tests for the Qdrant indexer against a live Qdrant.

These tests verify that the PointStruct shape we build is actually
accepted by the real qdrant-client, that named vectors round-trip,
and that vector search on dense + sparse retrieves the expected points.

They are skipped automatically when Qdrant is unreachable — no docker,
no tests, no noise.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest

from src.embeddings.bge_m3 import DENSE_DIM, EncodedBatch
from src.embeddings.indexer import (
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    ChunkForIndexing,
    build_points,
    ensure_collection,
)

pytestmark = pytest.mark.integration

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")


def _qdrant_available() -> bool:
    """Return True if we can reach Qdrant on QDRANT_URL."""
    try:
        from qdrant_client import QdrantClient  # noqa: PLC0415
    except ImportError:
        return False
    try:
        client = QdrantClient(url=QDRANT_URL, timeout=2)
        client.get_collections()
    except Exception:
        return False
    return True


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _qdrant_available(), reason=f"Qdrant is not reachable at {QDRANT_URL}"),
]


@pytest.fixture
def test_collection() -> Iterator[str]:
    """Yield a fresh, uniquely-named collection and drop it on teardown."""
    from qdrant_client import QdrantClient  # noqa: PLC0415

    name = f"dharma_test_{uuid4().hex[:8]}"
    client = QdrantClient(url=QDRANT_URL)
    try:
        yield name
    finally:
        try:
            if client.collection_exists(name):
                client.delete_collection(name)
        finally:
            client.close()


def _small_chunk(text: str) -> ChunkForIndexing:
    return ChunkForIndexing(
        chunk_id=uuid4(),
        text=text,
        parent_chunk_id=None,
        instance_id=uuid4(),
        work_canonical_id="test1",
        segment_id="test1:0.1",
        sequence=0,
        is_parent=False,
        token_count=len(text.split()),
    )


def test_ensure_collection_creates_real_collection(test_collection: str) -> None:
    from qdrant_client import QdrantClient  # noqa: PLC0415

    client = QdrantClient(url=QDRANT_URL)
    try:
        created = ensure_collection(client, collection_name=test_collection)
        assert created is True
        info = client.get_collection(test_collection)
        # Named vectors structure check — presence is what we care about.
        vec_params = info.config.params.vectors
        assert DENSE_VECTOR_NAME in vec_params
        assert vec_params[DENSE_VECTOR_NAME].size == DENSE_DIM
        sparse_params = info.config.params.sparse_vectors
        assert sparse_params is not None
        assert SPARSE_VECTOR_NAME in sparse_params
    finally:
        client.close()


def test_upsert_and_retrieve_by_id(test_collection: str) -> None:
    """Build real PointStructs, upsert them, then retrieve by point ID."""
    from qdrant_client import QdrantClient  # noqa: PLC0415

    client = QdrantClient(url=QDRANT_URL)
    try:
        ensure_collection(client, collection_name=test_collection)

        chunks = [_small_chunk("sati means mindfulness"), _small_chunk("dukkha is suffering")]
        encoded = EncodedBatch(
            dense=[[0.1] * DENSE_DIM, [0.2] * DENSE_DIM],
            sparse=[{"1": 0.5, "2": 0.3}, {"3": 0.9}],
        )
        points = build_points(chunks, encoded)
        client.upsert(collection_name=test_collection, points=points)

        ids = [str(c.chunk_id) for c in chunks]
        retrieved = client.retrieve(
            collection_name=test_collection, ids=ids, with_payload=True, with_vectors=True
        )
        assert len(retrieved) == 2
        by_id = {r.id: r for r in retrieved}
        for chunk in chunks:
            row = by_id[str(chunk.chunk_id)]
            assert row.payload["work_canonical_id"] == "test1"
            assert row.payload["chunk_id"] == str(chunk.chunk_id)
            assert DENSE_VECTOR_NAME in row.vector
            assert SPARSE_VECTOR_NAME in row.vector
    finally:
        client.close()


def test_dense_search_ranks_closer_vector_first(test_collection: str) -> None:
    """Semantic search plumbing: a query vector close to point A should
    rank A above B.
    """
    from qdrant_client import QdrantClient  # noqa: PLC0415

    client = QdrantClient(url=QDRANT_URL)
    try:
        ensure_collection(client, collection_name=test_collection)

        chunk_a = _small_chunk("close point")
        chunk_b = _small_chunk("far point")
        # Distinct dense vectors. a is pointing along axis 0, b along axis 1.
        vec_a = [1.0] + [0.0] * (DENSE_DIM - 1)
        vec_b = [0.0] + [1.0] + [0.0] * (DENSE_DIM - 2)
        encoded = EncodedBatch(dense=[vec_a, vec_b], sparse=[{}, {}])
        client.upsert(
            collection_name=test_collection,
            points=build_points([chunk_a, chunk_b], encoded),
        )

        # A query vector identical to A's embedding should retrieve A
        # with cosine similarity 1.0 and rank it first.
        result = client.query_points(
            collection_name=test_collection,
            query=vec_a,
            using=DENSE_VECTOR_NAME,
            limit=2,
        )
        hits = result.points
        assert len(hits) == 2
        assert hits[0].id == str(chunk_a.chunk_id)
        assert hits[0].score == pytest.approx(1.0, abs=1e-4)
        assert hits[1].id == str(chunk_b.chunk_id)
        assert hits[0].score > hits[1].score
    finally:
        client.close()


def test_sparse_search_rates_matching_tokens_higher(test_collection: str) -> None:
    """Sparse vectors: a query that shares a strongly-weighted token
    should retrieve the point that has that token.
    """
    from qdrant_client import QdrantClient  # noqa: PLC0415
    from qdrant_client.models import SparseVector  # noqa: PLC0415

    client = QdrantClient(url=QDRANT_URL)
    try:
        ensure_collection(client, collection_name=test_collection)

        chunk_sati = _small_chunk("sati")
        chunk_dukkha = _small_chunk("dukkha")
        # Token id 111 represents "sati"; 222 represents "dukkha"
        encoded = EncodedBatch(
            dense=[[0.0] * DENSE_DIM, [0.0] * DENSE_DIM],
            sparse=[{"111": 0.9}, {"222": 0.9}],
        )
        client.upsert(
            collection_name=test_collection,
            points=build_points([chunk_sati, chunk_dukkha], encoded),
        )

        result = client.query_points(
            collection_name=test_collection,
            query=SparseVector(indices=[111], values=[1.0]),
            using=SPARSE_VECTOR_NAME,
            limit=2,
        )
        hits = result.points
        # Only the sati point should surface — dukkha has no token 111.
        assert hits
        assert hits[0].id == str(chunk_sati.chunk_id)
    finally:
        client.close()


def test_upsert_is_idempotent(test_collection: str) -> None:
    """Re-upserting the same chunk UUID is a no-op on count."""
    from qdrant_client import QdrantClient  # noqa: PLC0415

    client = QdrantClient(url=QDRANT_URL)
    try:
        ensure_collection(client, collection_name=test_collection)

        chunk = _small_chunk("idempotency check")
        encoded = EncodedBatch(dense=[[0.3] * DENSE_DIM], sparse=[{}])
        points = build_points([chunk], encoded)

        client.upsert(collection_name=test_collection, points=points)
        first_count = client.count(test_collection, exact=True).count

        client.upsert(collection_name=test_collection, points=points)
        second_count = client.count(test_collection, exact=True).count

        assert first_count == 1
        assert second_count == 1
    finally:
        client.close()
