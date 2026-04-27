"""Prompt template + DI plumbing for Contextual Retrieval.

This module is provider-agnostic on purpose. Day-15 commits the prompt
template (validated against 50 sample chunks in ``docs/contextual/
validation_output_opus_v1.md``) and the data shapes the downstream
indexer will consume; the actual LLM client (Anthropic SDK / OpenAI-
compatible / cloud.ru) is plugged in on day-16 once we pick the
production provider.

Why a ``ContextProviderProtocol`` rather than a single concrete class
--------------------------------------------------------------------
Two real providers are on the table for day-16:

1. **Anthropic Haiku 3.5** — best English understanding, prompt
   caching cuts repeated-parent cost by ~80%. Estimated $1,800 for
   850K chunks at full corpus scale.
2. **cloud.ru hosted A100 + Qwen 2.5 32B (vLLM)** — ~$830 for the
   same job, fully in-RU infrastructure, no Anthropic billing
   friction. Trade-off: slightly weaker English Buddhist text
   handling.

Either way, the prompt is the same and the consumer of the result
(day-16 indexer) is the same. A protocol seam keeps day-15 honest:
we validate the *prompt*, not the *vendor*.

Prompt template lineage
-----------------------
* **v1** (this commit) — validated by reading 50 generated samples
  in chat. Two known soft-spots flagged: occasional speculative Pāli
  sutta titles (e.g. "Saddhā Sutta" for AN 5.38), a handful of
  outputs in the 110-130 token range. Both deemed acceptable for
  day-16 industrial run; tightening reserved for v2 if industrial
  outputs drift beyond 130 tokens routinely.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

PROMPT_TEMPLATE_V1: str = """\
You are an expert on the Pāli Canon (Theravāda Buddhism). For each chunk, \
write a SHORT context (50-100 tokens) that situates it within its source. \
The context will be PREPENDED to the chunk before embedding for retrieval, \
so it should help a search index find this exact passage.

Required content:
1. Sutta canonical ID (e.g. "MN 118")
2. Sutta title in Pāli (e.g. "Anāpānassati Sutta") if widely known — \
otherwise omit rather than guess
3. Location within the sutta (opening, gradual training, simile of X, etc.)
4. Main topic
5. Key Pāli terms preserved verbatim if present in the chunk (e.g. \
"satipaṭṭhāna", "anāpānassati", "paṭiccasamuppāda")

Style:
- Single paragraph, plain prose, no markdown
- 50-100 tokens (1-3 sentences)
- DO NOT paraphrase doctrine — describe factually
- DO preserve exact sutta IDs and Pāli terms
- DO use Sujato-style spelling (not Wisdom Pubs)

Output ONLY the context. No prefix, no headers, no quotation marks.
"""
"""Prompt template version 1 — validated against 50 samples on day-15.

