"""RAG service — wraps hybrid retrieval behind the ``/api/query`` contract.

Responsibilities:

* Resolve server-side defaults (``settings.retrieval_collection``,
  ``retrieval_rerank_default``, ``retrieval_expand_parents_default``)
  so callers never see them.
* Apply post-RRF filters (``forbidden_works``).
* Map :class:`HybridHit` to the public :class:`Source` shape, dropping
  internal diagnostic fields.
* Normalise the relevance score to ``[0, 1]``.
* Build the :class:`PipelineMetadata` so consumers can reason about
  which pipeline produced the answer.

Why a class rather than a free function:

* The encoder, Qdrant client, reranker, and DB session-maker are
  long-lived resources. Holding them on a service instance keeps the
  endpoint signature small and matches the layering on the retrieval
  side (resources owned by ``RetrievalResources``).
* When app-day-02 freezes ``src/rag/schemas.py`` for App-track, the
  RAGService class is the natural protocol-implementation point.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sqlalchemy as sa
from qdrant_client import QdrantClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import Settings, get_settings
from src.db.models.frbr import Chunk, Expression, Instance, Work
from src.db.models.lookups import Author
from src.embeddings.bge_m3 import BGEM3Encoder
from src.expand import FoundationalMatcher, expand_definitional
from src.processing.glossary import Glossary
from src.rag.schemas import (
    PipelineMetadata,
    QueryRequest,
    QueryResponse,
    Source,
    SourceDocument,
    SourceParagraph,
    SourceTranslation,
)
from src.retrieval.hybrid import hybrid_search
from src.retrieval.reranker import BGEReranker
from src.retrieval.schemas import HybridHit

logger = logging.getLogger(__name__)


def _normalise_score(hit: HybridHit, top_rrf_score: float) -> float:
    """Map an internal hit score onto ``[0, 1]`` for the public contract.

    * Reranker scores: BGE-reranker emits raw cross-encoder logits in a
      wide unbounded range. Sigmoid is the standard mapping (matches
      what BGE-reranker scripts use for cosine-like display).
    * RRF scores: bounded above by the sum of ``1/(k+rank)`` across
      channels, but the practical maximum is query-dependent. Scaling
      by the top hit's RRF score gives a within-response 0-1 ranking
      and avoids exposing the tuning constant ``k``.

    Either way, the normalised score is a *within-response* relative
    measure, not a calibrated probability. The Source.score docstring
    spells this out for clients.
    """
    if hit.rerank_score is not None:
        return 1.0 / (1.0 + math.exp(-hit.rerank_score))
    if top_rrf_score <= 0:
        return 0.0
    return min(1.0, max(0.0, hit.rrf_score / top_rrf_score))


def _build_version_string(
    *,
    collection: str,
    rerank: bool,
    expand_parents: bool,
    expand_pali: bool,
    expand_definitional: bool,
    foundational_boost: bool,
) -> str:
    """Compose the pipeline version label embedded in PipelineMetadata.

    Compact format chosen so logs and Phoenix span attributes stay
    grep-able. Example: ``dharma_v2-rerank0-parents1-pali1-defn1-fnd1``.
    """
    return (
        f"{collection}-rerank{int(rerank)}-parents{int(expand_parents)}"
        f"-pali{int(expand_pali)}"
        f"-defn{int(expand_definitional)}"
        f"-fnd{int(foundational_boost)}"
    )


def _hit_to_source(hit: HybridHit, *, score: float) -> Source:
    """Drop diagnostic fields, keep only what the public contract exposes."""
    snippet = hit.child_text if hit.child_text is not None else hit.text
    return Source(
        work_canonical_id=hit.work_canonical_id,
        segment_id=hit.segment_id,
        text=hit.text,
        snippet=snippet,
        score=score,
    )


class RAGService:
    """Production retrieval entrypoint.

    Owns no per-request state — safe to share one instance across all
    requests (the underlying resources are themselves shared).
    """

    def __init__(
        self,
        *,
        encoder: BGEM3Encoder,
        qdrant_client: QdrantClient,
        reranker: BGEReranker,
        session_maker: async_sessionmaker[AsyncSession],
        settings: Settings | None = None,
        glossary: Glossary | None = None,
        foundational_matcher: FoundationalMatcher | None = None,
    ) -> None:
        self._encoder = encoder
        self._qdrant = qdrant_client
        self._reranker = reranker
        self._session_maker = session_maker
        self._settings = settings or get_settings()
        self._glossary = glossary
        self._foundational = foundational_matcher

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[AsyncSession]:
        async with self._session_maker() as session:
            yield session

    async def query(self, request: QueryRequest) -> QueryResponse:
        """Run the full RAG retrieval pipeline and return the public response."""
        start = time.perf_counter()
        settings = self._settings
        collection = settings.retrieval_collection
        rerank = settings.retrieval_rerank_default
        expand_parents = settings.retrieval_expand_parents_default

        # Definitional expansion (rag-day-28). Runs *before* Pāli
        # expansion: the regex anchors on the raw user query
        # (``^What is X?$``), and Pāli expansion would append meanings
        # that break the anchor. Order: definitional → Pāli → encode.
        # See docs/concepts/28-definitional-expansion.md.
        # When the foundational matcher is loaded we also pass term
        # aliases — bridges bare-Pāli terms to English descriptive
        # phrases that match canonical sutta chunk text (``satipaṭṭhāna``
        # → "four foundations of mindfulness").
        expand_definitional_requested = (
            request.expand_definitional
            if request.expand_definitional is not None
            else settings.glossary_expand_definitional_default
        )
        expand_definitional_effective = False
        encoded_query = request.query
        if expand_definitional_requested:
            term_aliases = (
                {e.term: list(e.aliases) for e in self._foundational.entries}
                if self._foundational is not None
                else None
            )
            after_definitional = expand_definitional(request.query, term_aliases=term_aliases)
            if after_definitional != request.query:
                encoded_query = after_definitional
                expand_definitional_effective = True

        # Effective Pāli expansion: request override wins, else server
        # default. Skipped if no glossary is loaded — graceful fallback
        # so a missing dpd_full.json doesn't break the endpoint.
        # Operates on the (possibly definitional-expanded) text.
        expand_pali_requested = (
            request.expand_pali
            if request.expand_pali is not None
            else settings.glossary_expand_pali_default
        )
        expand_pali_effective = False
        if expand_pali_requested and self._glossary is not None:
            expanded = self._glossary.expand_query(encoded_query)
            if expanded != encoded_query:
                encoded_query = expanded
                expand_pali_effective = True

        # Foundational boost (rag-day-28). Captures matcher + raw user
        # query in a closure handed to ``hybrid_search`` for post-RRF
        # score multiplication on canonical works of curated terms.
        # Match runs against the *original* user query to avoid
        # accidental term inflation from the gloss template.
        foundational_requested = (
            request.foundational_boost
            if request.foundational_boost is not None
            else settings.glossary_foundational_boost_default
        )
        foundational_effective = False
        boost_callable = None
        if foundational_requested and self._foundational is not None:
            match_result = self._foundational.match(request.query)
            if match_result.boost_by_work:
                foundational_effective = True
                matcher_query = request.query

                def _apply_boost(hits: list[HybridHit]) -> list[HybridHit]:
                    assert self._foundational is not None  # narrowed above
                    return self._foundational.apply_boost(hits, matcher_query)

                boost_callable = _apply_boost

        # BM25 receives the *un-expanded* query so Postgres FTS keeps
        # precision on the raw term — we only sweeten the encoder-side
        # input. Raw user query is the safest BM25 source.
        # Exception (rag-day-29): when the foundational matcher fires on
        # a Pāli term that Sujato translates to English (`dukkha`/
        # `anatta`/`metta`), body text never contains the Pāli word —
        # BM25 returns 0 hits regardless of fold. Append English aliases
        # as ``OR`` clauses so FTS can match the translated form.
        # Diagnostic confirmed: BM25(``suffering``) ranks sn56.11 #1,
        # BM25(``not-self``) ranks sn22.59 #3 — exactly the works the
        # bare Pāli token misses.
        bm25_query = request.query
        if foundational_requested and self._foundational is not None:
            bm25_aliases = self._foundational.bm25_aliases(request.query)
            if bm25_aliases:
                # ``websearch_to_tsquery`` accepts lowercase ``or`` as
                # disjunction and ``"phrase"`` for phrase match.
                clauses = [request.query] + [f'"{a}"' if " " in a else a for a in bm25_aliases]
                bm25_query = " or ".join(clauses)

        async with self._session() as session:
            hits, _timings = await hybrid_search(
                query=encoded_query,
                bm25_query=bm25_query,
                encoder=self._encoder,
                qdrant_client=self._qdrant,
                db_session=session,
                reranker=self._reranker,
                top_k=request.top_k,
                rerank=rerank,
                collection_name=collection,
                expand_parents=expand_parents,
                apply_post_fusion_boost=boost_callable,
            )

        n_candidates = len(hits)
        if request.forbidden_works:
            forbidden = set(request.forbidden_works)
            hits = [h for h in hits if h.work_canonical_id not in forbidden]

        top_rrf_score = max((h.rrf_score for h in hits), default=0.0)
        sources = [_hit_to_source(h, score=_normalise_score(h, top_rrf_score)) for h in hits]

        latency_ms = (time.perf_counter() - start) * 1000.0
        return QueryResponse(
            query=request.query,
            sources=sources,
            latency_ms=latency_ms,
            metadata=PipelineMetadata(
                version=_build_version_string(
                    collection=collection,
                    rerank=rerank,
                    expand_parents=expand_parents,
                    expand_pali=expand_pali_effective,
                    expand_definitional=expand_definitional_effective,
                    foundational_boost=foundational_effective,
                ),
                collection=collection,
                rerank=rerank,
                expand_parents=expand_parents,
                expand_pali=expand_pali_effective,
                expand_definitional=expand_definitional_effective,
                foundational_boost=foundational_effective,
                n_candidates=n_candidates,
            ),
        )

    async def get_source(self, canonical_id: str) -> SourceDocument | None:
        """Fetch the full document for ``canonical_id`` (e.g. ``mn10``).

        Strategy: pick **one** translation deterministically — English
        first (``language_code='eng'``), then by ``publication_year``
        descending, falling back to creation order. Pick the **latest**
        Instance of that Expression by ``retrieved_at``. Return all
        parent-chunks of that Instance in document order.

        ``None`` when the work is not in the corpus or has no ingested
        instance yet — router maps to 404.
        """
        async with self._session() as session:
            work = (
                await session.execute(sa.select(Work).where(Work.canonical_id == canonical_id))
            ).scalar_one_or_none()
            if work is None:
                return None

            # English first, then most recent translation, then creation
            # order. Joined with Author so we can render the translator
            # name without a second round-trip.
            row = (
                await session.execute(
                    sa.select(Expression, Author)
                    .outerjoin(Author, Expression.author_id == Author.id)
                    .where(Expression.work_id == work.id)
                    .order_by(
                        sa.case((Expression.language_code == "eng", 0), else_=1),
                        Expression.publication_year.desc().nullslast(),
                        Expression.created_at.asc(),
                    )
                    .limit(1)
                )
            ).first()
            if row is None:
                logger.warning(
                    "rag.get_source.no_expression",
                    extra={"canonical_id": canonical_id},
                )
                return None
            expression, author = row

            instance = (
                await session.execute(
                    sa.select(Instance)
                    .where(Instance.expression_id == expression.id)
                    .order_by(Instance.retrieved_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if instance is None:
                logger.warning(
                    "rag.get_source.no_instance",
                    extra={"canonical_id": canonical_id},
                )
                return None

            chunks = (
                (
                    await session.execute(
                        sa.select(Chunk)
                        .where(
                            Chunk.instance_id == instance.id,
                            Chunk.is_parent.is_(True),
                        )
                        .order_by(Chunk.sequence.asc())
                    )
                )
                .scalars()
                .all()
            )

        return SourceDocument(
            canonical_id=work.canonical_id,
            title=work.title,
            title_pali=work.title_pali,
            tradition_code=work.tradition_code,
            is_restricted=work.is_restricted,
            translation=SourceTranslation(
                author=author.name if author is not None else None,
                language_code=expression.language_code,
                title=expression.title,
                publication_year=expression.publication_year,
                license=expression.license,
            ),
            paragraphs=[
                SourceParagraph(
                    sequence=chunk.sequence,
                    segment_id=chunk.segment_id,
                    text=chunk.text,
                )
                for chunk in chunks
            ],
        )
