"""Curated term → foundational works mapping with post-RRF boost (rag-day-28).

Why this exists
---------------
After definitional expansion, BGE-M3 may still mis-rank canonical
"root" suttas below derivative shorter texts that share the term's
surface form. Example from QA040:

    query: "What is dukkha?"
    expected: sn56.11 (Dhammacakkappavattana — First Sermon).
    actual: dozens of SN-22.x and MN-x chunks containing "dukkha"
            ranked above sn56.11.

The embedder cannot know that sn56.11 is the **canonical first source**
on dukkha and the others are practice-applications. This is human
domain knowledge — best encoded as a curated YAML and applied as a
post-fusion score boost.

How the boost is applied
------------------------
1. Lookup query (case-folded, NFC-normalised) against term + aliases.
2. For each matched entry, multiply ``rrf_score`` of every hit whose
   ``work_canonical_id`` is in ``entry.works`` by ``entry.boost``.
3. Re-sort by boosted score.

The boost is **post-fusion**, not pre-fusion. A pre-fusion boost
(e.g. inflating the dense-channel score) would propagate into all
queries containing the term, including ones where the foundational
sutta is not the right answer. Post-fusion boost only fires on
matched entries, so a query for "anger management in dukkha" doesn't
falsely promote sn56.11 if sn56.11 wasn't competitive in the
underlying retrieval.

YAML schema
-----------
See ``data/glossary/foundational.yaml`` for the live curation. Each
entry::

    - term: <canonical key>
      aliases: [<surface-form variants>, ...]
      works: [<work_canonical_id>, ...]
      boost: <float>   # optional, defaults to settings global

The aliases list should include latin / IAST / Cyrillic / English
synonyms — substring matching is the lookup mechanism.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from src.retrieval.schemas import HybridHit

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FoundationalEntry:
    """One curated mapping from a Buddhist term to its foundational work(s)."""

    term: str
    aliases: tuple[str, ...]
    works: tuple[str, ...]
    boost: float


@dataclass(frozen=True, slots=True)
class FoundationalMatch:
    """Result of matching a query against the foundational map.

    ``boost_by_work`` is keyed by ``work_canonical_id`` so the caller
    can apply the boost in O(N) over hits without re-walking entries.
    On overlap (same work appears in multiple matched entries), we
    keep the largest boost — most aggressive promotion wins.
    """

    matched_entries: tuple[FoundationalEntry, ...]
    boost_by_work: dict[str, float]


class FoundationalMatcher:
    """Match queries against the curated foundational mapping.

    Loaded once at startup from ``data/glossary/foundational.yaml``.
    Thread-safe (all state immutable after construction).
    """

    def __init__(self, entries: Sequence[FoundationalEntry], *, default_boost: float) -> None:
        self._entries = tuple(entries)
        self._default_boost = default_boost
        # Pre-compile per-alias regexes for whole-word matching.
        # Word-boundary protects against false matches like "dukkha" in
        # a longer made-up word. Built once, used many times.
        self._alias_index: list[tuple[re.Pattern[str], FoundationalEntry]] = []
        for entry in self._entries:
            for alias in entry.aliases + (entry.term,):
                normalised = _normalise(alias)
                if not normalised:
                    continue
                # Use word-boundary on both sides; ``re.escape`` so any
                # special chars in alias (rare, but defensive) are literal.
                pattern = re.compile(rf"(?<!\w){re.escape(normalised)}(?!\w)", re.IGNORECASE)
                self._alias_index.append((pattern, entry))

    @property
    def default_boost(self) -> float:
        return self._default_boost

    @property
    def entries(self) -> tuple[FoundationalEntry, ...]:
        return self._entries

    def match(self, query: str) -> FoundationalMatch:
        """Find all foundational entries triggered by ``query``.

        Returns an empty ``FoundationalMatch`` (no work boosted) if
        nothing matched. Callers can short-circuit on
        ``not match.boost_by_work``.
        """
        normalised_query = _normalise(query)
        seen: set[str] = set()
        matched: list[FoundationalEntry] = []
        boost_by_work: dict[str, float] = {}
        for pattern, entry in self._alias_index:
            if entry.term in seen:
                # Same entry already matched via another alias — skip.
                continue
            if pattern.search(normalised_query):
                seen.add(entry.term)
                matched.append(entry)
                effective_boost = entry.boost or self._default_boost
                for work_id in entry.works:
                    prev = boost_by_work.get(work_id, 0.0)
                    if effective_boost > prev:
                        boost_by_work[work_id] = effective_boost
        return FoundationalMatch(
            matched_entries=tuple(matched),
            boost_by_work=boost_by_work,
        )

    def bm25_aliases(self, query: str) -> list[str]:
        """Return English-descriptive aliases for matched terms.

        Sujato's translation replaces most Pāli terms with English
        equivalents (``dukkha`` → ``suffering``, ``anatta`` → ``not-self``,
        ``metta`` → ``loving-kindness``). A literal Pāli token query
        produces zero BM25 hits because the body text never contains
        the Pāli word. This method returns English aliases that the
        caller appends to the BM25 channel query so FTS can match.

        Filtering: skip the term itself, skip aliases that are ASCII
        transliterations of the same Pāli word (single-token, no
        spaces), skip Cyrillic aliases (FTS config is English).

        Returns at most 3 aliases per call to bound BM25 query length.
        """
        match = self.match(query)
        if not match.matched_entries:
            return []
        aliases: list[str] = []
        for entry in match.matched_entries:
            for alias in entry.aliases:
                cleaned = alias.strip()
                if not cleaned:
                    continue
                if _looks_pali_term(cleaned, entry.term):
                    continue
                if _looks_cyrillic(cleaned):
                    continue
                if cleaned not in aliases:
                    aliases.append(cleaned)
                if len(aliases) >= 3:
                    break
            if len(aliases) >= 3:
                break
        return aliases

    def apply_boost(self, hits: list[HybridHit], query: str) -> list[HybridHit]:
        """Boost ``rrf_score`` of hits whose work matches a curated term.

        Two-part promotion semantics:

        1. **Multiplicative**: ``rrf_score *= entry.boost`` for matched
           works. Lifts hits that are already competitive.
        2. **Floor-to-top**: if a foundational work appears in only one
           channel (e.g. BM25 alone — rrf_score ~0.015 vs top ~0.05),
           multiplicative boost is insufficient. Apply a floor at
           ``top_score`` so foundational works are guaranteed to
           appear near the top of the final list when matched. This
           is the explicit curatorial intent: ``dukkha → sn56.11``
           means "show sn56.11 prominently when user asks about
           dukkha", not "lift it slightly".

        The floor is the maximum *original* rrf_score across all hits
        (before per-hit multiplicative boost), so foundational works
        end up tied with the previous top, ranked by their own boost
        factor as tiebreak. Non-foundational works keep original
        scores, preserving organic ranking below the foundational cap.

        Returns a *new* list (HybridHit is frozen). When no match
        fires, returns the original list reference unchanged.
        """
        match = self.match(query)
        if not match.boost_by_work:
            return hits
        if not hits:
            return hits
        top_original = max(h.rrf_score for h in hits)
        boosted: list[HybridHit] = []
        for hit in hits:
            factor = match.boost_by_work.get(hit.work_canonical_id)
            if factor is None:
                boosted.append(hit)
            else:
                # Multiplicative bump first, then floor at top × factor
                # so the foundational tier lands above the organic top.
                multiplicative = hit.rrf_score * factor
                floor = top_original * factor
                new_score = max(multiplicative, floor)
                boosted.append(replace(hit, rrf_score=new_score))
        boosted.sort(key=lambda h: h.rrf_score, reverse=True)
        return boosted


def load_foundational_matcher(
    yaml_path: Path | None = None,
    *,
    default_boost: float = 1.5,
) -> FoundationalMatcher:
    """Load the curated YAML and build a :class:`FoundationalMatcher`.

    Defaults to ``data/glossary/foundational.yaml``. Raises
    :class:`FileNotFoundError` if missing — callers wrap in try/except
    if the matcher is optional (it is for the stub backend).
    """
    if yaml_path is None:
        yaml_path = Path(__file__).resolve().parents[2] / "data" / "glossary" / "foundational.yaml"
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"foundational.yaml must be a list of entries, got {type(raw).__name__}")
    entries: list[FoundationalEntry] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"foundational.yaml entry #{idx} is not a mapping")
        try:
            term = str(item["term"]).strip()
            aliases_raw = item.get("aliases") or []
            works_raw = item["works"]
        except KeyError as exc:
            raise ValueError(
                f"foundational.yaml entry #{idx} missing required field {exc}"
            ) from None
        aliases = tuple(str(a).strip() for a in aliases_raw if str(a).strip())
        works = tuple(str(w).strip() for w in works_raw if str(w).strip())
        if not term or not works:
            raise ValueError(f"foundational.yaml entry #{idx} must have non-empty term and works")
        boost = float(item.get("boost", default_boost))
        entries.append(FoundationalEntry(term=term, aliases=aliases, works=works, boost=boost))
    logger.info(
        "foundational.yaml loaded: %d entries, %d unique works",
        len(entries),
        len({w for e in entries for w in e.works}),
    )
    return FoundationalMatcher(entries, default_boost=default_boost)


def _looks_cyrillic(text: str) -> bool:
    """True iff text contains any Cyrillic character."""
    return any("\u0400" <= ch <= "\u04ff" for ch in text)


def _looks_pali_term(alias: str, canonical_term: str) -> bool:
    """True iff alias is just a Pāli/IAST variant of the canonical term.

    We want to skip aliases like ``satipatthana`` when canonical is
    ``satipaṭṭhāna`` — they're the same word in a different script and
    don't help BM25 (FTS already folds diacritics symmetrically). Keep
    English descriptive phrases like ``four foundations of mindfulness``.
    """
    a = unicodedata.normalize("NFC", alias).casefold()
    c = unicodedata.normalize("NFC", canonical_term).casefold()
    # Multi-word descriptive phrase → keep
    if " " in a:
        return False
    # Single token: drop ASCII variants of the same canonical Pāli word
    # by normalising both sides through the same diacritic folding the
    # corpus uses elsewhere. If they collapse to the same string, alias
    # is just a script variant.
    from src.processing.cleaner import to_ascii_fold

    return to_ascii_fold(a) == to_ascii_fold(c)


def _normalise(text: str) -> str:
    """Canonicalise text for matching: NFC + casefold + collapsed whitespace.

    NFC handles e.g. precomposed vs decomposed combining-mark forms of
    Pāli diacritics. Casefold is the Unicode-correct equivalent of
    lowercase that handles non-ASCII locales (e.g. Greek sigma).
    """
    nfc = unicodedata.normalize("NFC", text).casefold()
    return " ".join(nfc.split())
