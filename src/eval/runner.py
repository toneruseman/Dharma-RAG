"""Run the retrieval pipeline over every golden item and aggregate metrics.

Two responsibilities, kept separate for clarity:

1. :func:`run_eval` — given a golden set + retrieval resources, runs
   ``hybrid_search`` over every query and returns a list of
   :class:`PerQueryResult`. No metric aggregation here — this step is
   pure data collection.

2. :func:`summarise` — given the list of per-query results, computes
   ``ref_hit@K`` / ``MRR`` overall and broken down by difficulty +
   language. Returns an :class:`EvalSummary` ready for rendering.

Why two passes (collect → summarise) rather than one
----------------------------------------------------
* The same per-query list feeds *both* the with-rerank and without-
  rerank summaries when run sequentially. Recomputing during
  aggregation is essentially free (microseconds), while running the
  pipeline twice would not be.
* Per-query records are useful artefacts on their own (CSV export,
  failure inspection) — keeping them as the canonical intermediate
  representation makes that easy.
* The summarisation is pure (no I/O, no model), so it gets unit tests
  without any pipeline plumbing.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.eval.golden import GoldenItem, GoldenSet
from src.eval.metrics import mean_reciprocal_rank, reciprocal_rank, ref_hit_at_k
from src.expand import FoundationalMatcher
from src.expand import expand_definitional as _expand_definitional
from src.processing.glossary import Glossary
from src.retrieval.hybrid import (
    EncoderProtocol,
    HybridHit,
    QdrantQueryProtocol,
    RerankerCallable,
    hybrid_search,
)

logger = logging.getLogger(__name__)

DEFAULT_EVAL_TOP_K: int = 20
"""Top-K we keep from each query for metric computation.

