"""Pure metric functions for retrieval evaluation.

All functions here operate on plain lists of strings (work IDs) and a
set of expected IDs — no dependency on hybrid_search, HybridHit, or
the database. That keeps them trivially unit-testable and reusable for
the buddhologist-curated v0.1 set later, or for Ragas integration on
day-22 where we may compute the same metrics over different result
shapes.

Metrics implemented
-------------------
* :func:`ref_hit_at_k` — does any expected work appear in the top-K?
  Binary 0/1 per query.
* :func:`reciprocal_rank` — 1/rank of the first expected hit, or 0 if
  none. Building block for :func:`mean_reciprocal_rank`.
* :func:`mean_reciprocal_rank` — average of :func:`reciprocal_rank`.

Why not Ragas now
-----------------
Ragas's ``context_recall`` / ``context_precision`` are LLM-judged: each
candidate is scored by an LLM against the question. That requires a
generation step, an API key, and per-query latency dwarfing the actual
retrieval. Day-22 brings Ragas after the LLM layer is wired. Today's
metrics are deterministic, fast (< 1 ms total), and answer the only
question that matters at this stage — *did the right document
surface, and how high?*
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


def ref_hit_at_k(retrieved_works: Sequence[str], expected: Iterable[str], *, k: int) -> int:
    """Return 1 if any expected work appears in the first ``k`` retrieved.

    Parameters
    ----------
    retrieved_works:
        Ranked list of work IDs as produced by the retrieval pipeline,
        best-first. Order matters; only the first ``k`` are inspected.
    expected:
        Acceptable work IDs for this query (from ``GoldenItem.expected_works``).
        Membership is by string equality — case-sensitive.
    k:
        Cut-off depth. Must be ``>= 1``. If the list is shorter than ``k``,
        the function inspects what is there (no padding).

    Returns
    -------
    ``1`` if at least one of the first ``k`` retrieved IDs is in
    ``expected``, else ``0``. Returning an int (not a bool) so callers
    can ``sum`` and divide without casting.
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    expected_set = set(expected)
    if not expected_set:
        raise ValueError("expected must be non-empty")
    for hit in retrieved_works[:k]:
        if hit in expected_set:
            return 1
    return 0


def reciprocal_rank(retrieved_works: Sequence[str], expected: Iterable[str]) -> float:
    """Return ``1 / rank`` of the first expected hit, or ``0.0`` if none.

    Ranks are 1-based — top result is rank 1 → score 1.0; rank 2 → 0.5;
    rank 3 → 0.333; etc. The whole ``retrieved_works`` list is scanned
    (no implicit top-K cut). Pair with :func:`mean_reciprocal_rank` for
    the standard MRR.

    The reciprocal-rank formulation is preferred over "average rank"
    because it heavily penalises documents found only deep in the list:
    moving an answer from rank 1 → 2 costs 0.5; from 19 → 20 costs only
    0.003. That matches user perception — top results matter most.
    """
    expected_set = set(expected)
    if not expected_set:
        raise ValueError("expected must be non-empty")
    for idx, hit in enumerate(retrieved_works, start=1):
        if hit in expected_set:
            return 1.0 / idx
    return 0.0


def mean_reciprocal_rank(per_query_rr: Iterable[float]) -> float:
    """Mean of per-query reciprocal ranks.

    Returns ``0.0`` for an empty input — matches the convention that
    a non-existent eval has zero quality, rather than raising. Caller
    should guard against this if "no items" should be a hard error.
    """
    values = list(per_query_rr)
    if not values:
        return 0.0
    return sum(values) / len(values)


__all__ = [
    "mean_reciprocal_rank",
    "ref_hit_at_k",
    "reciprocal_rank",
]
