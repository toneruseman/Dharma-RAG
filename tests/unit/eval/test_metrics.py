"""Unit tests for the pure metric functions in :mod:`src.eval.metrics`.

The eval runner depends on these formulas being right; a silent off-by-
one would skew every reported number forever after. Tests use trivial
hand-built lists so the expected outputs are obvious.
"""

from __future__ import annotations

import math

import pytest

from src.eval.metrics import (
    mean_reciprocal_rank,
    reciprocal_rank,
    ref_hit_at_k,
)

# ---------------------------------------------------------------------------
# ref_hit_at_k
# ---------------------------------------------------------------------------


def test_ref_hit_at_k_hit_at_first_position() -> None:
    assert ref_hit_at_k(["mn118", "sn56.11"], {"mn118"}, k=1) == 1


def test_ref_hit_at_k_hit_within_window() -> None:
    assert ref_hit_at_k(["a", "b", "c", "mn118", "d"], {"mn118"}, k=5) == 1


def test_ref_hit_at_k_miss_outside_window() -> None:
    """Hit at rank 6 must not count when k=5."""
    retrieved = ["a", "b", "c", "d", "e", "mn118"]
    assert ref_hit_at_k(retrieved, {"mn118"}, k=5) == 0


def test_ref_hit_at_k_no_hit() -> None:
    assert ref_hit_at_k(["a", "b"], {"mn118"}, k=10) == 0


def test_ref_hit_at_k_multiple_expected_any_match() -> None:
    """If ANY expected work appears, that's a hit (set semantics)."""
    assert ref_hit_at_k(["sn56.11", "mn1"], {"mn118", "sn56.11"}, k=2) == 1


def test_ref_hit_at_k_short_list_no_padding() -> None:
    """If retrieved is shorter than k, we just inspect what we have."""
    assert ref_hit_at_k(["mn118"], {"mn118"}, k=10) == 1
    assert ref_hit_at_k(["mn1"], {"mn118"}, k=10) == 0


def test_ref_hit_at_k_empty_retrieved_returns_zero() -> None:
    assert ref_hit_at_k([], {"mn118"}, k=5) == 0


def test_ref_hit_at_k_invalid_k_raises() -> None:
    with pytest.raises(ValueError, match="k must be >= 1"):
        ref_hit_at_k(["a"], {"a"}, k=0)


def test_ref_hit_at_k_empty_expected_raises() -> None:
    """Empty expected set is a programming error — surface it."""
    with pytest.raises(ValueError, match="expected must be non-empty"):
        ref_hit_at_k(["a"], set(), k=1)


def test_ref_hit_at_k_case_sensitive() -> None:
    """``MN118`` and ``mn118`` are different IDs."""
    assert ref_hit_at_k(["MN118"], {"mn118"}, k=1) == 0


# ---------------------------------------------------------------------------
# reciprocal_rank
# ---------------------------------------------------------------------------


def test_reciprocal_rank_first_position() -> None:
    assert reciprocal_rank(["mn118", "x"], {"mn118"}) == 1.0


def test_reciprocal_rank_second_position() -> None:
    assert reciprocal_rank(["x", "mn118"], {"mn118"}) == 0.5


def test_reciprocal_rank_third_position() -> None:
    assert math.isclose(reciprocal_rank(["x", "y", "mn118"], {"mn118"}), 1 / 3)


def test_reciprocal_rank_no_hit_returns_zero() -> None:
    assert reciprocal_rank(["a", "b", "c"], {"mn118"}) == 0.0


def test_reciprocal_rank_first_match_wins() -> None:
    """If the expected ID appears twice, only the FIRST occurrence counts."""
    assert reciprocal_rank(["x", "mn118", "y", "mn118"], {"mn118"}) == 0.5


def test_reciprocal_rank_empty_retrieved_returns_zero() -> None:
    assert reciprocal_rank([], {"mn118"}) == 0.0


def test_reciprocal_rank_empty_expected_raises() -> None:
    with pytest.raises(ValueError, match="expected must be non-empty"):
        reciprocal_rank(["a"], set())


# ---------------------------------------------------------------------------
# mean_reciprocal_rank
# ---------------------------------------------------------------------------


def test_mean_reciprocal_rank_basic() -> None:
    assert mean_reciprocal_rank([1.0, 0.5, 0.0]) == pytest.approx(0.5)


def test_mean_reciprocal_rank_all_misses() -> None:
    assert mean_reciprocal_rank([0.0, 0.0, 0.0]) == 0.0


def test_mean_reciprocal_rank_all_perfect() -> None:
    assert mean_reciprocal_rank([1.0, 1.0, 1.0]) == 1.0


def test_mean_reciprocal_rank_empty_returns_zero() -> None:
    """Empty input is treated as zero, not as an error — eval over an
    empty slice (e.g. zero ``hard`` items) is meaningful by convention."""
    assert mean_reciprocal_rank([]) == 0.0


def test_mean_reciprocal_rank_accepts_iterables() -> None:
    """Generator input must work — runner builds these lazily."""
    assert mean_reciprocal_rank(x for x in [1.0, 0.0]) == 0.5
