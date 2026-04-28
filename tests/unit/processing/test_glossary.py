"""Unit tests for :mod:`src.processing.glossary`.

Tests run against a minimal in-memory glossary (not the full 50k-lemma
DPD dump) so they're fast and deterministic. The full glossary's smoke
behaviour is sanity-checked via integration in
``tests/unit/rag/test_service.py`` (which mocks the encoder layer
entirely)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from src.processing.glossary import (
    Glossary,
    GlossaryEntry,
    _strip_diacritics,
    _tokenize,
    load_glossary,
)

# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _build_minimal_glossary() -> Glossary:
    """Hand-rolled tiny glossary covering the cases tests exercise.

    Includes both diacritic-rich Pāli forms (``jhāna``, ``paṭicca``)
    and a deliberately ASCII-only Pāli lemma (``dukkha``) so the
    diacritic-guard heuristic gets exercised in both directions.
    """
    dpd: dict[str, GlossaryEntry] = {
        "jhāna": GlossaryEntry(
            pali="jhāna",
            pos=("nt",),
            meanings_en=("meditative absorption", "meditation"),
            meanings_ru=("медитативное погружение", "медитация"),
        ),
        "paṭicca": GlossaryEntry(
            pali="paṭicca",
            pos=("nt",),
            meanings_en=("dependent", "conditioned"),
            meanings_ru=("зависимый", "обусловленный"),
        ),
        "dukkha": GlossaryEntry(
            pali="dukkha",
            pos=("nt",),
            meanings_en=("suffering", "stress"),
            meanings_ru=("страдание", "неудовлетворённость"),
        ),
        "kamma": GlossaryEntry(
            pali="kamma",
            pos=("nt",),
            meanings_en=("action", "deed"),
            meanings_ru=("действие", "поступок"),
        ),
    }
    cyrillic_to_pali: dict[str, str] = {
        "джхана": "jhāna",
        "дхьяна": "jhāna",
        "дуккха": "dukkha",
        "карма": "kamma",
        "ступа": "thūpa",  # intentionally NOT in DPD — cyrillic-only resolution
    }
    return Glossary(dpd=dpd, cyrillic_to_pali=cyrillic_to_pali)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestStripDiacritics:
    def test_pali_diacritics_removed(self) -> None:
        assert _strip_diacritics("jhāna") == "jhana"
        assert _strip_diacritics("paṭiccasamuppāda") == "paticcasamuppada"
        # Macrons, dots, tilde all classed as Mn (non-spacing mark).
        assert _strip_diacritics("ṅkāra") == "nkara"

    def test_cyrillic_untouched(self) -> None:
        # Russian letters aren't decomposed in NFD with combining marks
        # for normal usage, so this is identity. The point is the
        # function shouldn't accidentally strip cyrillic.
        assert _strip_diacritics("джхана") == "джхана"


class TestTokenize:
    def test_basic_split(self) -> None:
        assert _tokenize("what is dukkha?") == ["what", "is", "dukkha"]

    def test_lowercases(self) -> None:
        assert _tokenize("DUKKHA") == ["dukkha"]

    def test_keeps_unicode(self) -> None:
        assert _tokenize("что такое джхана?") == ["что", "такое", "джхана"]
        assert _tokenize("paṭiccasamuppāda") == ["paṭiccasamuppāda"]

    def test_keeps_hyphenated_compounds(self) -> None:
        # Used by cyrillic.yaml ("благородная-истина").
        assert _tokenize("благородная-истина") == ["благородная-истина"]

    def test_drops_punctuation_and_numbers(self) -> None:
        assert _tokenize("foo, 42 bar!") == ["foo", "bar"]

    def test_empty_input(self) -> None:
        assert _tokenize("") == []
        assert _tokenize("   ") == []


# ---------------------------------------------------------------------------
# Glossary.expand_query
# ---------------------------------------------------------------------------


class TestExpandQuery:
    def test_empty_query_returns_empty(self) -> None:
        g = _build_minimal_glossary()
        assert g.expand_query("") == ""

    def test_no_matches_returns_unchanged(self) -> None:
        g = _build_minimal_glossary()
        q = "this query has no buddhist terms in it"
        assert g.expand_query(q) == q

    def test_pali_with_diacritics_adds_meanings(self) -> None:
        g = _build_minimal_glossary()
        out = g.expand_query("paṭicca")
        assert out.startswith("paṭicca ")
        # Default ``max_meanings=1`` post day-23 tuning: only top-1 EN
        # + top-1 RU per recognised term (the second-rank synonyms
        # diluted queries on targeted eval).
        assert "dependent" in out
        assert "зависимый" in out

    def test_pali_with_diacritics_adds_more_with_max_meanings_2(self) -> None:
        """Explicit ``max_meanings=2`` recovers the wider expansion that
        used to be the default before day-23 tuning."""
        g = _build_minimal_glossary()
        out = g.expand_query("paṭicca", max_meanings=2)
        assert "dependent" in out
        assert "conditioned" in out
        assert "зависимый" in out
        assert "обусловленный" in out

    def test_pure_ascii_pali_is_skipped(self) -> None:
        """Day-23 mini-eval finding: expanding ASCII tokens like
        ``dukkha`` / ``buddha`` adds noise on English queries (the
        encoder already understands them in the Buddhist context).

        The diacritic guard skips them; users who want the expansion
        can type with diacritics (``dukkha`` → ``ḍukkha`` won't make
        sense, but ``jhāna`` → diacritic form does) or in cyrillic
        (``дуккха``)."""
        g = _build_minimal_glossary()
        out = g.expand_query("dukkha")
        # No expansion — pure ASCII even though dukkha IS in DPD.
        assert out == "dukkha"

    def test_pali_without_diacritics_is_skipped(self) -> None:
        """``jhana`` (no diacritic) doesn't expand even though stripping
        the diacritics from DPD's ``jhāna`` would match it. Same
        rationale as ``test_pure_ascii_pali_is_skipped``: the heuristic
        only fires when the user signals they're using transliterated
        Pāli (diacritics) or cyrillic."""
        g = _build_minimal_glossary()
        out = g.expand_query("jhana")
        assert out == "jhana"

    def test_cyrillic_resolves_to_pali_and_meanings(self) -> None:
        g = _build_minimal_glossary()
        out = g.expand_query("что такое джхана?")
        assert "jhāna" in out
        # Default max_meanings=1: top-1 EN + top-1 RU only.
        assert "meditative absorption" in out
        assert "медитативное погружение" in out
        # Original query preserved verbatim at the start.
        assert out.startswith("что такое джхана?")

    def test_cyrillic_without_dpd_entry_still_adds_pali(self) -> None:
        """``ступа`` maps to a Pāli lemma the DPD fixture doesn't have —
        the Pāli form alone should still be appended so the encoder
        gets *something* extra."""
        g = _build_minimal_glossary()
        out = g.expand_query("ступа сегодня закрыта")
        assert "thūpa" in out
        # No EN/RU meanings since DPD didn't carry it.
        # (We don't pin specific tokens — just check no exception
        # and Pāli form is there.)

    def test_dedup_against_original_tokens(self) -> None:
        """If the query already contains a meaning, don't duplicate it."""
        g = _build_minimal_glossary()
        out = g.expand_query("paṭicca and dependent things")
        # "dependent" was in the query, so it shouldn't be re-added.
        assert out.count("dependent") == 1

    def test_max_terms_caps_expansion(self) -> None:
        """Three Pāli (diacritic-bearing) terms; cap at 1 → one expanded."""
        g = _build_minimal_glossary()
        out = g.expand_query("jhāna paṭicca карма", max_terms=1)
        # Exactly one of the three should have meanings appended.
        markers = sum(1 for m in ["meditative absorption", "dependent", "action"] if m in out)
        assert markers == 1

    def test_max_meanings_caps_per_term(self) -> None:
        g = _build_minimal_glossary()
        # paṭicca has 2 EN + 2 RU; max_meanings=0 keeps only the lemma.
        out = g.expand_query("paṭicca", max_meanings=0)
        assert "paṭicca" in out
        assert "dependent" not in out
        assert "conditioned" not in out
        assert "зависимый" not in out
        assert "обусловленный" not in out

    def test_query_appears_unchanged_at_start(self) -> None:
        g = _build_minimal_glossary()
        q = "что такое карма? please explain"
        out = g.expand_query(q)
        assert out.startswith(q)

    def test_english_word_coinciding_with_pali_lemma_is_skipped(self) -> None:
        """``dukkha`` happens to match a DPD lemma but it's also a
        widely-borrowed English Buddhist term — the encoder handles it
        already. Expanding it adds noise (`uncomfortable`, `неприятный`)
        that drags retrieval off-topic. Day-23 mini-eval found this on
        ``Buddha``/``sutta``/``kamma`` etc."""
        g = _build_minimal_glossary()
        # English query mentioning Pali borrowings should be untouched.
        q = "what does kamma have to do with dukkha and karma"
        assert g.expand_query(q) == q