Slightly larger than the production API default (8) so we can compute
``ref_hit@10`` and ``ref_hit@20`` from the same single retrieval run.
"""

DEFAULT_K_VALUES: tuple[int, ...] = (1, 5, 10, 20)
"""Cut-offs reported by :func:`summarise`. The headline metric in the
plan is ``ref_hit@5``; the others are diagnostic — ``@1`` flags whether
the *very* top is right, ``@10/@20`` show recall headroom for reranker
analysis."""


@dataclass(frozen=True, slots=True)
class PerQueryResult:
    """Outcome of running a single golden query through the pipeline.

    ``retrieved_works`` is the ranked work-id list (best-first), used
    by :func:`summarise` to compute every metric. ``hits`` is the full
    :class:`HybridHit` list kept for human inspection (printing the
    actual chunk text when an item misses).
    """

    item: GoldenItem
    retrieved_works: tuple[str, ...]
    hits: tuple[HybridHit, ...]
    latency_s: float
    rerank_s: float


@dataclass(frozen=True, slots=True)
class MetricsBlock:
    """Aggregated metrics for one slice of the eval (overall or breakdown)."""

    n: int
    ref_hit_at_k: dict[int, float]
    mrr: float


@dataclass(frozen=True, slots=True)
class EvalSummary:
    """Full report ready to render to console or markdown.

    ``label`` is e.g. ``"rerank=False"`` / ``"rerank=True"`` — set by
    the caller so a side-by-side table can be printed.
    """

    label: str
    overall: MetricsBlock
    by_difficulty: dict[str, MetricsBlock]
    by_language: dict[str, MetricsBlock]
    total_latency_s: float
    total_rerank_s: float


async def run_eval(
    *,
    golden: GoldenSet,
    encoder: EncoderProtocol,
    qdrant_client: QdrantQueryProtocol,
    db_session: AsyncSession,
    reranker: RerankerCallable | None,
    rerank: bool,
    top_k: int = DEFAULT_EVAL_TOP_K,
    collection_name: str | None = None,
    expand_parents: bool | None = None,
    glossary: Glossary | None = None,
    glossary_max_meanings: int = 1,
    foundational_matcher: FoundationalMatcher | None = None,
    expand_definitional: bool = False,
) -> list[PerQueryResult]:
    """Run ``hybrid_search`` over every item in ``golden`` and collect results.

    Sequential by design — the pipeline already parallelises its three
    channels per query, and 30 queries × 7s each is small enough that
    extra machinery (bounded gather, per-query backpressure) would just
    obscure failures.

    Parameters
    ----------
    rerank:
        Toggle for the cross-encoder pass. Both modes share the same
        encoder + Qdrant + DB session — only the final stage differs.
    top_k:
        Forwarded to ``hybrid_search``. Default 20.
    collection_name:
        Qdrant collection. ``None`` (default) uses ``hybrid_search``'s own
        default. Day-17 A/B passes ``"dharma_v2"``.
    expand_parents:
        Day-22 ablation knob. ``None`` (default) inherits the
        ``hybrid_search`` default (currently True after the day-18
        cutover). Pass ``False`` to evaluate child-only retrieval and
        measure the contribution of small-to-big expansion.
    glossary:
        Day-23 ablation knob. When provided, each item's query is
        rewritten via :meth:`Glossary.expand_query` *before* being
        encoded — same code path the production ``RAGService`` uses
        when ``expand_pali=True``. ``None`` (default) means no
        rewrite, eval mirrors the no-glossary baseline.
    glossary_max_meanings:
        Day-23 tuning knob — forwarded to ``expand_query``. ``2``
        matches the production default. ``1`` limits noise from
        long synonym chains; ``0`` adds only the canonical Pāli
        lemma without any EN/RU translation. Ignored when
        ``glossary`` is None.
    foundational_matcher:
        Day-32 ablation knob (rag-day-28+29+30 stack). When provided,
        every query is matched against the curated foundational map
        (``data/glossary/foundational.yaml``); on hit, the matcher's
        ``apply_boost`` callable is passed to ``hybrid_search`` for
        post-RRF score boost, and English aliases are appended to the
        BM25 channel via ``or``-clauses. Mirrors the production code
        path in :class:`src.rag.service.RAGService.query`.
    expand_definitional:
        Day-32 ablation knob (rag-day-28). When ``True``, every query
        is rewritten through the definitional template before the
        Pāli glossary expansion (``"What is X?"`` →
        ``"What is X? Discourse on X. Foundations of X. ..."``). When
        ``foundational_matcher`` is also set, the matcher's term
        aliases are passed to ``expand_definitional`` so the gloss
        also includes English descriptive phrases (mirrors
        production). ``False`` (default) means no rewrite.
    """
    results: list[PerQueryResult] = []
    # Forward only the kwargs the caller cared to override — keeps the
    # call site honest about which knobs are exercised in this run.
    extra: dict[str, object] = {}
    if collection_name is not None:
        extra["collection_name"] = collection_name
    if expand_parents is not None:
        extra["expand_parents"] = expand_parents
    # Pre-compute term_aliases once if both knobs active — avoids
    # rebuilding the dict per query.
    term_aliases: dict[str, list[str]] | None = None
    if expand_definitional and foundational_matcher is not None:
        term_aliases = {e.term: list(e.aliases) for e in foundational_matcher.entries}
    for idx, item in enumerate(golden.items, start=1):
        t0 = time.perf_counter()
        # Mirror RAGService.query() ordering: definitional → Pāli → encode.
        encoded_query = item.query
        if expand_definitional:
            encoded_query = _expand_definitional(item.query, term_aliases=term_aliases)
        if glossary is not None:
            encoded_query = glossary.expand_query(encoded_query, max_meanings=glossary_max_meanings)
        # BM25 sees raw query + foundational English aliases (rag-day-29
        # bridge). Encoder sees expanded gloss.
        bm25_query: str | None = None
        boost_callable = None
        if foundational_matcher is not None:
            matcher: FoundationalMatcher = foundational_matcher
            match = matcher.match(item.query)
            if match.boost_by_work:
                aliases = matcher.bm25_aliases(item.query)
                if aliases:
                    clauses = [item.query] + [f'"{a}"' if " " in a else a for a in aliases]
                    bm25_query = " or ".join(clauses)

                def _apply_boost(
                    hits: list[HybridHit],
                    _matcher: FoundationalMatcher = matcher,
                    _q: str = item.query,
                ) -> list[HybridHit]:
                    return _matcher.apply_boost(hits, _q)

                boost_callable = _apply_boost
        if bm25_query is not None:
            extra["bm25_query"] = bm25_query
        elif "bm25_query" in extra:
            extra.pop("bm25_query")
        if boost_callable is not None:
            extra["apply_post_fusion_boost"] = boost_callable
        elif "apply_post_fusion_boost" in extra:
            extra.pop("apply_post_fusion_boost")
        hits, timings = await hybrid_search(
            query=encoded_query,
            encoder=encoder,
            qdrant_client=qdrant_client,
            db_session=db_session,
            reranker=reranker,
            top_k=top_k,
            rerank=rerank,
            **extra,  # type: ignore[arg-type]
        )
        elapsed = time.perf_counter() - t0
        retrieved_works = tuple(h.work_canonical_id for h in hits)
        results.append(
            PerQueryResult(
                item=item,
                retrieved_works=retrieved_works,
                hits=tuple(hits),
                latency_s=timings.total_s,
                rerank_s=timings.rerank_s,
            )
        )
        logger.info(
            "eval %2d/%d  rerank=%s  id=%s  hit_top1=%s  latency=%.2fs",
            idx,
            len(golden.items),
            rerank,
            item.id,
            retrieved_works[:1] and retrieved_works[0] in set(item.expected_works),
            elapsed,
        )
    return results


def summarise(
    results: Sequence[PerQueryResult],
    *,
    label: str,
    k_values: Sequence[int] = DEFAULT_K_VALUES,
) -> EvalSummary:
    """Aggregate per-query results into overall + breakdown metrics."""
    by_difficulty: dict[str, list[PerQueryResult]] = {}
    by_language: dict[str, list[PerQueryResult]] = {}
    for r in results:
        by_difficulty.setdefault(r.item.difficulty, []).append(r)
        by_language.setdefault(r.item.language, []).append(r)

    return EvalSummary(
        label=label,
        overall=_metrics_block(results, k_values),
        by_difficulty={k: _metrics_block(v, k_values) for k, v in sorted(by_difficulty.items())},
        by_language={k: _metrics_block(v, k_values) for k, v in sorted(by_language.items())},
        total_latency_s=sum(r.latency_s for r in results),
        total_rerank_s=sum(r.rerank_s for r in results),
    )


def _metrics_block(
    results: Sequence[PerQueryResult],
    k_values: Sequence[int],
) -> MetricsBlock:
    """Compute one ``MetricsBlock`` for a slice of results."""
    if not results:
        return MetricsBlock(
            n=0,
            ref_hit_at_k={k: 0.0 for k in k_values},
            mrr=0.0,
        )

    ref_hits: dict[int, float] = {}
    for k in k_values:
        hits = sum(ref_hit_at_k(r.retrieved_works, r.item.expected_works, k=k) for r in results)
        ref_hits[k] = hits / len(results)

    rrs = [reciprocal_rank(r.retrieved_works, r.item.expected_works) for r in results]
    return MetricsBlock(
        n=len(results),
        ref_hit_at_k=ref_hits,
        mrr=mean_reciprocal_rank(rrs),
    )


__all__ = [
    "DEFAULT_EVAL_TOP_K",
    "DEFAULT_K_VALUES",
    "EvalSummary",
    "MetricsBlock",
    "PerQueryResult",
    "run_eval",
    "summarise",
]
