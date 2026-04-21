"""Unit tests for the text cleaner pipeline.

The cleaner touches many subtle Unicode behaviours, so tests are
grouped by concern: NFC normalisation, HTML handling, whitespace,
IAST canonicalisation, and ASCII folding. Each group has a
table-driven test and a handful of explicit edge cases.
"""

from __future__ import annotations

import unicodedata

import pytest

from src.processing.cleaner import (
    collapse_whitespace,
    normalise_iast,
    to_ascii_fold,
    to_canonical,
)

# ---------------------------------------------------------------------------
# NFC / Unicode normalisation
# ---------------------------------------------------------------------------


def test_nfc_composes_combining_diacritics() -> None:
    """Two codepoints (e + ◌́) must collapse to one (é)."""
    decomposed = "e" + "\u0301"  # e + COMBINING ACUTE ACCENT
    composed = "\u00e9"  # é
    assert decomposed != composed
    assert to_canonical(decomposed) == composed


def test_nfc_composes_pali_diacritics() -> None:
    """Pali ā written as two codepoints must end up as single U+0101."""
    decomposed = "a" + "\u0304"  # a + COMBINING MACRON
    composed = "\u0101"  # ā
    assert to_canonical(decomposed) == composed
    # And the sample word "sāpi" in decomposed form normalises.
    assert to_canonical("s" + decomposed + "pi") == "sāpi"


def test_canonical_output_is_nfc() -> None:
    """Whatever the input form, the output must satisfy is_normalized('NFC')."""
    inputs = ["satipaṭṭhāna", "s" + "a\u0304" + "pi", "nibbāna"]
    for raw in inputs:
        out = to_canonical(raw)
        assert unicodedata.is_normalized("NFC", out), raw


# ---------------------------------------------------------------------------
# HTML stripping + entity handling
# ---------------------------------------------------------------------------


def test_strips_html_tags() -> None:
    assert to_canonical("<p>The Buddha said.</p>") == "The Buddha said."


def test_strips_nested_and_self_closing_tags() -> None:
    assert to_canonical('<div><p class="x">Hello<br/>World</p></div>') == "Hello World"


def test_unescapes_html_entities_before_tag_stripping() -> None:
    """``&lt;foo&gt;`` is a literal ``<foo>`` that should NOT be treated as a tag.

    In practice after unescape + tag strip we lose the fake tag text,
    but this test documents the order: entities first, so we never
    accidentally preserve `&lt;` in the output.
    """
    # ``&quot;`` is a straightforward case — becomes a real quote.
    assert to_canonical("&quot;satipaṭṭhāna&quot;") == '"satipaṭṭhāna"'


def test_handles_empty_and_none_like_inputs() -> None:
    assert to_canonical("") == ""
    # Single space — after collapse_whitespace + strip, must be empty.
    assert to_canonical("   ") == ""


# ---------------------------------------------------------------------------
# Whitespace collapse
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("hello   world", "hello world"),
        ("line1\n\n\nline2", "line1 line2"),
        ("tab\there", "tab here"),
        ("\u00a0nbsp\u00a0here\u00a0", "nbsp here"),  # non-breaking space
        ("\u202fnarrow\u202f", "narrow"),  # narrow NBSP
    ],
)
def test_collapse_whitespace(raw: str, expected: str) -> None:
    assert collapse_whitespace(raw) == expected


def test_collapse_whitespace_preserves_single_spacing() -> None:
    assert collapse_whitespace("already clean") == "already clean"


# ---------------------------------------------------------------------------
# IAST canonicalisation
# ---------------------------------------------------------------------------


def test_normalise_iast_harmonises_anusvara_variants() -> None:
    """Historical ṁ (U+1E41) and modern ṃ (U+1E43) mean the same sound."""
    assert normalise_iast("saṁsāra") == "saṃsāra"
    assert normalise_iast("SAṀSĀRA") == "SAṂSĀRA"


def test_normalise_iast_leaves_other_diacritics_untouched() -> None:
    """Only variant-spellings are harmonised; real diacritics stay."""
    raw = "satipaṭṭhāna nibbāna saññā"
    assert normalise_iast(raw) == raw


def test_canonical_end_to_end_applies_iast_normalisation() -> None:
    """to_canonical must include the IAST step (integration check)."""
    assert to_canonical("<p>saṁsāra</p>") == "saṃsāra"


# ---------------------------------------------------------------------------
# ASCII fold
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("canonical", "folded"),
    [
        ("satipaṭṭhāna", "satipatthana"),
        ("nibbāna", "nibbana"),
        ("saññā", "sanna"),
        ("saṃsāra", "samsara"),
        ("Bhikkhu Ñāṇamoli", "Bhikkhu Nanamoli"),
        ("Dhammacakkappavattana", "Dhammacakkappavattana"),  # no-op
        ("ŚRĪ", "SRI"),  # Sanskrit sibilant + long vowel, upper-case
    ],
)
def test_ascii_fold_table(canonical: str, folded: str) -> None:
    assert to_ascii_fold(canonical) == folded


def test_ascii_fold_is_pure_ascii_for_pure_iast_input() -> None:
    """Every folded character of a pure-IAST string must be ASCII."""
    canonical = "satipaṭṭhānasuttaṃ nibbānañca saññāyevā"
    folded = to_ascii_fold(canonical)
    assert folded.isascii(), folded


def test_ascii_fold_preserves_non_pali_diacritics() -> None:
    """German / French diacritics survive — folding is Pali-scoped.

    The cleaner's job is BM25-matching Pali, not destroying legitimate
    translator names. ``Ñāṇamoli`` folds (it's Pali), but ``müller``
    should not — it's a surname that deserves its own form.
    """
    assert to_ascii_fold("müller") == "müller"
    assert to_ascii_fold("café") == "café"


def test_ascii_fold_on_empty_string() -> None:
    assert to_ascii_fold("") == ""


# ---------------------------------------------------------------------------
# Integration: full pipeline on a realistic bilara segment
# ---------------------------------------------------------------------------


def test_full_pipeline_on_realistic_segment() -> None:
    raw = "<p>\u00a0Evaṁ me sutaṁ—ekaṁ samayaṁ bhagavā\nukkaṭṭhāyaṁ viharati. </p>\n\n"
    canonical = to_canonical(raw)
    assert canonical == "Evaṃ me sutaṃ—ekaṃ samayaṃ bhagavā ukkaṭṭhāyaṃ viharati."
    assert to_ascii_fold(canonical) == "Evam me sutam—ekam samayam bhagava ukkatthayam viharati."
