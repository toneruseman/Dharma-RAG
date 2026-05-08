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
from src.rag.schemas import (
    PipelineMetadata,
    QueryRequest,
    QueryResponse,
    Source,
    SourceDocument,
    SourceParagraph,
    SourceTranslation,
    ThreadCard,
    ThreadRequest,
    ThreadResponse,
)

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


# Reading-Room fixtures — full documents for the same three works.
# Paragraph text is intentionally believable but tagged with a
# "[stub fixture]" suffix so a frontend dev can never mistake it for
# the real corpus. Author / year / license fields use real public
# metadata about Bhikkhu Sujato's translations on SuttaCentral.
_FIXTURE_DOCUMENTS: dict[str, SourceDocument] = {
    "mn10": SourceDocument(
        canonical_id="mn10",
        title="The Establishings of Mindfulness",
        title_pali="Satipaṭṭhāna Sutta",
        tradition_code="theravada",
        is_restricted=False,
        translation=SourceTranslation(
            author="Bhikkhu Sujato",
            language_code="eng",
            title="The Establishings of Mindfulness",
            publication_year=2018,
            license="CC0",
        ),
        paragraphs=[
            SourceParagraph(
                sequence=0,
                segment_id="mn10:1.1",
                text=(
                    "So I have heard. At one time the Buddha was staying in the land of "
                    "the Kurus, near the Kuru town named Kammāsadhamma. There the Buddha "
                    "addressed the mendicants, “Mendicants!” [stub fixture]"
                ),
            ),
            SourceParagraph(
                sequence=1,
                segment_id="mn10:2.1",
                text=(
                    "“Mendicants, the four kinds of mindfulness meditation are the path "
                    "to convergence. They are in order to purify sentient beings, to get "
                    "past sorrow and crying, to make an end of pain and sadness, to find "
                    "the way, to realize extinguishment. [stub fixture]"
                ),
            ),
            SourceParagraph(
                sequence=2,
                segment_id="mn10:8.1",
                text=(
                    "And how does a mendicant meditate by observing an aspect of the body? "
                    "It’s when a mendicant — gone to a wilderness, the root of a tree, or "
                    "an empty hut — sits down cross-legged, sets their body straight, and "
                    "establishes mindfulness in their presence. Just mindful, they breathe "
                    "in. Mindful, they breathe out. [stub fixture]"
                ),
            ),
            SourceParagraph(
                sequence=3,
                segment_id="mn10:46.1",
                text=(
                    "Whoever develops these four kinds of mindfulness meditation in this "
                    "way for seven years can expect one of two results: enlightenment in "
                    "the present life, or, if there’s a residue, non-return. [stub fixture]"
                ),
            ),
        ],
    ),
    "sn56.11": SourceDocument(
        canonical_id="sn56.11",
        title="Rolling Forth the Wheel of Dhamma",
        title_pali="Dhammacakkappavattana Sutta",
        tradition_code="theravada",
        is_restricted=False,
        translation=SourceTranslation(
            author="Bhikkhu Sujato",
            language_code="eng",
            title="Rolling Forth the Wheel of Dhamma",
            publication_year=2018,
            license="CC0",
        ),
        paragraphs=[
            SourceParagraph(
                sequence=0,
                segment_id="sn56.11:1.1",
                text=(
                    "So I have heard. At one time the Buddha was staying near Varanasi, "
                    "in the deer park at Isipatana. There the Buddha addressed the group "
                    "of five mendicants: [stub fixture]"
                ),
            ),
            SourceParagraph(
                sequence=1,
                segment_id="sn56.11:5.2",
                text=(
                    "“Now this, mendicants, is the noble truth of suffering. Rebirth is "
                    "suffering; old age is suffering; illness is suffering; death is "
                    "suffering; association with the disliked is suffering; separation "
                    "from the liked is suffering; not getting what you wish for is "
                    "suffering. In brief, the five grasping aggregates are suffering. "
                    "[stub fixture]"
                ),
            ),
            SourceParagraph(
                sequence=2,
                segment_id="sn56.11:6.1",
                text=(
                    "Now this, mendicants, is the noble truth of the origin of suffering. "
                    "It’s the craving that leads to future lives, mixed up with relishing "
                    "and greed, taking pleasure wherever it lands. That is, craving for "
                    "sensual pleasures, craving to continue existence, and craving to end "
                    "existence. [stub fixture]"
                ),
            ),
        ],
    ),
    "dn22": SourceDocument(
        canonical_id="dn22",
        title="The Longer Discourse on Mindfulness Meditation",
        title_pali="Mahāsatipaṭṭhāna Sutta",
        tradition_code="theravada",
        is_restricted=False,
        translation=SourceTranslation(
            author="Bhikkhu Sujato",
            language_code="eng",
            title="The Longer Discourse on Mindfulness Meditation",
            publication_year=2018,
            license="CC0",
        ),
        paragraphs=[
            SourceParagraph(
                sequence=0,
                segment_id="dn22:1.1",
                text=(
                    "So I have heard. At one time the Buddha was staying in the land of "
                    "the Kurus, near the Kuru town named Kammāsadhamma. There the Buddha "
                    "addressed the mendicants: [stub fixture]"
                ),
            ),
            SourceParagraph(
                sequence=1,
                segment_id="dn22:1.4",
                text=(
                    "“Mendicants, the four kinds of mindfulness meditation are the path "
                    "to convergence. They are for the purification of sentient beings, "
                    "for getting past sorrow and crying, for making an end of pain and "
                    "sadness, for finding the right way, for realizing extinguishment. "
                    "[stub fixture]"
                ),
            ),
        ],
    ),
}


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

    async def thread_next(self, request: ThreadRequest) -> ThreadResponse:
        # Map the fixture sources onto a deterministic stable chunk_id
        # space so the client's excluded-list dedup works across rounds.
        # Same shape as production: 3 cards available → after exclusions
        # the rest are ``exhausted=True``.
        excluded = set(request.excluded_chunk_ids or [])
        all_cards = [
            ThreadCard(
                chunk_id=f"stub-chunk-{i}",
                work_canonical_id=src.work_canonical_id,
                segment_id=src.segment_id,
                text=src.text,
                context_text=(
                    f"This passage from {src.work_canonical_id.upper()} "
                    "introduces a key Buddhist teaching. [stub context_text]"
                ),
                translator="sujato",
                language_code="eng",
                score=src.score,
            )
            for i, src in enumerate(_FIXTURE_SOURCES)
        ]
        fresh = [c for c in all_cards if c.chunk_id not in excluded]
        cards = fresh[: request.top_k]
        return ThreadResponse(
            query=request.query,
            cards=cards,
            exhausted=len(cards) < request.top_k,
            latency_ms=1.0,
        )

    async def get_source(self, canonical_id: str) -> SourceDocument | None:
        # Three fixture documents available; everything else returns
        # None so the router maps it to 404. Frontend dev exercises the
        # not-found code path by hitting any other ID (e.g. ``/read/foo``).
        return _FIXTURE_DOCUMENTS.get(canonical_id)


__all__ = ["StubRAGService"]
