"""Unit tests for :mod:`src.expand.foundational` (rag-day-28)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from src.expand.foundational import (
    FoundationalEntry,
    FoundationalMatcher,
    load_foundational_matcher,
)
from src.retrieval.schemas import HybridHit


def _make_hit(work_id: str, *, rrf_score: float = 0.05) -> HybridHit:
    return HybridHit(
        chunk_id=uuid4(),
        work_canonical_id=work_id,
        segment_id=f"{work_id}:1.0",
        parent_chunk_id=None,
        is_parent=True,
        text=f"sample text for {work_id}",
        rrf_score=rrf_score,
        per_channel_rank={"dense": 1, "sparse": None, "bm25": None},
    )


def _build_minimal_matcher() -> FoundationalMatcher:
    """Hand-rolled tiny matcher covering term/alias edge cases."""
    entries = [
        FoundationalEntry(
            term="four noble truths",
            aliases=("dukkha", "дуккха", "first sermon"),
            works=("sn56.11",),
            boost=1.5,
        ),
        FoundationalEntry(
            term="satipaṭṭhāna",
            aliases=("satipatthana", "сатипаттхана", "mindfulness foundations"),
            works=("mn10", "dn22"),
            boost=1.5,
        ),
        FoundationalEntry(
            term="metta",
            aliases=("mettā", "loving-kindness", "метта"),
            works=("snp1.8",),
            boost=1.4,
        ),
    ]
    return FoundationalMatcher(entries, default_boost=1.5)


class TestMatcherMatch:
    def test_term_direct_match(self) -> None:
        matcher = _build_minimal_matcher()
        result = matcher.match("What is satipaṭṭhāna?")
        assert "mn10" in result.boost_by_work
        assert "dn22" in result.boost_by_work
        assert result.boost_by_work["mn10"] == 1.5

    def test_alias_match(self) -> None:
        matcher = _build_minimal_matcher()
        result = matcher.match("explain dukkha")
        assert result.boost_by_work == {"sn56.11": 1.5}

    def test_cyrillic_alias_match(self) -> None:
        matcher = _build_minimal_matcher()
        result = matcher.match("что такое метта?")
        assert result.boost_by_work == {"snp1.8": 1.4}

    def test_case_insensitive_match(self) -> None:
        matcher = _build_minimal_matcher()
        result = matcher.match("LOVING-KINDNESS practice")
        assert result.boost_by_work == {"snp1.8": 1.4}

    def test_no_match(self) -> None:
        matcher = _build_minimal_matcher()
        result = matcher.match("How do I work with anger?")
        assert result.boost_by_work == {}
        assert result.matched_entries == ()

    def test_no_partial_word_match(self) -> None:
        # "dukkha" should not match inside "dukkhavilasa" (made-up).
        # Word-boundary regex protects us.
        matcher = _build_minimal_matcher()
        result = matcher.match("Practising dukkhavilasagamana every day")
        assert result.boost_by_work == {}

    def test_overlapping_entries_max_boost_wins(self) -> None:
        # Construct a query that hits two entries pointing to the same
        # work to verify max-boost wins.
        entries = [
            FoundationalEntry(
                term="anatta",
                aliases=("non-self",),
                works=("sn22.59",),
                boost=1.4,
            ),
            FoundationalEntry(
                term="not-self",
                aliases=(),
                works=("sn22.59",),
                boost=1.6,
            ),
        ]
        matcher = FoundationalMatcher(entries, default_boost=1.5)
        result = matcher.match("anatta and not-self in early buddhism")
        assert result.boost_by_work["sn22.59"] == 1.6


class TestApplyBoost:
    def test_boost_applied_and_resorted(self) -> None:
        matcher = _build_minimal_matcher()
        hits = [
            _make_hit("mn9", rrf_score=0.045),
            _make_hit("sn35.226", rrf_score=0.038),
            _make_hit("sn56.11", rrf_score=0.025),  # foundational, lower rank
        ]
        boosted = matcher.apply_boost(hits, "What is dukkha?")
        # sn56.11 lifted to top: 0.025 * 1.5 = 0.0375 > 0.045? No — 0.0375 < 0.045
        # Actually mn9 (0.045) still wins. Boost is moderate, not absolute.
        # Check that sn56.11 was boosted, not necessarily that it ranks #1.
        assert boosted[2].work_canonical_id == "sn56.11"
        assert boosted[2].rrf_score == pytest.approx(0.025 * 1.5)
        # Boost is large enough to lift past sn35.226 (0.038 vs 0.0375 — close).
        # Verify ordering reflects actual scores.
        scores = [h.rrf_score for h in boosted]
        assert scores == sorted(scores, reverse=True)

    def test_strong_boost_promotes_to_top(self) -> None:
        # When boost moves the score above all others, ordering changes.
        matcher = _build_minimal_matcher()
        hits = [
            _make_hit("mn9", rrf_score=0.030),
            _make_hit("mn10", rrf_score=0.025),  # foundational for satipatthana
        ]
        boosted = matcher.apply_boost(hits, "What is satipaṭṭhāna?")
        assert boosted[0].work_canonical_id == "mn10"
        assert boosted[0].rrf_score == pytest.approx(0.025 * 1.5)

    def test_no_match_returns_input(self) -> None:
        matcher = _build_minimal_matcher()
        hits = [_make_hit("mn9", rrf_score=0.045)]
        out = matcher.apply_boost(hits, "How do I work with anger?")
        # Identical reference — no allocation when nothing matched.
        assert out is hits

    def test_empty_hits(self) -> None:
        matcher = _build_minimal_matcher()
        assert matcher.apply_boost([], "What is dukkha?") == []


class TestLoadFoundationalMatcher:
    def test_real_yaml_loads(self) -> None:
        # Sanity: shipped foundational.yaml parses and has at least
        # the 12 Sahaya essentials + 6 supplementary entries.
        matcher = load_foundational_matcher()
        assert len(matcher.entries) >= 18

    def test_real_yaml_has_satipatthana(self) -> None:
        matcher = load_foundational_matcher()
        result = matcher.match("What is satipaṭṭhāna?")
        # mn10 and dn22 are the canonical first-sources per Sahaya.
        assert "mn10" in result.boost_by_work
        assert "dn22" in result.boost_by_work

    def test_real_yaml_has_dukkha(self) -> None:
        matcher = load_foundational_matcher()
        result = matcher.match("What is dukkha?")
        assert "sn56.11" in result.boost_by_work

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_foundational_matcher(tmp_path / "nonexistent.yaml")

    def test_invalid_root_type_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("just_a_string\n", encoding="utf-8")
        with pytest.raises(ValueError, match="must be a list"):
            load_foundational_matcher(path)

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("- term: foo\n", encoding="utf-8")  # no `works`
        with pytest.raises(ValueError, match="missing required field"):
            load_foundational_matcher(path)

    def test_empty_works_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("- {term: foo, works: []}\n", encoding="utf-8")
        with pytest.raises(ValueError, match="non-empty"):
            load_foundational_matcher(path)
