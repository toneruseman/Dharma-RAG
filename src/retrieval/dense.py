"""Dense-vector retrieval channel against Qdrant's ``bge_m3_dense`` head.

Thin wrapper around :func:`qdrant_client.QdrantClient.query_points` for
the named dense vector. Kept tiny on purpose — heavy lifting (encoding,
RRF, payload fetch) lives in dedicated modules; this one just speaks
Qdrant. That makes it the natural place for one-off behavioural tweaks
(e.g. score thresholds, result ef tuning) when the time comes.

The corresponding sparse channel is :mod:`src.retrieval.sparse`. They
are split because the Qdrant API takes different argument types
(`list[float]` for dense, `SparseVector` for sparse), and a single
function with a Union argument would be harder to read than two
focused ones.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID

from src.embeddings.indexer import COLLECTION_NAME, DENSE_VECTOR_NAME
from src.retrieval.schemas import ChannelHit

logger = logging.getLogger(__name__)


class QdrantQueryProtocol(Protocol):
    """Subset of ``QdrantClient`` we exercise from this module.

    Declaring a Protocol means tests can pass a fake without needing
    qdrant-client installed (it's already a dep, but the principle keeps
    the unit suite hermetic).
    """

    def query_points(
        self,
        collection_name: str,
        query: Any,
        *,
        using: str | None = ...,
        limit: int = ...,
        **kwargs: Any,
    ) -> Any: ...


def dense_search(
    client: QdrantQueryProtocol,
    dense_vector: Sequence[float],
    *,
    collection: str = COLLECTION_NAME,
    limit: int = 30,
) -> list[ChannelHit]:
    """Run a dense-vector query against Qdrant's ``bge_m3_dense`` head.

    Parameters
    ----------
    client:
        Qdrant client (production: ``QdrantClient`` from qdrant-client).
        Tests inject a fake satisfying :class:`QdrantQueryProtocol`.
    dense_vector:
        BGE-M3 dense output (list of 1024 floats). The caller is
        responsible for encoding; we do not pull in the encoder here so
        the function stays sync and the orchestrator can encode once
        and dispatch dense + sparse in parallel.
    collection:
        Override the target collection. Defaults to ``dharma_v1`` (the
        one populated by day-10's indexer).
    limit:
        Top-N to return. Day-12 plan: 30 per channel. RRF then truncates
        the union of the three lists down to 20.

    Returns
    -------
    Ranked list of :class:`ChannelHit`. Empty when the collection is
    empty or all candidates score below Qdrant's internal threshold —
    we do not raise, the orchestrator treats empty as "this channel
    contributed nothing" and proceeds.
    """
    if not dense_vector:
        # Defensive: empty vectors would trip Qdrant's input validation
        # with a noisy error. Treating it as "no signal, no hits" mirrors
        # the BM25 channel's behaviour on empty queries.
        return []

    response = client.query_points(
        collection_name=collection,
        query=list(dense_vector),
        using=DENSE_VECTOR_NAME,
        limit=limit,
        with_payload=False,
        with_vectors=False,
    )
    points = getattr(response, "points", response)
    hits: list[ChannelHit] = []
    for p in points:
        # Qdrant may return point IDs as plain strings (Qdrant's storage
        # is UUID-string in our schema). Coerce to UUID for downstream
        # type stability with the BM25 channel.
        chunk_id = UUID(str(p.id))
        hits.append(ChannelHit(chunk_id=chunk_id, score=float(p.score)))
    logger.debug(
        "dense_search returned %d hits from %r (limit=%d)",
        len(hits),
        collection,
        limit,
    )
    return hits
