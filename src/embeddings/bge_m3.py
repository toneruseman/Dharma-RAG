"""BGE-M3 encoder — dense + sparse embeddings in one forward pass.

Why BGE-M3
----------
ADR-0001 picks BGE-M3 as the Phase 1 embedding model for three
reasons the alternatives (OpenAI, Cohere, Voyage, mpnet) cannot match
simultaneously:

* **Multilingual.** Trained on 100+ languages in parallel, so a
  Russian query matches an English sutta passage without a detour
  through a translation pipeline.
* **Multi-functional.** One forward pass returns both a dense
  semantic vector (1024 dim) and a sparse lexical vector (learned
  weights over vocabulary). That's the hybrid retrieval input the
  reranker needs on rag-day-12.
* **Open weights, local inference.** No per-query cost, no vendor
  lock-in, and we can fine-tune on Dharma-RAG's own golden set in
  Phase 2 (rag-day-36+).

ColBERT multi-vectors are also available from BGE-M3 but deferred —
they blow up storage (~N tokens × 1024 dim per chunk), and Phase 1
doesn't need them.

Design
------
The encoder is a thin wrapper with three responsibilities:

1. **Lazy model loading.** The ~2.3 GB BGE-M3 weights are only pulled
   into memory on the first ``encode`` call. Unit tests that mock the
   model never pay that cost.
2. **Device detection.** CUDA GPU > CPU. fp16 on GPU (halves VRAM),
   fp32 on CPU (Pascal/older cards have no Tensor Cores — fp16 gives
   no speed-up, only accuracy cost).
3. **Batch control.** Encoding is parallelisable; we accept a list
   and let the caller choose batch size so the embed step can be
   tuned to GPU memory without touching this module.

The production code path injects the real ``BGEM3FlagModel``. Tests
inject a fake via the ``model_factory`` parameter — no patching,
no import-time side effects.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

logger = logging.getLogger(__name__)

# Dense vectors are 1024-dim float32 for BGE-M3. We stash the constant
# here so downstream (Qdrant collection schema, Alembic migrations for
# app-layer caches) can reference a single source of truth.
DENSE_DIM: int = 1024
MODEL_NAME: str = "BAAI/bge-m3"


class BGEM3ModelProtocol(Protocol):
    """Structural type matching the real ``BGEM3FlagModel.encode`` API.

    We duck-type rather than importing the class at module load so
    unit tests don't drag in torch + FlagEmbedding (~2 GB of deps).
    The real model satisfies this Protocol by virtue of its
    ``encode`` method signature.
    """

    def encode(
        self,
        sentences: list[str] | str,
        *,
        batch_size: int = ...,
        max_length: int = ...,
        return_dense: bool = ...,
        return_sparse: bool = ...,
        return_colbert_vecs: bool = ...,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class EncodedBatch:
    """Output of a single ``encode`` call.

    ``dense`` is a list (not np.ndarray) so callers without numpy as a
    hard dep can still consume it. Qdrant client takes plain Python
    floats happily.

    ``sparse`` is BGE-M3's ``lexical_weights`` — one dict per input
    text mapping vocab token-id (as string, per FlagEmbedding's own
    convention) to a float weight. Empty dict = no lexical signal.
    """

    dense: list[list[float]]
    sparse: list[dict[str, float]]


class BGEM3Encoder:
    """Device-aware BGE-M3 encoder with lazy model load.

    The encoder defers model instantiation until the first ``encode``
    call so that importing this module (done by ``src.api`` on every
    request) costs nothing. Pass ``model_factory`` to swap in a test
    double.

    Parameters
    ----------
    device:
        One of ``"auto"``, ``"cuda"``, ``"cpu"``. Auto picks CUDA if
        ``torch.cuda.is_available()``, else CPU.
    use_fp16:
        Half-precision weights. Enabled automatically on CUDA unless
        overridden; disabled on CPU (no speed-up, possible accuracy
        loss in float16 → int8 → float32 round-trips for reranking
        downstream).
    model_name:
        HuggingFace repo or local path. Defaults to ``BAAI/bge-m3``
        (~2.3 GB first download).
    model_factory:
        Injection point for tests. A callable that takes
        ``(model_name, device, use_fp16)`` and returns an object
        satisfying ``BGEM3ModelProtocol``. Production leaves this as
        ``None`` to pick up the default factory that imports
        ``FlagEmbedding`` lazily.
    """

    def __init__(
        self,
        *,
        device: str = "auto",
        use_fp16: bool | None = None,
        model_name: str = MODEL_NAME,
        model_factory: Callable[[str, str, bool], BGEM3ModelProtocol] | None = None,
    ) -> None:
        self._device = device
        self._use_fp16 = use_fp16
        self._model_name = model_name
        self._model_factory = model_factory or _default_model_factory
        self._model: BGEM3ModelProtocol | None = None
        self._resolved_device: str | None = None
        self._resolved_fp16: bool | None = None
        # Guards _ensure_model against a FastAPI worker pool loading
        # the ~2.3 GB weights twice under concurrent first-request load.
        self._load_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encode(
        self,
        texts: Sequence[str],
        *,
        batch_size: int = 12,
        max_length: int = 2048,
    ) -> EncodedBatch:
        """Encode a batch of texts, returning dense + sparse vectors.

        ``max_length=2048`` matches our chunker's parent cap so no
        token input is truncated in normal operation. BGE-M3 supports
        up to 8192 tokens if we ever need to embed a long-form work
        directly.

        ``batch_size=12`` is conservative for 11 GB VRAM with fp16 and
        max_length=2048. Callers running on bigger GPUs should pass a
        larger batch; CPU callers a smaller one.

        Empty input returns an empty ``EncodedBatch`` without loading
        the model — useful for conditional pipelines.
        """
        if not texts:
            return EncodedBatch(dense=[], sparse=[])

        model = self._ensure_model()
        raw = model.encode(
            list(texts),
            batch_size=batch_size,
            max_length=max_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        return _extract_batch(raw)

    @property
    def device(self) -> str:
        """Resolved device (``cuda`` or ``cpu``). Triggers a load if needed."""
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

    def _ensure_model(self) -> BGEM3ModelProtocol:
        # Fast path without the lock — by far the common case after
        # first load. A torn read is harmless because we re-check
        # inside the lock and Python refcounts keep the object alive.
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is not None:  # someone else loaded while we waited
                return self._model
            device = _resolve_device(self._device)
            # fp16 is only meaningful on CUDA — FlagEmbedding itself
            # silently forces fp16=False on CPU, so mirroring that rule
            # here keeps ``uses_fp16`` honest. Without this, a caller
            # that passes use_fp16=True with device="cpu" would see
            # uses_fp16=True in our property while the real model runs
            # fp32, misleading any dashboard.
            requested_fp16 = self._use_fp16 if self._use_fp16 is not None else True
            fp16 = requested_fp16 and device == "cuda"
            self._model = self._model_factory(self._model_name, device, fp16)
            self._resolved_device = device
            self._resolved_fp16 = fp16
            return self._model


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _resolve_device(requested: str) -> str:
    """Pick a torch device, preferring CUDA when available.

    Lazy-imports torch so ``_resolve_device("cpu")`` works in test
    environments where torch is mocked. Unknown device strings fall
    back to CPU rather than raising — makes the encoder harder to
    break from config typos.

    When the caller explicitly asks for CUDA but it isn't available,
    we log a warning before falling back. ``"auto"`` is silent since
    the name advertises "pick whatever works". A production deploy
    that hard-requires GPU can assert on the resolved device via
    the ``encoder.device`` property after construction.
    """
    if requested == "cpu":
        return "cpu"
    if requested in ("cuda", "auto"):
        try:
            import torch  # noqa: PLC0415 — intentional lazy import

            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        if requested == "cuda":
            logger.warning(
                "CUDA requested but not available; BGE-M3 will run on CPU "
                "(~20x slower). Check torch install: `python -c "
                '"import torch; print(torch.cuda.is_available())"`.'
            )
        return "cpu"
    logger.warning("Unknown device %r; falling back to CPU.", requested)
    return "cpu"


def _default_model_factory(model_name: str, device: str, use_fp16: bool) -> BGEM3ModelProtocol:
    """Real BGE-M3 loader. Imported lazily to keep tests light.

    Any I/O (HuggingFace download on first run, weight deserialisation
    from local cache afterwards) happens here.
    """
    from FlagEmbedding import BGEM3FlagModel  # noqa: PLC0415

    # ``devices="cuda"`` or ``"cpu"`` is what FlagEmbedding expects;
    # the keyword is singular in 1.3.x. FlagEmbedding's classes are
    # typed loosely, so we cast to our Protocol for downstream mypy
    # happiness — the runtime object exposes exactly the encode()
    # signature we declared.
    return cast(
        BGEM3ModelProtocol,
        BGEM3FlagModel(model_name, use_fp16=use_fp16, devices=device),
    )


def _extract_batch(raw: dict[str, Any]) -> EncodedBatch:
    """Coerce FlagEmbedding's output into a predictable shape.

    FlagEmbedding returns numpy arrays and a list of ``defaultdict``
    objects. We materialise to plain Python types so downstream
    serialisation (to Postgres JSONB, to Qdrant over HTTP) never has
    to care about numpy again.
    """
    dense_raw = raw.get("dense_vecs")
    sparse_raw = raw.get("lexical_weights")
    if dense_raw is None or sparse_raw is None:
        raise RuntimeError(
            "BGE-M3 returned incomplete output: 'dense_vecs' and "
            "'lexical_weights' must both be non-None. "
            f"Got keys: {sorted(raw.keys())}, "
            f"dense_vecs is None: {dense_raw is None}, "
            f"lexical_weights is None: {sparse_raw is None}."
        )
    if len(dense_raw) != len(sparse_raw):
        # Could only happen on a FlagEmbedding version change that
        # reshapes one of the outputs. Catching it here beats silently
        # zipping misaligned dense/sparse pairs into Qdrant.
        raise RuntimeError(
            "BGE-M3 returned mismatched dense/sparse batch sizes: "
            f"{len(dense_raw)} dense vs {len(sparse_raw)} sparse."
        )

    dense = [list(map(float, vec)) for vec in dense_raw]
    # Sparse values may be numpy scalars; ``float(v)`` normalises both
    # np.float32 and native floats. Keys are already strings from
    # FlagEmbedding 1.3.x.
    sparse = [{str(k): float(v) for k, v in weights.items()} for weights in sparse_raw]
    return EncodedBatch(dense=dense, sparse=sparse)
