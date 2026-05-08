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
            aliases=("dukkha", "дуккха", "suffering", "first sermon"),
            works=("sn56.11",),
            boost=1.5,
        ),
        FoundationalEntry(
            term="anatta",
            aliases=("анатта", "non-self", "not-self"),
            works=("sn22.59",),
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


class TestBM25Aliases:
    def test_dukkha_returns_suffering(self) -> None:
        # Sujato translates `dukkha` to `suffering` in body text.
        # bm25_aliases must surface English aliases for BM25 channel.
        matcher = _build_minimal_matcher()
        aliases = matcher.bm25_aliases("What is dukkha?")
        assert "suffering" in aliases

    def test_anatta_returns_not_self(self) -> None:
        matcher = _build_minimal_matcher()
        aliases = matcher.bm25_aliases("What is anatta?")
        assert "not-self" in aliases or "non-self" in aliases

    def test_metta_returns_loving_kindness(self) -> None:
        matcher = _build_minimal_matcher()
        aliases = matcher.bm25_aliases("Что такое метта?")
        assert "loving-kindness" in aliases

    def test_no_match_returns_empty(self) -> None:
        matcher = _build_minimal_matcher()
        assert matcher.bm25_aliases("How do I work with anger?") == []

    def test_skips_pali_script_variants(self) -> None:
        # `satipatthana` is just an ASCII spelling of `satipaṭṭhāna` —
        # FTS already handles that via to_ascii_fold. We want
        # English descriptive aliases only.
        matcher = _build_minimal_matcher()
        aliases = matcher.bm25_aliases("What is satipaṭṭhāna?")
        assert "satipatthana" not in aliases
        assert "mindfulness foundations" in aliases

    def test_skips_cyrillic(self) -> None:
        # Cyrillic aliases never go to FTS (config is English).
        matcher = _build_minimal_matcher()
        aliases = matcher.bm25_aliases("What is satipaṭṭhāna?")
        assert all(not any("\u0400" <= ch <= "\u04ff" for ch in a) for a in aliases)

    def test_caps_at_three(self) -> None:
        # Bound query length so BM25 doesn't choke on long OR-chains.
        from src.expand.foundational import FoundationalEntry, FoundationalMatcher

        entry = FoundationalEntry(
            term="x",
            aliases=("alpha one", "beta two", "gamma three", "delta four", "epsilon five"),
            works=("w1",),
            boost=1.5,
        )
        matcher = FoundationalMatcher([entry], default_boost=1.5)
        aliases = matcher.bm25_aliases("x is interesting")
        assert len(aliases) <= 3


class TestApplyBoost:
    def test_floor_to_top_promotes_low_ranked_foundational(self) -> None:
        # Floor-to-top semantics (rag-day-29): foundational works only
        # in BM25 channel get rrf_score ~0.015 vs top ~0.045 — pure
        # multiplication is insufficient. Floor at top_original * boost
        # guarantees they appear near top.
        matcher = _build_minimal_matcher()
        hits = [
            _make_hit("mn9", rrf_score=0.045),
            _make_hit("sn35.226", rrf_score=0.038),
            _make_hit("sn56.11", rrf_score=0.025),  # foundational, low
        ]
        boosted = matcher.apply_boost(hits, "What is dukkha?")
        # sn56.11 floored to 0.045 * 1.5 = 0.0675 → ranks #1
        assert boosted[0].work_canonical_id == "sn56.11"
        assert boosted[0].rrf_score == pytest.approx(0.045 * 1.5)
        # Non-foundational works keep original scores, ordered organically
        assert boosted[1].work_canonical_id == "mn9"
        assert boosted[1].rrf_score == pytest.approx(0.045)
        assert boosted[2].work_canonical_id == "sn35.226"
        assert boosted[2].rrf_score == pytest.approx(0.038)

    def test_floor_does_not_demote_high_competitive_foundational(self) -> None:
        # When foundational score from multiplicative boost already
        # exceeds the floor, multiplicative wins (don't demote).
        matcher = _build_minimal_matcher()
        hits = [
            _make_hit("mn9", rrf_score=0.030),
            _make_hit("mn10", rrf_score=0.040),  # foundational, already high
        ]
        boosted = matcher.apply_boost(hits, "What is satipaṭṭhāna?")
        # mn10 multiplicative: 0.040 * 1.5 = 0.060
        # mn10 floor:          0.040 * 1.5 = 0.060 (same)
        # max = 0.060 → mn10 #1
        assert boosted[0].work_canonical_id == "mn10"
        assert boosted[0].rrf_score == pytest.approx(0.060)

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
        # 12 Sahaya essentials + 6 supplementary + 5 rag-day-30
        # Russian-foundational + 1 rag-day-32 right-effort split-out
        # + 3 rag-day-35 English-title (fire sermon / chariot / samatha-yanika).
        matcher = load_foundational_matcher()
        assert len(matcher.entries) >= 27

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

    def test_real_yaml_russian_samadhi(self) -> None:
        # rag-day-30: Russian definitional query for samādhi must
        # surface AN 4.41 (Samādhibhāvanā Sutta).
        matcher = load_foundational_matcher()
        result = matcher.match("Что такое самадхи?")
        assert "an4.41" in result.boost_by_work

    def test_real_yaml_russian_bojjhanga(self) -> None:
        # rag-day-30: «факторы пробуждения» → SN 46.3.
        matcher = load_foundational_matcher()
        result = matcher.match("Что такое факторы пробуждения?")
        assert "sn46.3" in result.boost_by_work

    def test_real_yaml_russian_three_refuges(self) -> None:
        # rag-day-30: «три прибежища» → AN 6.10 (Mahānāma Sutta).
        matcher = load_foundational_matcher()
        result = matcher.match("Что такое три прибежища?")
        assert "an6.10" in result.boost_by_work

    def test_real_yaml_russian_brahmavihara(self) -> None:
        # rag-day-30: «брахмавихара» → DN 13 (Tevijja).
        matcher = load_foundational_matcher()
        result = matcher.match("Что такое брахмавихара?")
        assert "dn13" in result.boost_by_work

    def test_real_yaml_dependent_origination_extended(self) -> None:
        # rag-day-30: extended `dependent origination` aliases must
        # match the new Russian phrases without breaking the canonical
        # work pointer.
        matcher = load_foundational_matcher()
        result = matcher.match("что такое 12 нидан?")
        assert "sn12.2" in result.boost_by_work

    def test_real_yaml_lay_ethics_sila_alias(self) -> None:
        # rag-day-30: extended `lay ethics` covers «нравственность» / sīla.
        matcher = load_foundational_matcher()
        result = matcher.match("Что такое нравственность?")
        assert "dn31" in result.boost_by_work

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
