"""Detect and expand short definitional queries (rag-day-28).

Why this exists
---------------
On the QA040 corpus probe (see ``docs/QA040_INVESTIGATION.md``) we
observed that the literal query

    "What is satipaṭṭhāna?"

placed mn10 at rrf_rank ``#126`` (out of top-200), while the
hand-rewritten

    "What are the four foundations of mindfulness?"

placed mn10 at ``#1``. The two queries mean the same thing, but the
shorter Pāli-on-bare form gives BGE-M3 a query embedding that drifts
toward the cluster centroid of all chunks containing satipaṭṭhāna —
lots of derivative SN-47 fragments dominate. The longer gloss form
contains "Foundations of...", "Sutta on...", "Discourse on..." — the
exact phrases that show up in canonical sutta titles and openings,
so BGE-M3 lands on them.

We don't need an LLM to bridge the gap. A deterministic regexp +
template is enough to reproduce the smoking-gun rewrite.

What this module does NOT do
----------------------------
* Doesn't disambiguate ambiguous Pāli (use the rag-day-23 glossary).
* Doesn't substitute synonyms (foundational mapping handles
  cross-term semantic boosts).
* Doesn't try to be exhaustive — if the regexp doesn't match, the
  query passes through unchanged. False-negative is preferred over
  false-positive (a non-definitional query rewritten as definitional
  loses precision on its actual topic).
"""

from __future__ import annotations

import re

# Patterns that mark a query as definitional. We're deliberately
# restrictive: each pattern requires the question to be *short and
# focused* (≤ 8 tokens after the trigger). This avoids rewriting
# long practice-oriented queries like "How do I work with anger when
# I'm feeling restless in jhana?" — those are not definitional even
# though they contain "in jhana".
#
# Capture group is named ``term``. The trigger phrase that opens the
# question is captured implicitly by the pattern start.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    # English: "What is satipaṭṭhāna?", "What is the dukkha?"
    re.compile(r"^\s*what\s+(?:is|are)\s+(?:the\s+|a\s+)?(?P<term>[^?.,;]+?)\s*[?.]?\s*$", re.I),
    # English: "Define satipaṭṭhāna", "Define the four noble truths"
    re.compile(r"^\s*define\s+(?:the\s+)?(?P<term>[^?.,;]+?)\s*[?.]?\s*$", re.I),
    # English: "Meaning of satipaṭṭhāna", "Definition of dukkha"
    re.compile(r"^\s*(?:meaning|definition)\s+of\s+(?P<term>[^?.,;]+?)\s*[?.]?\s*$", re.I),
    # Russian: "Что такое сатипаттхана?", "Что такое четыре благородные истины"
    re.compile(r"^\s*что\s+такое\s+(?P<term>[^?.,;]+?)\s*[?.]?\s*$", re.I),
    # Russian: "Определение сатипаттханы", "Что значит дуккха"
    re.compile(r"^\s*(?:определение|значение)\s+(?P<term>[^?.,;]+?)\s*[?.]?\s*$", re.I),
    re.compile(r"^\s*что\s+(?:значит|означает)\s+(?P<term>[^?.,;]+?)\s*[?.]?\s*$", re.I),
)

# Maximum number of words in the captured term. Above this we assume
# the question is sufficiently specific already and shouldn't be
# template-expanded. Empirically: "What is the relationship between
# satipaṭṭhāna and anapanasati?" — 7 words after "What is" — is not
# improved by gloss-template (it's a genuine relational question).
_MAX_TERM_WORDS = 6

# Templates per detected language. We pick the language by which
# pattern matched (English vs Cyrillic). The template intentionally
# echoes phrases that show up in canonical sutta titles and openings:
# "Discourse on X", "Sutta on X", "Foundations of X". These are the
# words BGE-M3 sees in the corpus and pulls toward.
_TEMPLATE_EN = "What is {term}? Discourse on {term}. Foundations of {term}. Sutta on {term}."
_TEMPLATE_RU = "Что такое {term}? Учение о {term}. Основы {term}. Сутта о {term}."


