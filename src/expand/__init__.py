"""Query-side expansion shims (rag-day-28).

Two pure-text rewrite stages applied between the existing Pāli
glossary expansion (``src.processing.glossary``) and the encoder:

* :mod:`.definitional` — detects "what is X?" / "что такое X?" patterns
  and rewrites them into a longer gloss-shaped template so BGE-M3
  pulls foundational suttas instead of derivative shorter texts.
  Smoking gun in ``docs/QA040_INVESTIGATION.md``: a hand-rewritten
  longer query lifts mn10 from rrf_rank #126 to #1.

* :mod:`.foundational` — a curated YAML map ``term → [foundational_works]``
  applied as a post-RRF score boost. Closes the case where embedding
  cannot tell that a long obzornaya sutta is the *root* text for a
  topic vs short derivative suttas with the same surface form.

See ``docs/concepts/28-definitional-expansion.md`` for the full
rationale and the alternatives that were rejected (LLM rewrite,
RAG-Fusion, HyDE, learned-sparse, title-only named vector).
"""

from src.expand.definitional import expand_definitional, is_definitional
from src.expand.foundational import (
    FoundationalEntry,
    FoundationalMatcher,
    load_foundational_matcher,
)

__all__ = [
    "FoundationalEntry",
    "FoundationalMatcher",
    "expand_definitional",
    "is_definitional",
    "load_foundational_matcher",
]
