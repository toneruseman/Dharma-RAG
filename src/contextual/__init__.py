"""Contextual Retrieval — LLM-generated context prepended to chunks before embedding.

Anthropic's Contextual Retrieval method (August 2024): prepend a short
LLM-generated context (50-100 tokens) to each chunk so the embedding
captures *where* the chunk lives in its document, not just the chunk's
own surface words. Reported −49% retrieval errors on Anthropic's benchmark
when added on top of dense + sparse hybrid.

Day-15 scope (prompt validation only)
-------------------------------------
* Define ``PROMPT_TEMPLATE_V1`` — the first iteration of the prompt
  template, validated in-conversation against 50 sample chunks
  (see ``docs/contextual/validation_output_opus_v1.md``).
* Define :class:`ContextualizedChunk` — the data shape downstream code
  (day-16 industrial run, day-17 A/B eval) consumes.
* Define :class:`ContextProviderProtocol` — DI seam for the actual LLM
  call. Day-15 ships only the protocol + a fake for tests; day-16
  picks the real provider (Anthropic Haiku 3.5 / cloud.ru Qwen / etc).
* :func:`build_request_messages` — the pure function that turns a
  (parent, child) pair into the API messages list. Tests verify the
  shape; no network call.

What this module does NOT do (yet)
----------------------------------
* No real LLM call. Day-16 picks the provider and adds a concrete
  implementation of :class:`ContextProviderProtocol`.
* No batch orchestration over the corpus. Day-16 adds the indexer.
* No re-embedding into Qdrant. Day-16 writes ``dharma_v2`` collection.
"""

from src.contextual.contextualizer import (
    PROMPT_TEMPLATE_V1,
    ContextProviderProtocol,
    ContextualizedChunk,
    build_request_messages,
    format_prefixed_chunk,
)

__all__ = [
    "PROMPT_TEMPLATE_V1",
    "ContextProviderProtocol",
    "ContextualizedChunk",
    "build_request_messages",
    "format_prefixed_chunk",
]
