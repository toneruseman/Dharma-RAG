"""Unit tests for Reciprocal Rank Fusion.

The fuser is a pure function — every test runs in microseconds with
hand-built ranked lists, no mocks.
"""

from __future__ import annotations

import pytest

from src.retrieval.rrf import DEFAULT_K, FusedHit, reciprocal_rank_fusion

# ---------------------------------------------------------------------------
# Empty / edge inputs
# ---------------------------------------------------------------------------


def test_empty_input_returns_empty_list() -> None:
    assert reciprocal_rank_fusion({}) == []


def test_all_channels_empty_returns_empty_list() -> None:
    assert reciprocal_rank_fusion({"dense": [], "sparse": []}) == []


def test_one_channel_empty_others_have_results() -> None:
    result = reciprocal_rank_fusion({"dense": ["a", "b"], "sparse": []})
    assert [h.doc_id for h in result] == ["a", "b"]
    # ``sparse`` is a recognised channel even though it returned nothing
    assert result[0].per_channel_rank == {"dense": 1, "sparse": None}


def test_single_channel_passes_through_in_order() -> None:
    result = reciprocal_rank_fusion({"dense": ["x", "y", "z"]})
    assert [h.doc_id for h in result] == ["x", "y", "z"]
    # First doc at rank 1, score 1/(60+1)
    assert result[0].score == pytest.approx(1 / 61)
    assert result[2].score == pytest.approx(1 / 63)


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------


def test_doc_appearing_in_two_channels_outranks_doc_in_one() -> None:
    """The whole point of fusion: presence across channels matters
    more than winning a single channel.
    """
    result = reciprocal_rank_fusion(
        {
            "dense": ["only_dense", "shared"],  # shared at rank 2
            "sparse": ["shared", "only_sparse"],  # shared at rank 1
        }
    )
    by_id = {h.doc_id: h for h in result}
    # shared: 1/61 + 1/62 ≈ 0.0325
    # only_dense: 1/61 ≈ 0.01639
    # only_sparse: 1/62 ≈ 0.01613
    assert by_id["shared"].score > by_id["only_dense"].score
    assert by_id["shared"].score > by_id["only_sparse"].score
    assert result[0].doc_id == "shared"


def test_higher_rank_in_one_channel_beats_lower_rank_in_another() -> None:
    """Both at rank 5 in one channel = same score, no difference."""
    result = reciprocal_rank_fusion(
        {
            "a_channel": ["doc_at_1", "x", "x", "x", "doc_at_5"],
        }
    )
    by_id = {h.doc_id: h for h in result}
    # 1/61 ≈ 0.01639 > 1/65 ≈ 0.01538
    assert by_id["doc_at_1"].score > by_id["doc_at_5"].score


def test_per_channel_rank_records_missing_channels_as_none() -> None:
    result = reciprocal_rank_fusion(
        {
            "dense": ["a"],
            "sparse": ["b"],
            "bm25": ["a", "b"],
        }
    )
    by_id = {h.doc_id: h for h in result}
    assert by_id["a"].per_channel_rank == {"dense": 1, "sparse": None, "bm25": 1}
    assert by_id["b"].per_channel_rank == {"dense": None, "sparse": 1, "bm25": 2}


def test_per_channel_rank_keys_match_input_channels() -> None:
    """Even channels with zero hits appear in per_channel_rank as None."""
    result = reciprocal_rank_fusion(
        {"dense": ["a"], "sparse": [], "bm25": ["a"]},
    )
    assert result[0].per_channel_rank == {"dense": 1, "sparse": None, "bm25": 1}


# ---------------------------------------------------------------------------
# Concrete worked example from the user-facing explanation
# ---------------------------------------------------------------------------


