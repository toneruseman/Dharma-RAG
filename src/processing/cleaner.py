"""Text normalisation pipeline for Dharma-RAG.

The cleaner is deliberately a set of small pure functions rather than a
class: each stage transforms ``str -> str`` with no hidden state, so we
can mix and match, unit-test each step in isolation, and apply the same
pipeline at query time that we used at ingest time.

Two canonical outputs matter downstream:

* :func:`to_canonical` — the text a reader sees, with full IAST
  diacritics preserved (``satipaṭṭhāna``). Embedded into the LLM
  prompt, shown in citations, stored as ``chunk.text``.
* :func:`to_ascii_fold` — a diacritic-stripped shadow used by BM25 and
  as a fallback when users type ``satipatthana`` without diacritics.
  Stored as ``chunk.text_ascii_fold``.

The query pipeline must apply the same transforms so a query of
``satipatthana`` matches chunks indexed as ``satipaṭṭhāna``.
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Final

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

# HTML tags: greedy enough to catch ``<p class="foo">`` and ``<br/>`` but
# NOT the ``<`` / ``>`` signs inside prose. Pali corpora occasionally
# contain angle brackets in editorial notes (``<angamagadha>``); those
# are effectively tags for our purpose and can be stripped.
_TAG_RE: Final[re.Pattern[str]] = re.compile(r"<[^>]+>")

# All Unicode whitespace categories collapse to a single ASCII space.
# Bilara text sometimes ships NBSP (U+00A0) or narrow NBSP (U+202F).
_WHITESPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")

# Pali IAST diacritic map for ASCII folding. We deliberately keep it
# explicit (no "strip every combining mark") so non-Pali diacritics
# like German umlauts or French accents remain untouched — those might
# appear in translator names or modern commentary and we don't want to
# flatten "Bhikkhu Ñāṇamoli" into "Bhikkhu Nanamoli" for the canonical
# form. ASCII-fold is only for BM25 matching, not for display.
_IAST_FOLD_MAP: Final[dict[str, str]] = {
    # Long vowels → short counterpart.
    "ā": "a", "Ā": "A",
    "ī": "i", "Ī": "I",
    "ū": "u", "Ū": "U",
    "ṝ": "r", "Ṝ": "R",
    "ḹ": "l", "Ḹ": "L",
    # Vocalic r / l.
    "ṛ": "r", "Ṛ": "R",
    "ḷ": "l", "Ḷ": "L",
    # Retroflex consonants (dot below).
    "ṭ": "t", "Ṭ": "T",
    "ḍ": "d", "Ḍ": "D",
    "ṇ": "n", "Ṇ": "N",
    "ṣ": "s", "Ṣ": "S",
    # Palatal / guttural nasals.
    "ñ": "n", "Ñ": "N",
    "ṅ": "n", "Ṅ": "N",
    # Anusvāra (ṃ is the modern IAST form; ṁ is the older Pali
    # Text Society form — we canonicalise both to ṃ in
    # `normalise_iast` and only fold here).
    "ṃ": "m", "Ṃ": "M",
    # Visarga.
    "ḥ": "h", "Ḥ": "H",
    # Palatal sibilant.
    "ś": "s", "Ś": "S",
}  # fmt: skip

# Map of IAST variant-spellings that mean the same sound. Applied in
# :func:`normalise_iast`. The most common one in Pali text is ṁ vs ṃ —
# PTS used ṁ (U+1E41, m-dot-above) historically; modern scholarship
# and bilara use ṃ (U+1E43, m-dot-below). Harmonising them means
# ``saṁsāra`` and ``saṃsāra`` produce identical embeddings.
_IAST_CANONICAL_MAP: Final[dict[str, str]] = {
    "ṁ": "ṃ", "Ṁ": "Ṃ",
    # Older "nn" variant for ñ is rarely seen in machine-readable
    # Pali but we leave the slot here for when Access to Insight
    # scraping starts.
}  # fmt: skip


# ---------------------------------------------------------------------------
# Public pipeline
# ---------------------------------------------------------------------------


def to_canonical(raw: str) -> str:
    """Full canonical cleaning for display and embedding.

    Order matters: HTML entities are unescaped *before* tag stripping
    so that ``&lt;foo&gt;`` does not accidentally become a tag; NFC
    normalisation runs after entity decoding so that entity-produced
    combining characters get composed; whitespace is the last step so
    stripped HTML leaves a clean gap.
    """
    if not raw:
        return ""
    text = html.unescape(raw)
    text = _strip_tags(text)
    text = unicodedata.normalize("NFC", text)
    text = normalise_iast(text)
    text = collapse_whitespace(text)
    return text


def to_ascii_fold(canonical: str) -> str:
    """ASCII-folded shadow of a canonical text.

    Input must already be canonical (NFC-normalised IAST) — passing
    raw HTML here will produce garbage. The intended call site is
    ``to_ascii_fold(to_canonical(raw))``, or the chunk's stored
    ``text`` field which is guaranteed canonical.
    """
    if not canonical:
        return ""
    return "".join(_IAST_FOLD_MAP.get(ch, ch) for ch in canonical)


def normalise_iast(text: str) -> str:
    """Harmonise IAST variant spellings to their canonical form.

    Currently handles ``ṁ → ṃ``. Extended as new corpora surface more
    spelling variants.
    """
    if not text:
        return text
    return "".join(_IAST_CANONICAL_MAP.get(ch, ch) for ch in text)


def collapse_whitespace(text: str) -> str:
    """Collapse any run of Unicode whitespace to a single space and strip.

    Preserves internal structure (one space between words) while
    removing newlines, tabs, and non-breaking spaces that the source
    might have sprinkled in for layout.
    """
    return _WHITESPACE_RE.sub(" ", text).strip()


def _strip_tags(text: str) -> str:
    """Remove HTML/XML-style tags. No attempt to parse malformed HTML."""
    return _TAG_RE.sub(" ", text)
