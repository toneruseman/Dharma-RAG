"""In-memory ``StubRAGService`` for development without a real RAG backend.

Used when ``RAG_BACKEND=stub`` (see ``src.config.Settings.rag_backend``).
The fixture data below is small but real-shape: the response is a
fully valid :class:`QueryResponse` so frontend code that consumes it
exercises the same parsing path as in production.

Why a separate module under ``src.api`` and not ``src.rag``: the stub
is a *deployment* concern, not a library concept. ``src.rag`` is the
public contract surface; the stub is one of two ways the FastAPI app
can fulfil it.
"""

from __future__ import annotations

from src.rag.protocol import RAGServiceProtocol
from src.rag.schemas import PipelineMetadata, QueryRequest, QueryResponse, Source

# Three plausible Buddhist-canon sources covering distinct topics so a
# frontend mock-up shows variety. ``score`` values are illustrative —
# they're not produced by any real metric, just sorted high → low.
_FIXTURE_SOURCES: tuple[Source, ...] = (
    Source(
        work_canonical_id="mn10",
        segment_id="mn10:8.1",
        text=(
            "And how, mendicants, do mendicants live observing an aspect "
            "of the body? It's when a mendicant — gone to a wilderness, "
            "the root of a tree, or an empty hut — sits down cross-legged, "
            "sets their body straight, and establishes mindfulness in "
            "their presence. Just mindful, they breathe in. Mindful, "
            "they breathe out. [stub fixture — Satipaṭṭhāna Sutta]"
        ),
        snippet=("Just mindful, they breathe in. Mindful, they breathe out."),
        score=0.92,
    ),
    Source(
        work_canonical_id="sn56.11",
        segment_id="sn56.11:5.2",
        text=(
            "Now this, mendicants, is the noble truth of suffering. Birth "
            "is suffering, old age is suffering, illness is suffering, "
            "death is suffering; sorrow, lamentation, pain, grief, and "
            "despair are suffering; union with the disliked is suffering; "
            "separation from the liked is suffering; not getting what one "
            "wants is suffering. [stub fixture — Dhammacakkappavattana]"
        ),
        snippet=("Now this, mendicants, is the noble truth of suffering."),
        score=0.81,
    ),
    Source(
        work_canonical_id="dn22",
        segment_id="dn22:1.4",
        text=(
            "There is, mendicants, this one way for the purification of "
            "beings, for getting past sorrow and lamentation, for the "
            "ending of pain and sadness, for finding the right path, for "
            "realising extinguishment — that is, the four kinds of "
            "mindfulness meditation. [stub fixture — Mahāsatipaṭṭhāna]"
        ),
        snippet=("the four kinds of mindfulness meditation"),
        score=0.74,
    ),
)


class StubRAGService(RAGServiceProtocol):
    """In-memory implementation: same shape, hardcoded payload, ~1 ms.

    Returns the same fixture sources for every query (clipped to
    ``request.top_k``). The point is the *shape*, not the relevance —
    real-quality retrieval lives in :class:`src.rag.service.RAGService`.
    """

    async def query(self, request: QueryRequest) -> QueryResponse:
        # forbidden_works post-filter still applied so the contract
        # behaves identically — frontend dev sees an empty list when
        # they pass `forbidden_works=["mn10", "sn56.11", "dn22"]`,
        # exactly like production.
        sources = list(_FIXTURE_SOURCES)
        if request.forbidden_works:
            forbidden = set(request.forbidden_works)
            sources = [s for s in sources if s.work_canonical_id not in forbidden]
        sources = sources[: request.top_k]

        return QueryResponse(
            query=request.query,
            sources=sources,
            latency_ms=1.0,
            metadata=PipelineMetadata(
                version="stub-v1",
                collection="stub",
                rerank=False,
                expand_parents=False,
                expand_pali=False,
                n_candidates=len(_FIXTURE_SOURCES),
            ),
        )


__all__ = ["StubRAGService"]
