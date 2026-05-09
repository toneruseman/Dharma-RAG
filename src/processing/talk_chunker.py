"""Parent-child chunker for oral dharma talks (rag-day-37).

Why a separate module from :mod:`src.processing.chunker`
--------------------------------------------------------
The canonical chunker (``chunk_segments``) takes ordered ``SegmentInput``
records — bilara-style segments with stable ``segment_id``s like
``mn10:8.1``. That structure drives chunk boundaries: parents start on
new paragraphs, children on new sentences. Talks have **no segments**,
just continuous prose from a Whisper transcription. Different shape →
different chunker.

What this module does
---------------------
1. Take a raw talk body (header/footer already stripped by the loader).
2. Split into paragraphs on blank-line boundaries (``\\n\\n``).
3. Group paragraphs into **parents** of ~1024 tokens (keeping paragraph
   boundaries — never splitting a paragraph across parents).
4. Split each parent into **children** of ~384 tokens with sentence-
   level boundaries and a small overlap window (~25%). The overlap
   helps small-to-big retrieval recover when a query matches text
   straddling a child boundary.

Outputs are the same :class:`ChildChunk` / :class:`ParentChunk`
shapes the canonical chunker produces — keeping the downstream
ingest path (``ingest_dharmaseed.py`` → DB → encoder) unified.

Talks have no ``segment_id``; we emit ``segment_ids=[]`` on every
chunk and signal position via ``position`` / ``position_in_parent``
only. Citations end up as ``rb_12345 · ¶3`` rather than ``mn10:8.1``.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Final

from src.processing.chunker import (
    MAX_CHILD_TOKENS,
    MAX_PARENT_TOKENS,
    TARGET_CHILD_TOKENS,
    TARGET_PARENT_TOKENS,
    ChildChunk,
    ParentChunk,
    TokenCounter,
    default_token_count,
)

# Default child overlap as a fraction of ``target_child_tokens``. For
# talks at 384/1024, 25% means ~96 tokens (~5 sentences) repeated
# between adjacent children. Sized to recover near-boundary queries
# without exploding storage cost (1.25× the no-overlap baseline).
DEFAULT_CHILD_OVERLAP_RATIO: Final[float] = 0.25

# Sentence boundary heuristic. We accept ``. `` / ``? `` / ``! `` and
# also Russian terminators. Robust enough for Whisper output, which
# tends to be well-punctuated; not a full segmenter.
_SENTENCE_END_RE: Final[re.Pattern[str]] = re.compile(r"(?<=[.!?…])\s+")


def _split_paragraphs(body: str) -> list[str]:
    """Break a Whisper-transcript body into paragraphs.

    Whisper output uses a blank line between speaker pauses. Empty
    paragraphs (caused by trailing whitespace or transcript artefacts)
    are skipped.
    """
    paragraphs = re.split(r"\n{2,}", body.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def _split_sentences(text: str) -> list[str]:
    """Sentence-level split for child boundaries.

    Falls back to the whole paragraph if no sentence-ender is found —
    keeps the chunker robust against paragraphs that are a single long
    sentence (common in stream-of-consciousness teachings).
    """
    parts = _SENTENCE_END_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()] or [text.strip()]


def chunk_talk(
    body: str,
    *,
    target_parent_tokens: int = TARGET_PARENT_TOKENS,
    max_parent_tokens: int = MAX_PARENT_TOKENS,
    target_child_tokens: int = TARGET_CHILD_TOKENS,
    max_child_tokens: int = MAX_CHILD_TOKENS,
    child_overlap_ratio: float = DEFAULT_CHILD_OVERLAP_RATIO,
    count_tokens: TokenCounter = default_token_count,
) -> list[ParentChunk]:
    """Chunk a talk body into parents containing ordered child chunks.

    Parameters mirror :func:`src.processing.chunker.chunk_segments`
    where they make sense; ``child_overlap_ratio`` is talk-specific.

    Returns parent chunks in document order (``position`` 0..N-1). Each
    parent owns its children (``children`` populated). Both parent and
    child carry empty ``segment_ids`` — talks have none — so callers
    must not infer structure from that field.
    """
    if child_overlap_ratio < 0.0 or child_overlap_ratio >= 1.0:
        raise ValueError(f"child_overlap_ratio must be in [0, 1), got {child_overlap_ratio}")

    parents = _build_parents(
        paragraphs=_split_paragraphs(body),
        target_parent_tokens=target_parent_tokens,
        max_parent_tokens=max_parent_tokens,
        count_tokens=count_tokens,
    )

    out: list[ParentChunk] = []
    for position, parent_text in enumerate(parents):
        children = _build_children(
            parent_text=parent_text,
            target_child_tokens=target_child_tokens,
            max_child_tokens=max_child_tokens,
            child_overlap_ratio=child_overlap_ratio,
            count_tokens=count_tokens,
        )
        out.append(
            ParentChunk(
                text=parent_text,
                token_count=count_tokens(parent_text),
                segment_ids=[],
                position=position,
                children=children,
            )
        )
    return out


def _build_parents(
    paragraphs: list[str],
    *,
    target_parent_tokens: int,
    max_parent_tokens: int,
    count_tokens: TokenCounter,
) -> list[str]:
    """Group paragraphs into parent-sized buckets without splitting them."""
    parents: list[str] = []
    cur: list[str] = []
    cur_tok = 0
    for para in paragraphs:
        ptok = count_tokens(para)
        # If a single paragraph already exceeds max_parent_tokens, emit
        # it on its own — splitting at sentence boundaries would risk
        # corrupting structure. The reranker / downstream consumer can
        # cope with one oversized parent; better than half-paragraphs.
        if ptok > max_parent_tokens and not cur:
            parents.append(para)
            continue
        if cur and cur_tok + ptok > target_parent_tokens:
            parents.append("\n\n".join(cur))
            cur, cur_tok = [], 0
        cur.append(para)
        cur_tok += ptok
    if cur:
        parents.append("\n\n".join(cur))
    return parents


def _build_children(
    *,
    parent_text: str,
    target_child_tokens: int,
    max_child_tokens: int,
    child_overlap_ratio: float,
    count_tokens: TokenCounter,
) -> list[ChildChunk]:
    """Split ``parent_text`` into overlapping sentence-aligned children."""
    sentences = _split_sentences(parent_text)
    sent_toks = [count_tokens(s) for s in sentences]

    overlap_target = int(target_child_tokens * child_overlap_ratio)
    children: list[ChildChunk] = []

    i = 0
    position = 0
    while i < len(sentences):
        # Grow forward from sentence i until we hit target.
        cur: list[str] = []
        cur_tok = 0
        j = i
        while j < len(sentences) and (cur_tok + sent_toks[j] <= max_child_tokens or not cur):
            cur.append(sentences[j])
            cur_tok += sent_toks[j]
            j += 1
            if cur_tok >= target_child_tokens:
                break
        if not cur:
            break
        children.append(
            ChildChunk(
                text=" ".join(cur),
                token_count=cur_tok,
                segment_ids=[],
                position_in_parent=position,
            )
        )
        position += 1

        if j >= len(sentences):
            break

        # Step the cursor back by ~overlap_target tokens so the next
        # child re-includes a tail of this one. Walk backwards from j
        # accumulating tokens until we have enough overlap.
        back = j
        back_tok = 0
        while back > i + 1 and back_tok < overlap_target:
            back -= 1
            back_tok += sent_toks[back]
        # Avoid infinite loop on degenerate inputs (single huge sentence).
        i = max(back, i + 1)

    return children


__all__ = ["chunk_talk", "DEFAULT_CHILD_OVERLAP_RATIO"]


# Convenience for callers that want word counts but a different
# heuristic — exposed so ingest scripts can swap in BGE-M3's tokenizer
# later without changing this module.
def words_token_count(text: str) -> int:
    """Pure word-count heuristic (no 1.3× modifier).

    Useful for quick-and-rough budgeting; production ingest should use
    the inherited ``default_token_count`` for parity with the canon
    chunker.
    """
    return max(1, len(text.split()))


_ = Callable[[str], int]  # silence unused import — ``TokenCounter`` already covers it
