"""Stable contract for the RAG service.

``POST /api/query`` is the **production** retrieval entrypoint that
downstream consumers (LLM generation, future Telegram bot, frontend)
will call. Unlike ``POST /api/retrieve`` — which exposes the full
diagnostic surface for evaluation and tuning — ``/api/query`` only
takes *semantic* parameters and returns a stable, stripped result
shape.

The split is deliberate: ``/api/retrieve`` will keep evolving as we
tune RRF weights, add channels, swap the reranker. ``/api/query`` is
the contract we promise to keep stable. Server-side defaults
(`retrieval_collection`, `retrieval_rerank_default`,
`retrieval_expand_parents_default` from settings) decide pipeline
behaviour — clients do not pass them.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Body of POST /api/query."""

    query: str = Field(..., min_length=1, max_length=2000, description="User query")
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description=(
            "Number of source passages to return. Tighter cap than "
            "/api/retrieve (which allows up to 100) because /api/query "
            "is sized for direct LLM consumption — 5 parents at "
            "~1.5K tokens each fits comfortably in any context window."
        ),
    )
    language: str | None = Field(
        default=None,
        description=(
            "Reserved for future filtering. Currently ignored; the "
            "corpus is English-only after rag-day-04. Accepting it now "
            "lets clients write code that survives the multi-language "
            "rollout without a contract bump."
        ),
    )
    forbidden_works: list[str] | None = Field(
        default=None,
        description=(
            "Optional post-filter: drop hits whose ``work_canonical_id`` "
            "appears in this list. Use for per-tenant content policy "
            "(e.g. excluding texts a community considers sensitive). "
            "Filtering is post-RRF — ``top_k`` is honoured after the "
            "filter, so requests with a long forbidden list may return "
            "fewer than ``top_k`` sources."
        ),
    )
    expand_pali: bool | None = Field(
        default=None,
        description=(
            "Override Pāli-glossary query expansion (rag-day-23). "
            "``None`` (default) defers to the server-side setting "
            "``glossary_expand_pali_default``. ``True`` rewrites the "
            "query with the canonical Pāli lemma + its EN/RU meanings "
            "before encoding (helps bare-Pāli or cyrillic-transliterated "
            "queries). ``False`` forces a clean no-expansion run, useful "
            "for debugging an unexpected hit set."
        ),
    )


class Source(BaseModel):
    """One source passage in the response.

    Mapped from :class:`src.retrieval.schemas.HybridHit`. Internal
    diagnostic fields (``rrf_score``, ``per_channel_rank``,
    ``rerank_score``, ``rrf_rank``, ``parent_chunk_id``, ``is_parent``,
    ``chunk_id``) are intentionally **dropped** — clients should not
    couple to retrieval internals. ``score`` is a normalised 0-1
    summary suitable for UI sorting / thresholding.
    """

    work_canonical_id: str = Field(
        ..., description="Stable canonical ID like ``mn10`` or ``sn56.11``."
    )
    segment_id: str | None = Field(
        default=None,
        description=(
            "SuttaCentral segment identifier when present. Useful for "
            "deep-linking back to the source on suttacentral.net."
        ),
    )
    text: str = Field(
        ...,
        description=(
            "Passage handed to the LLM. With server-side parent "
            "expansion (default), this is the parent chunk — a "
            "semantically-complete section, ~1024-2048 tokens."
        ),
    )
    snippet: str = Field(
        ...,
        description=(
            "The precise child fragment that matched the query. Use "
            "for highlighted citations in the UI; ``text`` is the "
            "broader passage. When parent expansion is off, "
            "``snippet`` equals ``text``."
        ),
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Normalised relevance score in [0, 1]. Source: rerank "
            "score (sigmoid-mapped) when the reranker ran, otherwise "
            "RRF score scaled by the top hit. Comparable within a "
            "single response only — not across responses."
        ),
    )


class PipelineMetadata(BaseModel):
    """Diagnostic metadata about which pipeline produced the response.

    Embedded so a downstream consumer can reason about answer quality
    when the server-side defaults change. Stable in the sense that the
    *fields* are guaranteed; *values* are free to evolve as we tune.
    """

    version: str = Field(
        ...,
        description=(
            "Pipeline version string — encodes collection + flags. "
            "Format: ``{collection}-rerank{0|1}-parents{0|1}``. "
            "Example: ``dharma_v2-rerank0-parents1``."
        ),
    )
    collection: str = Field(..., description="Qdrant collection that served the query.")
    rerank: bool = Field(..., description="Whether the cross-encoder reranker ran.")
    expand_parents: bool = Field(
        ..., description="Whether parent expansion (small-to-big) was applied."
    )
    expand_pali: bool = Field(
        ...,
        description=(
            "Whether the query was rewritten via the Pāli glossary "
            "(rag-day-23) before encoding. ``False`` when either "
            "disabled by setting/request or when no glossary terms "
            "matched the query — the metadata field tracks the "
            "*effective* expansion, not just the toggle."
        ),
    )
    n_candidates: int = Field(
        ..., ge=0, description="RRF candidate pool size before truncation to ``top_k``."
    )