Stable as a frozen string — bump to ``PROMPT_TEMPLATE_V2`` if the
industrial run on day-16 reveals systematic problems. The version
string ends up in ``ContextualizedChunk.prompt_version`` so future
maintenance can tell which prompt produced which embedding."""

PROMPT_VERSION_V1: str = "v1-2026-04-27"


@dataclass(frozen=True, slots=True)
class ContextualizedChunk:
    """One chunk with its LLM-generated context attached.

    ``prefixed_text`` is what gets embedded — context + the original
    child text concatenated. The original ``child_text`` is kept around
    so downstream code can show users the un-prefixed passage when
    rendering search results.

    Versioning rationale
    --------------------
    ``prompt_version`` and ``model_id`` are stored alongside the
    generated context so day-22+ work (re-embed when prompt changes,
    A/B against a different model) can identify which generation
    produced which embedding without re-running the corpus.
    """

    chunk_id: UUID
    parent_chunk_id: UUID | None
    child_text: str
    context: str
    prefixed_text: str
    prompt_version: str
    model_id: str


class ContextProviderProtocol(Protocol):
    """Structural type for the LLM client used to generate contexts.

    The protocol is intentionally minimal: one method that takes a
    (parent, child) pair and returns a context string. Concrete
    implementations (day-16) handle prompt caching, retries, batching,
    and rate-limiting. Tests use a ``FakeProvider`` that returns a
    deterministic string.
    """

    @property
    def model_id(self) -> str:
        """Stable string identifying the provider + model + version.

        Stored in ``ContextualizedChunk.model_id`` so we can later filter
        embeddings by which generation produced them.
        """
        ...

    def generate_context(self, *, parent_text: str, child_text: str) -> str:
        """Return a 50-100 token context for ``child_text``.

        Raises whatever the underlying provider raises on failure;
        day-16 indexer wraps with retry/backoff. Day-15 unit tests do
        not depend on this method (they target the pure helpers below).
        """
        ...


def build_request_messages(
    *, parent_text: str, child_text: str, prompt_template: str = PROMPT_TEMPLATE_V1
) -> list[dict[str, Any]]:
    """Compose the message list a chat-completions API would receive.

    Output is the standard OpenAI/Anthropic shape: a list of role-tagged
    messages. Day-16 providers convert this to their SDK's specific
    types. The structure here is what we test against — getting the
    parent in the *right* slot is essential for prompt caching to fire
    in the Anthropic SDK (the cacheable prefix must come before the
    per-chunk variable part).

    Parameters
    ----------
    parent_text:
        The full parent chunk (1024-2048 tokens). Forms the "context"
        portion of the prompt — wide-zoom view of where the child
        sits.
    child_text:
        The child chunk (~384 tokens) for which the context is
        generated.
    prompt_template:
        Defaults to :data:`PROMPT_TEMPLATE_V1`. Tests can pass a
        shorter stand-in to keep fixtures readable.
    """
    if not parent_text.strip():
        raise ValueError("parent_text must be non-empty")
    if not child_text.strip():
        raise ValueError("child_text must be non-empty")

    user_content = (
        f"<document>\n{parent_text.strip()}\n</document>\n\n<chunk>\n{child_text.strip()}\n</chunk>"
    )
    return [
        {"role": "system", "content": prompt_template.strip()},
        {"role": "user", "content": user_content},
    ]


def format_prefixed_chunk(*, context: str, child_text: str) -> str:
    """Concatenate context + chunk in the form fed to the embedding model.

    The format is plain text with a single-line separator — no XML, no
    markdown, no tags — so BGE-M3 sees a clean continuous passage. The
    context comes first because retrieval queries tend to anchor on
    metadata-style cues (sutta IDs, topic terms) which we want at the
    front of the embedded text.
    """
    ctx = context.strip()
    chunk = child_text.strip()
    if not ctx:
        raise ValueError("context must be non-empty")
    if not chunk:
        raise ValueError("child_text must be non-empty")
    return f"{ctx}\n\n{chunk}"


def build_contextualized_chunk(
    *,
    chunk_id: UUID,
    parent_chunk_id: UUID | None,
    child_text: str,
    context: str,
    model_id: str,
    prompt_version: str = PROMPT_VERSION_V1,
) -> ContextualizedChunk:
    """Glue helper: build the dataclass from raw fields.

    Kept separate from the dataclass constructor so tests can build
    these by hand without recomputing ``prefixed_text``, and so
    downstream code has a single chokepoint that always uses
    :func:`format_prefixed_chunk` (no risk of two consumers concat-ing
    differently).
    """
    return ContextualizedChunk(
        chunk_id=chunk_id,
        parent_chunk_id=parent_chunk_id,
        child_text=child_text,
        context=context,
        prefixed_text=format_prefixed_chunk(context=context, child_text=child_text),
        prompt_version=prompt_version,
        model_id=model_id,
    )


__all__ = [
    "PROMPT_TEMPLATE_V1",
    "PROMPT_VERSION_V1",
    "ContextProviderProtocol",
    "ContextualizedChunk",
    "build_contextualized_chunk",
    "build_request_messages",
    "format_prefixed_chunk",
]


# Keep ``Sequence`` quiet about top-level unused; reserved for future
# batch helpers in day-16 (e.g. ``contextualize_batch(parents, ...)``).
_: Any = Sequence
