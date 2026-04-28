"""Sparse-vector retrieval channel against Qdrant's ``bge_m3_sparse`` head.

Mirror of :mod:`src.retrieval.dense`, but for the BGE-M3 lexical head.
The lexical head returns ``{token_id: weight}`` dicts; Qdrant accepts
the equivalent ``SparseVector(indices=[...], values=[...])``.

Kept separate from dense because the Qdrant query argument types
differ (list of floats vs SparseVector), the empty-input semantics
differ (an all-stopword query produces an empty sparse dict, which is
valid but yields no hits — we short-circuit), and split modules read
cleaner than one function with mixed responsibilities.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol
from uuid import UUID

from src.embeddings.indexer import COLLECTION_NAME, SPARSE_VECTOR_NAME
from src.retrieval.schemas import ChannelHit

logger = logging.getLogger(__name__)


class QdrantQueryProtocol(Protocol):
    """Subset of ``QdrantClient`` used here. See :mod:`dense` for rationale."""

    def query_points(
        self,
        collection_name: str,
        query: Any,
        *,
        using: str | None = ...,
        limit: int = ...,
        **kwargs: Any,
    ) -> Any: ...


def sparse_search(
    client: QdrantQueryProtocol,
    sparse_weights: dict[str, float],
    *,
    collection: str = COLLECTION_NAME,
    limit: int = 30,
) -> list[ChannelHit]:
    """Run a sparse-vector query against Qdrant's ``bge_m3_sparse`` head.

    Parameters
    ----------
    sparse_weights:
        Output of :class:`src.embeddings.bge_m3.EncodedBatch.sparse[i]` —
        a dict ``{token_id_as_string: weight_as_float}``. Empty dict is
        legal (BGE-M3 emits one when every input token is a stopword or
        sub-word with zero learned weight) and produces zero hits.
    collection, limit:
        Same semantics as :func:`src.retrieval.dense.dense_search`.

    Returns
    -------
    Ranked list of :class:`ChannelHit`. Empty when the input dict is
    empty or no point in the collection shares a positive-weight token.
    """
    if not sparse_weights:
        return []

    # Lazy import: qdrant-client.models pulls in pydantic-v2 model
    # definitions. Importing it at module top adds noticeable test
    # collection time for tests that do not exercise sparse search.
    from qdrant_client.models import SparseVector  # noqa: PLC0415

    indices = [int(token_id) for token_id in sparse_weights]
    values = [float(weight) for weight in sparse_weights.values()]

    response = client.query_points(
        collection_name=collection,
        query=SparseVector(indices=indices, values=values),
        using=SPARSE_VECTOR_NAME,
        limit=limit,
        with_payload=False,
        with_vectors=False,
    )
    points = getattr(response, "points", response)
    hits: list[ChannelHit] = []
    for p in points:
        chunk_id = UUID(str(p.id))
        hits.append(ChannelHit(chunk_id=chunk_id, score=float(p.score)))
    logger.debug(
        "sparse_search returned %d hits from %r (limit=%d)",
        len(hits),
        collection,
        limit,
    )
    return hits
