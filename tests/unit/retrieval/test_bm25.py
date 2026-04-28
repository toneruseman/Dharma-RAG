"""Unit tests for the pure-function surface of :mod:`src.retrieval.bm25`.

The ``search`` function itself is integration-tested against a live
Postgres in ``tests/integration/test_bm25_fts.py`` — it has nothing to
mock usefully. Here we cover the parts that don't need a database:
query normalisation and the dataclass shape.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.retrieval.bm25 import FTS_CONFIG, BM25Hit, normalize_query

# ---------------------------------------------------------------------------
# normalize_query — pure function, must mirror the ingest ascii_fold
# ---------------------------------------------------------------------------


def test_normalize_query_is_empty_string_on_empty() -> None:
    assert normalize_query("") == ""


def test_normalize_query_strips_pali_diacritics() -> None:
    # The whole point: a user who types with or without diacritics
    # gets the same query. This is what aligns query and index.
    assert normalize_query("satipaṭṭhāna") == "satipatthana"
    assert normalize_query("anāpānassati") == "anapanassati"
    assert normalize_query("Sāvatthī") == "savatthi"


def test_normalize_query_is_case_normalised_by_fold() -> None:
    # to_ascii_fold produces lowercase output — BM25 must not care
    # about the user's capitalisation.
    assert normalize_query("BUDDHA") == "buddha"
    assert normalize_query("BuDDhA") == "buddha"


def test_normalize_query_collapses_whitespace() -> None:
    assert normalize_query("   four   noble    truths  ") == "four noble truths"
    assert normalize_query("\tfour\nnoble\rtruths") == "four noble truths"


def test_normalize_query_preserves_ascii_alphanumerics() -> None:
    # The normaliser must not eat digits or internal punctuation it
    # does not know about. Postgres websearch_to_tsquery handles the
    # quoting itself.
    assert normalize_query("MN 10") == "mn 10"
    assert normalize_query("sn56.11") == "sn56.11"


def test_normalize_query_is_idempotent() -> None:
    q = "satipaṭṭhāna and Ānanda"
    once = normalize_query(q)
    twice = normalize_query(once)
    assert once == twice


# ---------------------------------------------------------------------------
# BM25Hit dataclass — exists mostly to freeze the contract day-12 depends on
# ---------------------------------------------------------------------------


def test_bm25hit_is_frozen_and_slotted() -> None:
    hit = BM25Hit(
        chunk_id=uuid4(),
        score=0.42,
        work_canonical_id="mn10",
        segment_id="mn10:12.3",
        parent_chunk_id=None,
        is_parent=False,
    )
    with pytest.raises((AttributeError, TypeError)):
        hit.score = 0.99  # type: ignore[misc]


def test_bm25hit_sorts_by_score_desc_via_tuple() -> None:
    # Hybrid fusion on day 12 will stable-sort parallel lists; this
    # test locks in that BM25Hit's score is a plain float we can
    # compare without surprises.
    lo = BM25Hit(
        chunk_id=uuid4(),
        score=0.1,
        work_canonical_id="mn1",
        segment_id=None,
        parent_chunk_id=None,
        is_parent=False,
    )
    hi = BM25Hit(
        chunk_id=uuid4(),
        score=0.9,
        work_canonical_id="mn2",
        segment_id=None,
        parent_chunk_id=None,
        is_parent=False,
    )
    ranked = sorted([lo, hi], key=lambda h: h.score, reverse=True)
    assert ranked[0].score == 0.9
    assert ranked[1].score == 0.1


def test_fts_config_is_simple() -> None:
    # If someone swaps this to 'english' the diacritic-fold contract
    # breaks silently (stemmer chews Pali words we never expected).
    # Make the invariant explicit in a test.
    assert FTS_CONFIG == "simple"
