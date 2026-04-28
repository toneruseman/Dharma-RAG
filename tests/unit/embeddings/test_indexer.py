"""Unit tests for the Qdrant indexer.

No real Qdrant, no real BGE-M3 — every test injects a ``FakeQdrantClient``
and ``FakeEncoder`` so the suite runs in under a second with no network
or GPU.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.embeddings.bge_m3 import DENSE_DIM, EncodedBatch
from src.embeddings.indexer import (
    COLLECTION_NAME,
    DENSE_VECTOR_NAME,
    SPARSE_VECTOR_NAME,
    ChunkForIndexing,
    IndexerStats,
    batches_from_iterable,
    build_point,
    build_points,
    ensure_collection,
    index_corpus,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class FakeQdrantClient:
    """Records every client call so tests can assert on sequence + args."""

    existing_collections: set[str] = field(default_factory=set)
    created: list[dict[str, Any]] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    upserts: list[dict[str, Any]] = field(default_factory=list)
    upsert_fail_on_batch_index: int | None = None
    _upsert_calls: int = 0

    def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.existing_collections

    def create_collection(
        self,
        collection_name: str,
        vectors_config: Any,
        sparse_vectors_config: Any,
        **kwargs: Any,
    ) -> None:
        self.created.append(
            {
                "collection_name": collection_name,
                "vectors_config": vectors_config,
                "sparse_vectors_config": sparse_vectors_config,
                "kwargs": kwargs,
            }
        )
        self.existing_collections.add(collection_name)

    def delete_collection(self, collection_name: str) -> None:
        self.deleted.append(collection_name)
        self.existing_collections.discard(collection_name)

    def upsert(
        self,
        collection_name: str,
        points: list[Any],
        **kwargs: Any,
    ) -> None:
        if (
            self.upsert_fail_on_batch_index is not None
            and self._upsert_calls == self.upsert_fail_on_batch_index
        ):
            self._upsert_calls += 1
            raise RuntimeError("simulated upsert failure")
        self._upsert_calls += 1
        self.upserts.append(
            {
                "collection_name": collection_name,
                "points": points,
                "kwargs": kwargs,
            }
        )

    def count(self, collection_name: str, exact: bool = True) -> int:
        return sum(
            len(u["points"]) for u in self.upserts if u["collection_name"] == collection_name
        )


class FakeEncoder:
    """Deterministic stand-in for :class:`BGEM3Encoder`."""

    def __init__(self, *, fail_on_call: int | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail_on_call = fail_on_call

    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int = 12,
        max_length: int = 2048,
    ) -> EncodedBatch:
        self.calls.append(
            {"texts": list(texts), "batch_size": batch_size, "max_length": max_length}
        )
        if self.fail_on_call is not None and len(self.calls) - 1 == self.fail_on_call:
            raise RuntimeError("simulated encoder failure")
        dense = [[float(i)] * DENSE_DIM for i in range(len(texts))]
        sparse = [{"42": 0.5 + i * 0.01, "7": 0.3} for i in range(len(texts))]
        return EncodedBatch(dense=dense, sparse=sparse)


def _sample_chunk(
    *,
    chunk_id: UUID | None = None,
    parent_chunk_id: UUID | None = None,
    text: str = "hello world",
    is_parent: bool = False,
    pericope_id: str | None = None,
) -> ChunkForIndexing:
    return ChunkForIndexing(
        chunk_id=chunk_id or uuid4(),
        text=text,
        parent_chunk_id=parent_chunk_id,
        instance_id=uuid4(),
        work_canonical_id="mn10",
        segment_id="mn10:12.3",
        sequence=7,
        is_parent=is_parent,
        token_count=42,
        pericope_id=pericope_id,
    )


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------


def test_ensure_collection_creates_when_missing() -> None:
    client = FakeQdrantClient()
    created = ensure_collection(client)
    assert created is True
    assert len(client.created) == 1
    cfg = client.created[0]
    assert cfg["collection_name"] == COLLECTION_NAME
    assert DENSE_VECTOR_NAME in cfg["vectors_config"]
    assert SPARSE_VECTOR_NAME in cfg["sparse_vectors_config"]
    assert cfg["vectors_config"][DENSE_VECTOR_NAME].size == DENSE_DIM


def test_ensure_collection_is_noop_when_already_exists() -> None:
    client = FakeQdrantClient(existing_collections={COLLECTION_NAME})
    created = ensure_collection(client)
    assert created is False
    assert client.created == []
    assert client.deleted == []


def test_ensure_collection_recreates_when_requested() -> None:
    client = FakeQdrantClient(existing_collections={COLLECTION_NAME})
    created = ensure_collection(client, recreate=True)
    assert created is True
    assert client.deleted == [COLLECTION_NAME]
    assert len(client.created) == 1


def test_ensure_collection_respects_custom_dim() -> None:
    client = FakeQdrantClient()
    ensure_collection(client, dense_dim=384)
    assert client.created[0]["vectors_config"][DENSE_VECTOR_NAME].size == 384


# ---------------------------------------------------------------------------
# build_point / build_points
# ---------------------------------------------------------------------------


def test_build_point_payload_covers_required_fields() -> None:
    chunk = _sample_chunk()
    dense = [0.1] * DENSE_DIM
    sparse = {"42": 0.8, "7": 0.2}

    point = build_point(chunk, dense, sparse)

    assert point.id == str(chunk.chunk_id)
    assert point.payload["chunk_id"] == str(chunk.chunk_id)
    assert point.payload["instance_id"] == str(chunk.instance_id)
    assert point.payload["work_canonical_id"] == "mn10"
    assert point.payload["segment_id"] == "mn10:12.3"
    assert point.payload["sequence"] == 7
    assert point.payload["is_parent"] is False
    assert point.payload["token_count"] == 42
    assert point.payload["parent_chunk_id"] is None


def test_build_point_includes_pericope_id_when_set() -> None:
    chunk = _sample_chunk(pericope_id="jhana-formula-1")
    point = build_point(chunk, [0.0] * DENSE_DIM, {})
    assert point.payload["pericope_id"] == "jhana-formula-1"


def test_build_point_omits_pericope_id_when_none() -> None:
    chunk = _sample_chunk()
    point = build_point(chunk, [0.0] * DENSE_DIM, {})
    assert "pericope_id" not in point.payload


def test_build_point_serialises_parent_chunk_id_as_string() -> None:
    parent_id = uuid4()
    chunk = _sample_chunk(parent_chunk_id=parent_id)
    point = build_point(chunk, [0.0] * DENSE_DIM, {})
    assert point.payload["parent_chunk_id"] == str(parent_id)


def test_build_point_vectors_carry_named_keys() -> None:
    chunk = _sample_chunk()
    dense = [0.5] * DENSE_DIM
    sparse = {"100": 1.5, "200": 0.25}

    point = build_point(chunk, dense, sparse)

    assert DENSE_VECTOR_NAME in point.vector
    assert SPARSE_VECTOR_NAME in point.vector
    assert point.vector[DENSE_VECTOR_NAME] == dense
    sv = point.vector[SPARSE_VECTOR_NAME]
    # indices/values are parallel arrays; order of dict keys is preserved
    # on CPython 3.7+, so this assertion is deterministic.
    assert sv.indices == [100, 200]
    assert sv.values == [1.5, 0.25]


def test_build_point_accepts_empty_sparse() -> None:
    chunk = _sample_chunk()
    point = build_point(chunk, [0.0] * DENSE_DIM, {})
    sv = point.vector[SPARSE_VECTOR_NAME]
    assert sv.indices == []
    assert sv.values == []


def test_build_points_zips_batch_correctly() -> None:
    chunks = [_sample_chunk(text=f"c{i}") for i in range(3)]
    dense = [[float(i)] * DENSE_DIM for i in range(3)]
    sparse: list[dict[str, float]] = [{"1": 0.1}, {"2": 0.2}, {"3": 0.3}]
    encoded = EncodedBatch(dense=dense, sparse=sparse)

    points = build_points(chunks, encoded)

    assert len(points) == 3
    for i, point in enumerate(points):
        assert point.id == str(chunks[i].chunk_id)
        assert point.vector[DENSE_VECTOR_NAME] == dense[i]
        expected_idx = [int(k) for k in sparse[i].keys()]
        assert points[i].vector[SPARSE_VECTOR_NAME].indices == expected_idx


def test_build_points_raises_on_misaligned_batch() -> None:
    chunks = [_sample_chunk() for _ in range(3)]
    encoded = EncodedBatch(dense=[[0.0] * DENSE_DIM, [0.0] * DENSE_DIM], sparse=[{}, {}])
    with pytest.raises(RuntimeError, match="Misaligned batch"):
        build_points(chunks, encoded)


# ---------------------------------------------------------------------------
# index_corpus orchestration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_index_corpus_happy_path() -> None:
    client = FakeQdrantClient(existing_collections={COLLECTION_NAME})
    encoder = FakeEncoder()

    batch1 = [_sample_chunk(text=f"a{i}") for i in range(3)]
    batch2 = [_sample_chunk(text=f"b{i}") for i in range(2)]

    stats = await index_corpus(
        client=client,
        encoder=encoder,
        batches=batches_from_iterable([batch1, batch2]),
    )

    assert stats.batches_processed == 2
    assert stats.chunks_encoded == 5
    assert stats.points_upserted == 5
    assert stats.failed_batches == []
    assert len(client.upserts) == 2
    assert len(client.upserts[0]["points"]) == 3
    assert len(client.upserts[1]["points"]) == 2


@pytest.mark.asyncio
async def test_index_corpus_skips_empty_batches() -> None:
    client = FakeQdrantClient(existing_collections={COLLECTION_NAME})
    encoder = FakeEncoder()
    real_chunk = _sample_chunk(text="real")

    stats = await index_corpus(
        client=client,
        encoder=encoder,
        batches=batches_from_iterable([[], [real_chunk], []]),
    )

    assert stats.skipped_empty == 2
    assert stats.points_upserted == 1
    # Encoder must have been invoked only for the non-empty batch.
    assert len(encoder.calls) == 1
    assert encoder.calls[0]["texts"] == ["real"]


@pytest.mark.asyncio
async def test_index_corpus_records_encoder_failure_and_continues() -> None:
    client = FakeQdrantClient(existing_collections={COLLECTION_NAME})
    encoder = FakeEncoder(fail_on_call=0)  # first batch fails

    batch_good = [_sample_chunk(text="good")]
    batch_also_good = [_sample_chunk(text="also")]

    stats = await index_corpus(
        client=client,
        encoder=encoder,
        batches=batches_from_iterable([batch_good, batch_also_good]),
    )

    assert stats.batches_processed == 2
    assert stats.failed_batches == [0]
    assert stats.points_upserted == 1
    assert len(client.upserts) == 1
    assert client.upserts[0]["points"][0].payload["chunk_id"] == str(batch_also_good[0].chunk_id)


@pytest.mark.asyncio
async def test_index_corpus_records_upsert_failure_and_continues() -> None:
    client = FakeQdrantClient(existing_collections={COLLECTION_NAME}, upsert_fail_on_batch_index=0)
    encoder = FakeEncoder()

    stats = await index_corpus(
        client=client,
        encoder=encoder,
        batches=batches_from_iterable([[_sample_chunk()], [_sample_chunk()]]),
    )

    assert stats.failed_batches == [0]
    assert stats.points_upserted == 1
    # Encoder still ran on the failed batch (failure is at upsert stage)
    assert len(encoder.calls) == 2


@pytest.mark.asyncio
async def test_index_corpus_propagates_when_continue_on_error_false() -> None:
    client = FakeQdrantClient(existing_collections={COLLECTION_NAME})
    encoder = FakeEncoder(fail_on_call=0)

    with pytest.raises(RuntimeError, match="simulated encoder failure"):
        await index_corpus(
            client=client,
            encoder=encoder,
            batches=batches_from_iterable([[_sample_chunk()]]),
            continue_on_error=False,
        )


@pytest.mark.asyncio
async def test_index_corpus_passes_encoder_tuning() -> None:
    client = FakeQdrantClient(existing_collections={COLLECTION_NAME})
    encoder = FakeEncoder()

    await index_corpus(
        client=client,
        encoder=encoder,
        batches=batches_from_iterable([[_sample_chunk()]]),
        encoder_batch_size=64,
        encoder_max_length=512,
    )

    assert encoder.calls[0]["batch_size"] == 64
    assert encoder.calls[0]["max_length"] == 512


@pytest.mark.asyncio
async def test_index_corpus_empty_stream_is_a_noop() -> None:
    client = FakeQdrantClient(existing_collections={COLLECTION_NAME})
    encoder = FakeEncoder()

    stats = await index_corpus(
        client=client,
        encoder=encoder,
        batches=batches_from_iterable([]),
    )

    assert stats == IndexerStats()
    assert client.upserts == []
    assert encoder.calls == []
