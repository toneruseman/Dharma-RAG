"""Parent-child structural chunker for Dharma-RAG.

Design note — why this module exists
------------------------------------
Bilara ships segments (~10-30 tokens each). Neither of our downstream
consumers can use segments directly:

* **Retrieval indexes** (BGE-M3 dense, sparse, BM25) want chunks of
  roughly 256-512 tokens — one thought at a time, so the embedding
  captures a single idea cleanly.
* **LLM context** wants 1024-2048 tokens of cohesive prose so the
  generation model actually understands the passage.

A single chunk size can't serve both. The industry pattern
(LangChain's Parent Document Retrieval, Anthropic's Contextual
Retrieval paper) is to store **two** sizes per text: small child
chunks drive the search, and their parent is what the LLM sees.
This module produces both, from an ordered sequence of bilara
segments.

Design principles
-----------------
1. **Pure and dependency-free.** No DB, no tokenizer library. The
   token counter is injected so we can start with a heuristic and
   swap in the BGE-M3 tokenizer on rag-day-10 without touching this
   file.
2. **Structure-aware breaks.** Bilara segment IDs encode paragraph
   structure (``mn1:3.2`` → paragraph 3, sentence 2). We prefer to
   start new parents at paragraph boundaries and new children at
   sentence boundaries, falling back to hard-splits only when a
   single segment exceeds the target.
3. **Deterministic.** Same input → same chunks, every time. That's
   what makes ingest idempotent and lets us compare eval runs
   across days.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Final

# Type alias: any function that turns text into a token count.
# Default is a word-count heuristic (good enough for layout); swap in
# a real tokenizer on rag-day-10.
TokenCounter = Callable[[str], int]

# --- Default target sizes (override per call when experimenting) ----------

TARGET_PARENT_TOKENS: Final[int] = 1536
MAX_PARENT_TOKENS: Final[int] = 2048
TARGET_CHILD_TOKENS: Final[int] = 384
MAX_CHILD_TOKENS: Final[int] = 512

# Bilara segment IDs look like ``uid:paragraph.sentence`` (or
# ``uid:paragraph.sentence.word`` for fine-grained cases). Capturing
# the paragraph number lets us detect "new paragraph starts here"
# cheaply. Range-form uids (``an1.1-10``) complicate the colon split,
# so we anchor on the last colon.
_PARAGRAPH_RE: Final[re.Pattern[str]] = re.compile(r"^[^:]+:(\d+)\.")


# ---------------------------------------------------------------------------
# Inputs / outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SegmentInput:
    """A single bilara-level segment fed to the chunker.

    The chunker takes segments (not raw text) because segment IDs carry
    structural information we want to exploit (paragraph breaks) and
    preserve in the output metadata (``segment_ids`` per chunk for
    citations).

    Invariant: ``text`` must already be Unicode-NFC-normalised — the
    chunker is the point where per-segment cleaning results feed into
    persistent state, and downstream code (ASCII fold, BM25 index,
    embedding) assumes NFC. We assert rather than silently re-normalise
    so a missing ``to_canonical`` call in an upstream pipeline surfaces
    loudly in tests.
    """

    segment_id: str
    text: str

    def __post_init__(self) -> None:
        if self.text and not unicodedata.is_normalized("NFC", self.text):
            raise ValueError(
                f"SegmentInput.text must be NFC-normalised; got a "
                f"denormalised string for segment_id={self.segment_id!r}. "
                "Pipe the text through src.processing.cleaner.to_canonical "
                "before constructing a SegmentInput."
            )


@dataclass(slots=True)
class ChildChunk:
    """A small chunk that goes into the retrieval indexes.

    ``segment_ids`` is the list of bilara segments concatenated to
    form this child, in order. ``position_in_parent`` is 0-based within
    its parent, used for stable ordering on retrieval-time reassembly.
    """

    text: str
    token_count: int
    segment_ids: list[str]
    position_in_parent: int


@dataclass(slots=True)
class ParentChunk:
    """A large chunk containing one or more children.

    ``position`` is 0-based within the full Instance (i.e. per sutta).
    ``children`` are ordered by ``position_in_parent``.
    """

    text: str
    token_count: int
    segment_ids: list[str]
    position: int
    children: list[ChildChunk] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def default_token_count(text: str) -> int:
    """Quick-and-dirty token estimate.

    Why this heuristic: English words map to about 1.3 tokens in most
    modern tokenisers (tiktoken, BPE-based ones). Pali transliteration
    with diacritics tokenises finer (2-3 tokens per unfamiliar word),
    but since ingested text is mostly English translations plus a few
    Pali quotes, the 1.3 factor is close enough for layout decisions.

    A real tokenizer call costs ~100 µs per segment; this heuristic
    costs ~1 µs. Over 124k segments that's a 20-second difference.
    Good enough for rag-day-07; swap for the BGE-M3 tokenizer on
    rag-day-10 when accuracy actually matters.
    """
    words = len(text.split())
    return max(1, int(round(words * 1.3)))


def chunk_segments(
    segments: Sequence[SegmentInput],
    *,
    target_parent_tokens: int = TARGET_PARENT_TOKENS,
    max_parent_tokens: int = MAX_PARENT_TOKENS,
    target_child_tokens: int = TARGET_CHILD_TOKENS,
    max_child_tokens: int = MAX_CHILD_TOKENS,
    count_tokens: TokenCounter = default_token_count,
) -> list[ParentChunk]:
    """Turn an ordered list of segments into parent+child chunks.

    Algorithm, in plain English:

    1. Walk segments left to right, accumulating into the current
       parent buffer.
    2. When the buffer reaches ``target_parent_tokens`` AND the next
       segment starts a new paragraph (different number after the
       colon), close the parent — this gives us a natural boundary
       break.
    3. If the buffer ever exceeds ``max_parent_tokens``, force-close
       even mid-paragraph (safety valve).
    4. Within each closed parent, sub-walk its segments to build
       children with the same ``target``/``max`` logic at sentence
       (segment) boundaries.

    Target vs max: the target is the "we'd like to close around here"
    threshold; max is the "never exceed this" safety rail. Keeping the
    gap (1536 → 2048, 384 → 512) lets us wait for a natural break
    instead of chopping mid-thought.

    Returns a list of ``ParentChunk`` objects in source order. Each
    parent carries its children, already sliced and numbered. Empty
    input → empty output (no error).
    """
    if not segments:
        return []

    # Pre-compute paragraph keys so we don't re-regex the same segment
    # multiple times when checking boundaries.
    paragraphs = [_paragraph_of(s.segment_id) for s in segments]
    token_counts = [count_tokens(s.text) for s in segments]

    # First pass: group into parents.
    parents: list[list[int]] = []  # each element is a list of segment indices
    current: list[int] = []
    current_tokens = 0

    for i in range(len(segments)):
        seg_tokens = token_counts[i]

        # At a parent boundary if (a) current is already at or past
        # target AND this segment starts a new paragraph, or (b) adding
        # this segment would exceed max (safety valve).
        at_paragraph_break = (
            i > 0 and paragraphs[i] is not None and paragraphs[i] != paragraphs[i - 1]
        )
        would_overflow = current_tokens + seg_tokens > max_parent_tokens

        if current and (
            (current_tokens >= target_parent_tokens and at_paragraph_break) or would_overflow
        ):
            parents.append(current)
            current = []
            current_tokens = 0

        current.append(i)
        current_tokens += seg_tokens

    if current:
        parents.append(current)

    # Second pass: slice each parent into children.
    result: list[ParentChunk] = []
    for parent_idx, seg_indices in enumerate(parents):
        parent_segments = [segments[i] for i in seg_indices]
        parent_token_counts = [token_counts[i] for i in seg_indices]
        parent = _assemble_parent(
            parent_segments,
            parent_token_counts,
            position=parent_idx,
            target_child_tokens=target_child_tokens,
            max_child_tokens=max_child_tokens,
        )
        result.append(parent)
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _paragraph_of(segment_id: str) -> str | None:
    """Return the paragraph key from a bilara segment id, or None.

    ``mn1:3.2`` → ``"3"``. ``mn-name:1.mn-mulapannasa`` → ``None``
    (paragraph number is non-numeric). ``None`` disables the boundary
    heuristic for that segment — we fall back to token-count-only
    splitting, which is the safe default.
    """
    m = _PARAGRAPH_RE.match(segment_id)
    if m is None:
        return None
    return m.group(1)


def _assemble_parent(
    segments: Sequence[SegmentInput],
    token_counts: Sequence[int],
    *,
    position: int,
    target_child_tokens: int,
    max_child_tokens: int,
) -> ParentChunk:
    """Build one ParentChunk from a slice of segments + slice children."""
    parent_text = " ".join(s.text for s in segments).strip()
    parent_tokens = sum(token_counts)
    parent_segment_ids = [s.segment_id for s in segments]

    # Slice into children using the same "accumulate until target,
    # emit" pattern, breaking on any segment boundary.
    children: list[ChildChunk] = []
    buffer_indices: list[int] = []
    buffer_tokens = 0

    for i in range(len(segments)):
        seg_tokens = token_counts[i]
        would_overflow = buffer_tokens + seg_tokens > max_child_tokens
        at_target = buffer_tokens >= target_child_tokens

        if buffer_indices and (at_target or would_overflow):
            children.append(
                _make_child(
                    [segments[j] for j in buffer_indices],
                    [token_counts[j] for j in buffer_indices],
                    position_in_parent=len(children),
                )
            )
            buffer_indices = []
            buffer_tokens = 0

        buffer_indices.append(i)
        buffer_tokens += seg_tokens

    if buffer_indices:
        children.append(
            _make_child(
                [segments[j] for j in buffer_indices],
                [token_counts[j] for j in buffer_indices],
                position_in_parent=len(children),
            )
        )

    return ParentChunk(
        text=parent_text,
        token_count=parent_tokens,
        segment_ids=parent_segment_ids,
        position=position,
        children=children,
    )


def _make_child(
    segments: Sequence[SegmentInput],
    token_counts: Sequence[int],
    *,
    position_in_parent: int,
) -> ChildChunk:
    return ChildChunk(
        text=" ".join(s.text for s in segments).strip(),
        token_count=sum(token_counts),
        segment_ids=[s.segment_id for s in segments],
        position_in_parent=position_in_parent,
    )