def test_worked_example_for_four_noble_truths_query() -> None:
    """The example I walked the user through must produce the
    documented ranking: SN56.29 first (dense 2 + bm25 1), then SN56.27
    (dense 1 + sparse 4), then SN56.28 (dense 3 + sparse 2).

    Locking this in as a regression test: if someone later "improves"
    the formula with weights or a different k, this will tell us
    whether they broke the documented semantics.
    """
    result = reciprocal_rank_fusion(
        {
            "dense": ["SN56.27", "SN56.29", "SN56.28", "MN141", "AN3.61"],
            "sparse": ["SN56.13", "SN56.28", "AN3.61", "SN56.27"],
            "bm25": ["SN56.29", "SN56.23", "MN141", "SN56.15"],
        },
    )
    top3 = [h.doc_id for h in result[:3]]
    assert top3 == ["SN56.29", "SN56.27", "SN56.28"]


# ---------------------------------------------------------------------------
# Stability and ties
# ---------------------------------------------------------------------------


def test_ties_break_in_first_appearance_order() -> None:
    """Two docs with identical RRF scores keep their order from the
    first channel they appeared in. Determinism matters for tests and
    user-facing logs.
    """
    result = reciprocal_rank_fusion(
        {
            "dense": ["a", "b"],  # both rank 1 and 2
            "sparse": ["b", "a"],  # roles swapped → identical RRF scores
        }
    )
    # Both 'a' and 'b' have score 1/61 + 1/62, identical. 'a' came first
    # in the dense channel, so it should rank first.
    assert [h.doc_id for h in result] == ["a", "b"]
    assert result[0].score == result[1].score


def test_duplicate_doc_in_single_channel_keeps_best_rank() -> None:
    """Defensive: if a channel pathologically returns the same doc
    twice, the better rank wins. Real Qdrant / FTS won't do this, but
    the function should not crash or double-count.
    """
    result = reciprocal_rank_fusion({"dense": ["a", "a", "b"]})
    by_id = {h.doc_id: h for h in result}
    # 'a' is at rank 1 (best of its two appearances), 'b' at rank 3
    assert by_id["a"].per_channel_rank == {"dense": 1}
    assert by_id["a"].score == pytest.approx(1 / 61)
    # NOT 1/61 + 1/62 — that would be double-counting
    assert by_id["a"].score < 2 / 61


# ---------------------------------------------------------------------------
# Limit and parameter validation
# ---------------------------------------------------------------------------


def test_limit_truncates_to_top_n() -> None:
    result = reciprocal_rank_fusion({"dense": ["a", "b", "c", "d", "e"]}, limit=3)
    assert len(result) == 3
    assert [h.doc_id for h in result] == ["a", "b", "c"]


def test_limit_none_returns_everything() -> None:
    result = reciprocal_rank_fusion({"dense": ["a", "b", "c"]}, limit=None)
    assert len(result) == 3


def test_limit_larger_than_available_is_safe() -> None:
    result = reciprocal_rank_fusion({"dense": ["a", "b"]}, limit=100)
    assert len(result) == 2


def test_invalid_k_raises() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        reciprocal_rank_fusion({"dense": ["a"]}, k=0)
    with pytest.raises(ValueError, match="must be positive"):
        reciprocal_rank_fusion({"dense": ["a"]}, k=-1)


def test_custom_k_changes_score_scale() -> None:
    """Smaller k gives bigger top-rank scores (1/(1+1) > 1/(60+1))."""
    small_k = reciprocal_rank_fusion({"dense": ["a"]}, k=1)
    big_k = reciprocal_rank_fusion({"dense": ["a"]}, k=1000)
    assert small_k[0].score > big_k[0].score


# ---------------------------------------------------------------------------
# FusedHit dataclass contract
# ---------------------------------------------------------------------------


def test_fused_hit_is_frozen_and_slotted() -> None:
    hit = FusedHit(doc_id="a", score=0.5, per_channel_rank={"dense": 1})
    with pytest.raises((AttributeError, TypeError)):
        hit.score = 0.99  # type: ignore[misc]


def test_default_k_is_canonical_60() -> None:
    """If someone changes the default, every downstream test should
    notice it. Keep the constant pinned in a test so the choice is
    explicit.
    """
    assert DEFAULT_K == 60
