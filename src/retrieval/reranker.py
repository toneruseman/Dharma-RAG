"""BGE-reranker-v2-m3 — second-stage cross-encoder for retrieval.

Why a separate stage on top of day-12 hybrid RRF
------------------------------------------------
Day-12 retrieval is a *bi-encoder* pipeline: query and chunks are
encoded independently, then compared by vector geometry. This is
fast (one query encode + one Qdrant lookup) but only roughly orders
candidates. A *cross-encoder* takes the (query, chunk) pair as a
single concatenated input and computes a richer relevance score —
~5-15 percentage points more accurate on standard benchmarks but
N times slower (one forward pass per pair).

We use the bi-encoder to *recall* (top-30 candidates from 6,478
chunks in ~70 ms) and the cross-encoder to *precision-rerank* the
shortlist (top-30 → top-8 in ~50-150 ms on a 1080 Ti). The cost of
running the cross-encoder over the entire corpus would be
~30 minutes per query — unworkable. Two-stage funnel keeps us in
real-time territory.

Model
-----
``BAAI/bge-reranker-v2-m3`` — same family as our BGE-M3 encoder,
multilingual (100+ languages, including Russian against English),
~568M parameters, ~1.1 GB weights. Output is a single relevance
score per (query, chunk) pair — no normalisation, higher = more
relevant.

Design
------
* **Lazy load.** Weights are pulled from HuggingFace only on the
  first ``rerank`` call. Importing the module costs nothing.
* **Thread-safe lazy init** via ``threading.Lock`` — same pattern as
  :class:`src.embeddings.bge_m3.BGEM3Encoder`.
* **Pure DI.** Tests inject a ``FakeReranker`` satisfying
  :class:`RerankerProtocol` instead of loading 1.1 GB. No torch
  import is required by the unit suite.
* **fp16 on GPU only.** Pascal architecture (1080 Ti) has no Tensor
  Cores; fp16 on CPU gives no speed-up and may hurt quality. Mirror
  the BGE-M3 encoder's auto-selection rule.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import UUID

logger = logging.getLogger(__name__)

MODEL_NAME: str = "BAAI/bge-reranker-v2-m3"


class RerankerProtocol(Protocol):
    """Structural type matching ``FlagEmbedding.FlagReranker.compute_score``.

    We declare the protocol rather than importing the concrete class so
    the unit test suite stays free of torch + FlagEmbedding imports
    (they would add seconds to pytest collection and pull a 2 GB dep).
    The real model satisfies this protocol by virtue of its
    ``compute_score`` signature.
    """

    def compute_score(
        self,
        sentence_pairs: Sequence[Sequence[str]],
        *,
        batch_size: int = ...,
        max_length: int = ...,
        normalize: bool = ...,
    ) -> list[float] | float: ...


@dataclass(frozen=True, slots=True)
class CandidateForRerank:
    """One candidate pair shipped to the reranker.

    The orchestrator (:mod:`src.retrieval.hybrid`) builds these from
    the post-RRF enriched results: ``chunk_id`` for downstream
    payload look-up, ``text`` for the actual cross-encoder input,
    ``rrf_rank`` for observability so we can later tell *how much*
    the reranker reordered things.
    """

    chunk_id: UUID
    text: str
    rrf_rank: int


@dataclass(frozen=True, slots=True)
class RerankedHit:
    """One scored candidate after the reranker pass.

    ``score`` is the raw reranker output (not bounded — typically in
    the [-10, 10] range for our model). The orchestrator sorts by
    descending score and truncates to ``top_k``.
    """

    chunk_id: UUID
    score: float
    rrf_rank: int


class BGEReranker:
    """Device-aware BGE-reranker-v2-m3 wrapper with lazy model load.

    Designed to be a singleton in the FastAPI app (one instance shared
    across all requests) — see :class:`src.api.retrieve.RetrievalResources`.

    Parameters
    ----------
    device:
        ``"auto"`` / ``"cuda"`` / ``"cpu"``. ``"auto"`` picks CUDA if
        available, falls back to CPU.
    use_fp16:
        ``None`` (default) → auto: fp16 on CUDA, fp32 on CPU.
        ``True``/``False`` overrides.
    model_name:
        HuggingFace repo. Defaults to ``BAAI/bge-reranker-v2-m3``.
    model_factory:
        Test injection point. Production leaves this ``None``.
    """

    def __init__(
        self,
        *,
        device: str = "auto",
        use_fp16: bool | None = None,
        model_name: str = MODEL_NAME,
        model_factory: Callable[[str, str, bool], RerankerProtocol] | None = None,
    ) -> None:
        self._device = device
        self._use_fp16 = use_fp16
        self._model_name = model_name
        self._model_factory = model_factory or _default_model_factory
        self._model: RerankerProtocol | None = None
        self._resolved_device: str | None = None
        self._resolved_fp16: bool | None = None
        self._load_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rerank(
        self,
        query: str,
        candidates: Sequence[CandidateForRerank],
        *,
        top_k: int,
        batch_size: int = 32,
        max_length: int = 1024,
    ) -> list[RerankedHit]:
        """Score every candidate against the query, return top-K by score.

        Parameters
        ----------
        query:
            Free-form user query. Empty string returns ``[]`` without
            loading the model — mirrors :func:`bm25.search` semantics.
        candidates:
            List of :class:`CandidateForRerank`. Empty list returns
            ``[]``.
        top_k:
            How many to return after reranking. If ``top_k`` exceeds
            the candidate count, all candidates are returned (sorted).
        batch_size:
            Internal cross-encoder batch. 32 is safe for 11 GB VRAM
            with fp16 and max_length=1024. Tune for bigger GPUs.
        max_length:
            Token budget for the (query + chunk) concatenation. Our
            child chunks are ~384 tokens, so 1024 covers everything
            with headroom for the query and special tokens.
        """
        if not query or not candidates or top_k <= 0:
            return []

        model = self._ensure_model()
        pairs: list[list[str]] = [[query, c.text] for c in candidates]

        raw_scores = model.compute_score(
            pairs,
            batch_size=batch_size,
            max_length=max_length,
            normalize=False,
        )
        # FlagReranker returns a single float when given one pair, or
        # a list otherwise. Normalise to a list.
        scores: list[float]
        if isinstance(raw_scores, int | float):
            scores = [float(raw_scores)]
        else:
            scores = [float(s) for s in raw_scores]

        if len(scores) != len(candidates):
            raise RuntimeError(
                f"Reranker returned {len(scores)} scores for "
                f"{len(candidates)} candidates — model output mismatch."
            )

        hits = [
            RerankedHit(chunk_id=c.chunk_id, score=s, rrf_rank=c.rrf_rank)
            for c, s in zip(candidates, scores, strict=True)
        ]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    @property
    def device(self) -> str:
        """Resolved device. Triggers model load on first access."""
        self._ensure_model()
        assert self._resolved_device is not None
        return self._resolved_device

    @property
    def uses_fp16(self) -> bool:
        self._ensure_model()
        assert self._resolved_fp16 is not None
        return self._resolved_fp16

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_model(self) -> RerankerProtocol:
        # Fast path without lock — common case after first load.
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is not None:
                return self._model
            device = _resolve_device(self._device)
            requested_fp16 = self._use_fp16 if self._use_fp16 is not None else True
            fp16 = requested_fp16 and device == "cuda"
            self._model = self._model_factory(self._model_name, device, fp16)
            self._resolved_device = device
            self._resolved_fp16 = fp16
            logger.info(
                "Reranker loaded: model=%s device=%s fp16=%s",
                self._model_name,
                device,
                fp16,
            )
            return self._model


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _resolve_device(requested: str) -> str:
    """Pick a torch device, preferring CUDA when available.

    Lazy-imports torch so test environments where torch is mocked can
    still call ``_resolve_device("cpu")`` without surprises. Mirrors
    the same helper in :mod:`src.embeddings.bge_m3` — kept duplicated
    rather than shared because cross-module helper imports from
    ``embeddings`` into ``retrieval`` would create a cycle.
    """
    if requested == "cpu":
        return "cpu"
    if requested in ("cuda", "auto"):
        try:
            import torch  # noqa: PLC0415

            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        if requested == "cuda":
            logger.warning(
                "CUDA requested but not available; reranker will run on CPU "
                "(~50-100x slower). Check torch.cuda.is_available()."
            )
        return "cpu"
    logger.warning("Unknown device %r; falling back to CPU.", requested)
    return "cpu"


def _default_model_factory(model_name: str, device: str, use_fp16: bool) -> RerankerProtocol:
    """Real BGE-reranker loader. Imported lazily to keep tests light."""
    from FlagEmbedding import FlagReranker  # noqa: PLC0415

    return cast(
        RerankerProtocol,
        FlagReranker(model_name, use_fp16=use_fp16, devices=device),
    )


def _scores_to_hits(
    candidates: Sequence[CandidateForRerank],
    scores: Sequence[float],
    top_k: int,
) -> list[RerankedHit]:
    """Helper kept public-ish for tests that want to bypass model calls."""
    if len(scores) != len(candidates):
        raise RuntimeError(
            f"Mismatched lengths: {len(scores)} scores, " f"{len(candidates)} candidates."
        )
    hits = [
        RerankedHit(chunk_id=c.chunk_id, score=float(s), rrf_rank=c.rrf_rank)
        for c, s in zip(candidates, scores, strict=True)
    ]
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:top_k]


# Keep ``Any`` quiet about top-level unused.
_: Any = None