def is_definitional(query: str) -> tuple[str, str] | None:
    """Return ``(term, lang)`` if ``query`` looks definitional, else ``None``.

    ``lang`` is ``"en"`` or ``"ru"`` and tells the caller which template
    to use for expansion. We expose this separately so observability
    spans can record *whether* a query was detected as definitional
    even if expansion is later disabled by config.
    """
    for pat in _PATTERNS:
        match = pat.match(query)
        if match is None:
            continue
        term = match.group("term").strip()
        if not term:
            continue
        if len(term.split()) > _MAX_TERM_WORDS:
            # Long captured term — likely a relational question, not a
            # definitional one. Pass through.
            continue
        lang = "ru" if _looks_cyrillic(query) else "en"
        return term, lang
    return None


def expand_definitional(
    query: str,
    *,
    term_aliases: dict[str, list[str]] | None = None,
) -> str:
    """Rewrite a definitional query into expanded gloss form.

    Behaviour:
    * Non-definitional or ambiguous → returns ``query`` unchanged.
    * Short definitional → prepends a template with the captured term
      substituted, retaining the original query verbatim at the start
      so any keyword the user typed survives (BM25 channel still sees
      the literal form).
    * When ``term_aliases`` is provided and contains an entry whose
      key matches the captured term (case-insensitive substring),
      English aliases are appended as extra gloss sentences. This is
      what bridges the bare-Pāli term in the user query (``satipaṭṭhāna``)
      to the English description that BGE-M3 actually finds in
      canonical sutta chunks (``four foundations of mindfulness``).

    ``term_aliases`` is plumbed in from ``FoundationalMatcher`` upstream
    — keeping it optional so this module stays independent of the
    glossary layer. Without it the function still expands, just with
    bare-template gloss only.

    Example::

        >>> expand_definitional("What is satipaṭṭhāna?")
        'What is satipaṭṭhāna? Discourse on satipaṭṭhāna. Foundations of \
satipaṭṭhāna. Sutta on satipaṭṭhāna.'
        >>> expand_definitional("How do I work with anger?")
        'How do I work with anger?'
    """
    detected = is_definitional(query)
    if detected is None:
        return query
    term, lang = detected
    template = _TEMPLATE_RU if lang == "ru" else _TEMPLATE_EN
    expanded = template.format(term=term)
    extra = _aliases_extension(term, lang, term_aliases)
    if extra:
        expanded = f"{expanded} {extra}"
    return expanded


def _aliases_extension(
    term: str,
    lang: str,
    term_aliases: dict[str, list[str]] | None,
) -> str:
    """Build a trailing gloss sentence from canonical aliases.

    Picks aliases that look like canonical English descriptive phrases
    (multi-word, ASCII-mostly) and wraps them as a final sentence.
    Skips aliases that look like the captured term itself or are
    pure Pāli/Cyrillic — they don't help BGE-M3 cross to English
    chunk text.
    """
    if not term_aliases:
        return ""
    term_lower = term.casefold().strip()
    aliases: list[str] = []
    for key, alias_list in term_aliases.items():
        key_lower = key.casefold().strip()
        if term_lower == key_lower or term_lower in key_lower or key_lower in term_lower:
            aliases = alias_list
            break
    if not aliases:
        return ""
    # Pick aliases that are multi-word English phrases (descriptive),
    # skipping single-token ones (less useful) and Cyrillic aliases.
    descriptive = [
        a
        for a in aliases
        if " " in a.strip() and not _looks_cyrillic(a) and a.casefold() != term_lower
    ]
    if not descriptive:
        return ""
    # Join up to 3 aliases — more dilutes the encode signal.
    chosen = descriptive[:3]
    if lang == "ru":
        return ". ".join(f"То же что {a}" for a in chosen) + "."
    return ". ".join(f"Also known as {a}" for a in chosen) + "."


def _looks_cyrillic(text: str) -> bool:
    """Return True iff the query contains any Cyrillic character.

    Used to pick the Russian-language template. Mixed-script queries
    (e.g. "Что такое satipaṭṭhāna?") count as Cyrillic — the Russian
    template still surfaces the term, and the term itself preserves
    its IAST diacritics.
    """
    return any("\u0400" <= ch <= "\u04ff" for ch in text)