class QueryResponse(BaseModel):
    """Body of the response from POST /api/query."""

    query: str = Field(..., description="Echo of the user's query.")
    sources: list[Source] = Field(
        ...,
        description=(
            "Top-k source passages in relevance order. May be empty "
            "when the query yields no hits or when ``forbidden_works`` "
            "filters everything out."
        ),
    )
    latency_ms: float = Field(..., description="End-to-end wall-clock time in milliseconds.")
    metadata: PipelineMetadata


# --------------------------------------------------------------------- #
# GET /api/sources/{canonical_id} — Reading Room (app-day-21).
#
# Different shape from QueryResponse: instead of top-k passages ranked
# by relevance, we return the *full* document for a single work.
# Drives the `/read/[uid]` Next.js page; not part of the retrieval flow.
# --------------------------------------------------------------------- #


class SourceParagraph(BaseModel):
    """A single ordered paragraph (parent-chunk) of the document."""

    sequence: int = Field(
        ..., ge=0, description="Position in the document (0-based, document order)."
    )
    segment_id: str | None = Field(
        default=None,
        description=(
            "SuttaCentral-style identifier when present (e.g. ``mn10:12.3``). "
            "Used for deep-linking from search results to the matching paragraph."
        ),
    )
    text: str = Field(..., description="Paragraph body — parent-chunk text, ~1024-2048 tokens.")


class SourceTranslation(BaseModel):
    """Provenance metadata for the rendered translation."""

    author: str | None = Field(
        default=None,
        description=(
            "Translator's display name when known (e.g. ``Bhikkhu Sujato``). "
            "May be ``None`` for anonymous or compiler editions."
        ),
    )
    language_code: str = Field(
        ...,
        description=(
            "Language code as stored in the corpus, typically ISO 639-3 "
            "(``eng``, ``rus``, ``pli``). Stub returns ``en``-style codes "
            "for fixture readability — frontend should accept either."
        ),
    )
    title: str | None = Field(
        default=None,
        description=(
            "Translation-specific title, may differ from the work's canonical "
            "title (e.g. ``The Establishings of Mindfulness`` for ``mn10``)."
        ),
    )
    publication_year: int | None = Field(
        default=None, description="Year of publication when known."
    )
    license: str = Field(
        ...,
        description=(
            "SPDX-like license tag (``CC0``, ``CC-BY-4.0``, "
            "``CC-BY-NC-4.0``, ``ARR``…). Always set — corpus invariant."
        ),
    )


class SourceDocument(BaseModel):
    """Full document body for the Reading Room.

    Shape mirrors what a reader needs: identity (``canonical_id`` /
    ``title`` / ``title_pali``), provenance (``translation``), and
    body (``paragraphs`` in document order). Diagnostic retrieval
    fields are intentionally absent — this isn't a search response.
    """

    canonical_id: str = Field(
        ..., description="Stable canonical ID like ``mn10`` (echoes the path parameter)."
    )
    title: str = Field(..., description="Canonical title of the work.")
    title_pali: str | None = Field(
        default=None,
        description=(
            "Pāli title with diacritics when known (e.g. ``Satipaṭṭhāna Sutta``). "
            "Useful to display alongside an English translation."
        ),
    )
    tradition_code: str = Field(
        ..., description="Tradition tag from ``tradition_t`` (``theravada``, ``mahayana``…)."
    )
    is_restricted: bool = Field(
        default=False,
        description=(
            "Vajrayana / tantric works flagged as requiring initiation. "
            "When ``True`` the frontend should gate the body behind a "
            "consent screen (Phase 5)."
        ),
    )
    translation: SourceTranslation = Field(
        ..., description="Metadata for the translation chosen by the server."
    )
    paragraphs: list[SourceParagraph] = Field(
        ...,
        description=(
            "Document body — parent-chunks in document order. Empty list "
            "is theoretically possible (work with no ingested instance) "
            "but caller should treat it as an error condition."
        ),
    )
