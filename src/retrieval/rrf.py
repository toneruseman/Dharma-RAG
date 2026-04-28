"""Reciprocal Rank Fusion — combine ranked lists from independent retrievers.

Why RRF
-------
On day 10 we shipped two scoring channels (BGE-M3 dense + sparse) via
Qdrant; on day 11 we added BM25 via Postgres FTS. Their score scales
are *incomparable*:

* dense cosine ∈ [-1, 1] (typically 0.0-1.0 for our corpus)
* sparse dot product ∈ [0, ~3] (unbounded above, depends on token weights)
* BM25 ts_rank_cd ∈ [0, ~2] (depends on document length and term density)

Naive score addition would let whichever channel happens to have the
largest scale dominate the fused ranking. Min-max or z-score
normalisation requires per-corpus statistics and does not generalise to
new queries cleanly.

**Reciprocal Rank Fusion** (Cormack et al. 2009) sidesteps the problem
entirely by ignoring scores and operating on *ranks*:

    RRF(d) = sum over channels c of  1 / (k + rank_c(d))

If document ``d`` is on rank 1 in dense, rank 5 in sparse, and not in
BM25's top-N, its RRF score is ``1/(k+1) + 1/(k+5) + 0``. The constant
``k`` (canonical value: 60) flattens the difference between adjacent
ranks: position 1 contributes 1/61 ≈ 0.0164, position 2 → 1/62 ≈ 0.0161
— almost identical. That makes "appearing at all near the top of two
channels" far more valuable than "winning #1 in just one channel",
which empirically gives better results on heterogeneous retrievers.

Design
------
* **Pure function.** No DB, no async, no I/O. Trivial to unit-test
  with hand-built ranked lists (see ``test_rrf.py``).
* **Channel weights deferred.** The classical RRF formula is unweighted.
  Day-14 eval will tell us whether we should bias towards a particular
  channel; until then equal weights match the plan and avoid premature
  optimisation.
* **Ties broken stably.** When two documents tie on RRF score, we keep
  whichever appeared earlier in the input. This makes the function
  deterministic for the same inputs and friendly to snapshot tests.
"""

from __future__ import annotations

import logging
from collections.abc import Hashable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# The canonical RRF constant from the original paper. Larger k means
# less aggressive penalisation of lower ranks, giving each channel a
# more even contribution. 60 is the off-the-shelf value that keeps
# rank-1 vs rank-30 differences in a useful range.
DEFAULT_K: int = 60

# The fuser does not care whether callers pass UUIDs, strings, or
# anything else hashable. Production code passes UUIDs (chunk ids);
# tests pass plain strings ("a", "b") for readability. We use
# ``Hashable`` directly rather than a generic to keep the API simple
# under the project's mypy 3.11 target — a TypeVar would buy us
# call-site type narrowing at the cost of complicating the signature.


@dataclass(frozen=True, slots=True)
class FusedHit:
    """One fused result with provenance for debugging.

    ``per_channel_rank`` makes it easy to spot retrieval pathologies in
    the API response — e.g. "this document only ranked because BM25 saw
    it; dense and sparse did not" is a clear signal that the dense
    channel may be missing something or that the sparse signal is weak
    on that query.
    """

    doc_id: Hashable
    score: float
    per_channel_rank: dict[str, int | None]


def reciprocal_rank_fusion(
    channel_results: dict[str, list[Hashable]],
    *,
    k: int = DEFAULT_K,
    limit: int | None = None,
) -> list[FusedHit]:
    """Combine ranked lists from N retrievers into one fused ranking.

    Parameters
    ----------
    channel_results:
        Mapping ``channel_name -> [doc_id_at_rank_1, doc_id_at_rank_2, ...]``.
        Each list MUST be in descending-relevance order; the function
        does not re-sort. Lists may have different lengths and may share
        any subset of doc_ids.
    k:
        RRF flattening constant. Defaults to 60 (the paper's recommendation).
        Lower ``k`` makes top ranks dominate; higher ``k`` makes participation
        across channels matter more.
    limit:
        Truncate the output to the top-N. ``None`` returns everything.
        Day-12 plan calls with ``limit=20`` so 20 candidates flow into
        day-13's reranker.

    Returns
    -------
    Documents sorted by descending RRF score. Each entry carries its
    per-channel ranks (``None`` when the doc did not appear in a given
    channel's top list) for downstream observability.

    Raises
    ------
    ValueError:
        If ``k <= 0``. RRF with ``k=0`` would assign infinite weight to
        rank-1 documents, defeating the algorithm's whole point.

    Examples
    --------
    >>> result = reciprocal_rank_fusion(
    ...     {"dense": ["a", "b", "c"], "sparse": ["b", "a", "d"]}, k=60
    ... )
    >>> [h.doc_id for h in result[:3]]
    ['a', 'b', 'c']
    """
    if k <= 0:
        raise ValueError(f"RRF constant k must be positive, got {k}")
    if not channel_results:
        return []

    # First pass: for every (channel, doc) pair, record the doc's 1-based
    # rank. We use 1-based here to match the paper; the formula 1/(k+rank)
    # then gives positive scores in (0, 1/(k+1)].
    per_channel_rank: dict[Hashable, dict[str, int]] = {}
    insertion_order: dict[Hashable, int] = {}
    next_index = 0
    for channel, ranked in channel_results.items():
        for rank, doc_id in enumerate(ranked, start=1):
            doc_ranks = per_channel_rank.setdefault(doc_id, {})
            # If the same doc appears twice in one channel (shouldn't,
            # but be defensive) we keep its best rank — matches the
            # intuitive "highest position" semantics.
            existing = doc_ranks.get(channel)
            if existing is None or rank < existing:
                doc_ranks[channel] = rank
            if doc_id not in insertion_order:
                insertion_order[doc_id] = next_index
                next_index += 1

    # Second pass: compute RRF score per doc, fill missing channels with
    # None for the per_channel_rank field of FusedHit.
    all_channels = list(channel_results.keys())
    scored: list[tuple[float, int, FusedHit]] = []
    for doc_id, ranks in per_channel_rank.items():
        score = sum(1.0 / (k + rank) for rank in ranks.values())
        full_ranks: dict[str, int | None] = {ch: ranks.get(ch) for ch in all_channels}
        hit = FusedHit(doc_id=doc_id, score=score, per_channel_rank=full_ranks)
        # Sort key: (-score, insertion_order) — descending score, then
        # original first-appearance for stability across calls.
        scored.append((-score, insertion_order[doc_id], hit))

    scored.sort(key=lambda triple: (triple[0], triple[1]))
    fused = [triple[2] for triple in scored]

    if limit is not None:
        fused = fused[:limit]
    logger.debug(
        "RRF fused %d unique docs from %d channels (k=%d)",
        len(fused),
        len(channel_results),
        k,
    )
    return fused