# ---------------------------------------------------------------------------
# load_glossary — file IO behaviour
# ---------------------------------------------------------------------------


class TestLoadGlossary:
    def test_missing_dpd_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_glossary(
                dpd_path=tmp_path / "missing.json",
                cyrillic_path=tmp_path / "also_missing.yaml",
            )

    def test_loads_from_files(self, tmp_path: Path) -> None:
        dpd_payload = {
            "jhāna": {
                "lemma": "jhāna",
                "pos": ["nt"],
                "meanings_en": ["meditation"],
                "meanings_ru": ["медитация"],
            },
        }
        cyr_payload = [
            {"pali": "jhāna", "cyrillic": ["джхана"]},
        ]
        dpd_path = tmp_path / "dpd.json"
        cyr_path = tmp_path / "cyr.yaml"
        dpd_path.write_text(json.dumps(dpd_payload, ensure_ascii=False), encoding="utf-8")
        cyr_path.write_text(yaml.safe_dump(cyr_payload, allow_unicode=True), encoding="utf-8")

        g = load_glossary(dpd_path=dpd_path, cyrillic_path=cyr_path)

        assert g.size == {"dpd_lemmas": 1, "cyrillic_variants": 1}
        out = g.expand_query("джхана")
        assert "jhāna" in out
        assert "медитация" in out

    def test_cyrillic_collision_keeps_first(self, tmp_path: Path) -> None:
        """When two Pāli entries share the same cyrillic variant, we
        keep the first and warn (rather than silently overwrite)."""
        dpd_payload = {
            "sīla": {
                "lemma": "sīla",
                "pos": [],
                "meanings_en": ["virtue"],
                "meanings_ru": [],
            },
            "bala": {
                "lemma": "bala",
                "pos": [],
                "meanings_en": ["power"],
                "meanings_ru": [],
            },
        }
        cyr_payload = [
            {"pali": "sīla", "cyrillic": ["сила"]},
            {"pali": "bala", "cyrillic": ["сила"]},  # collides
        ]
        dpd_path = tmp_path / "dpd.json"
        cyr_path = tmp_path / "cyr.yaml"
        dpd_path.write_text(json.dumps(dpd_payload, ensure_ascii=False), encoding="utf-8")
        cyr_path.write_text(yaml.safe_dump(cyr_payload, allow_unicode=True), encoding="utf-8")

        g = load_glossary(dpd_path=dpd_path, cyrillic_path=cyr_path)
        # First-listed lemma wins (sīla).
        out = g.expand_query("сила")
        assert "sīla" in out
        assert "virtue" in out
        assert "bala" not in out
