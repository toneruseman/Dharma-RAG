"""Unit tests for the BGE-reranker wrapper.

No real model is loaded anywhere in this file — every test swaps in a
``FakeReranker`` via the ``model_factory`` DI seam. The reranker
weights (~1.1 GB) and torch import are skipped entirely.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from src.retrieval.reranker import (
    MODEL_NAME,
    BGEReranker,
    CandidateForRerank,
    RerankedHit,
    _resolve_device,
    _scores_to_hits,
)

# ---------------------------------------------------------------------------
# Fake model
# ---------------------------------------------------------------------------


class FakeReranker:
    """Structurally satisfies ``RerankerProtocol``.

    Records every ``compute_score`` call so tests can assert on
    plumbing. Score = ``len(text) / 100`` to give deterministic,
    interesting orderings without ML dependencies.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def compute_score(
        self,
        sentence_pairs: Any,
        *,
        batch_size: int = 32,
        max_length: int = 1024,
        normalize: bool = False,
    ) -> list[float]:
        pairs = [list(p) for p in sentence_pairs]
        self.calls.append(
            {
                "pairs": pairs,
                "batch_size": batch_size,
                "max_length": max_length,
                "normalize": normalize,
            }
        )
        return [float(len(pair[1])) / 100.0 for pair in pairs]


def _fake_factory(_name: str, _device: str, _fp16: bool) -> FakeReranker:
    return FakeReranker()


def _candidate(*, text: str, rrf_rank: int = 0) -> CandidateForRerank:
    return CandidateForRerank(chunk_id=uuid4(), text=text, rrf_rank=rrf_rank)


# ---------------------------------------------------------------------------
# _resolve_device
# ---------------------------------------------------------------------------


def test_resolve_device_cpu_always_returns_cpu() -> None:
    assert _resolve_device("cpu") == "cpu"


def test_resolve_device_unknown_falls_back_to_cpu() -> None:
    assert _resolve_device("tpu") == "cpu"


def test_resolve_device_auto_returns_cpu_without_cuda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    assert _resolve_device("auto") == "cpu"


def test_resolve_device_auto_returns_cuda_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    assert _resolve_device("auto") == "cuda"


# ---------------------------------------------------------------------------
# Reranker behaviour with FakeReranker
# ---------------------------------------------------------------------------


def test_rerank_empty_query_returns_empty_without_loading_model() -> None:
    reranker = BGEReranker(model_factory=_fake_factory)
    hits = reranker.rerank("", [_candidate(text="x")], top_k=5)
    assert hits == []


def test_rerank_empty_candidates_returns_empty_without_loading_model() -> None:
    reranker = BGEReranker(model_factory=_fake_factory)
    hits = reranker.rerank("query", [], top_k=5)
    assert hits == []


def test_rerank_invalid_top_k_returns_empty() -> None:
    reranker = BGEReranker(model_factory=_fake_factory)
    hits = reranker.rerank("q", [_candidate(text="x")], top_k=0)
    assert hits == []


def test_rerank_orders_by_descending_score() -> None:
    """FakeReranker returns ``len(text) / 100`` — longer text wins."""
    reranker = BGEReranker(model_factory=_fake_factory)
    short = _candidate(text="ab")
    medium = _candidate(text="abcdef")
    long = _candidate(text="abcdefghijklmnop")

    hits = reranker.rerank("query", [short, medium, long], top_k=3)

    assert [h.chunk_id for h in hits] == [long.chunk_id, medium.chunk_id, short.chunk_id]
    assert hits[0].score > hits[1].score > hits[2].score


def test_rerank_truncates_to_top_k() -> None:
    reranker = BGEReranker(model_factory=_fake_factory)
    cands = [_candidate(text="x" * (i + 1)) for i in range(10)]
    hits = reranker.rerank("query", cands, top_k=3)
    assert len(hits) == 3


def test_rerank_preserves_rrf_rank_in_output() -> None:
    reranker = BGEReranker(model_factory=_fake_factory)
    a = _candidate(text="short", rrf_rank=2)
    b = _candidate(text="much longer text", rrf_rank=10)

    hits = reranker.rerank("q", [a, b], top_k=2)

    # b wins on score (longer text), but its rrf_rank is preserved.
    assert hits[0].chunk_id == b.chunk_id
    assert hits[0].rrf_rank == 10
    assert hits[1].rrf_rank == 2


def test_rerank_passes_batch_and_max_length_to_model() -> None:
    fake = FakeReranker()

    def factory(_n: str, _d: str, _f: bool) -> FakeReranker:
        return fake

    reranker = BGEReranker(model_factory=factory)
    reranker.rerank(
        "q",
        [_candidate(text="a"), _candidate(text="b")],
        top_k=2,
        batch_size=16,
        max_length=512,
    )
    assert fake.calls[0]["batch_size"] == 16
    assert fake.calls[0]["max_length"] == 512
    assert fake.calls[0]["normalize"] is False


def test_rerank_handles_single_pair_scalar_return() -> None:
    """Some FlagEmbedding versions return a single float, not a list,
    when given exactly one pair. Our wrapper must handle both shapes.
    """

    class ScalarFake:
        def compute_score(self, sentence_pairs: Any, **kwargs: Any) -> float:
            return 4.2

    reranker = BGEReranker(model_factory=lambda _n, _d, _f: ScalarFake())
    hits = reranker.rerank("q", [_candidate(text="single")], top_k=1)
    assert len(hits) == 1
    assert hits[0].score == 4.2


def test_rerank_raises_on_score_count_mismatch() -> None:
    """Should not silently zip-truncate — that would mis-attribute scores."""

    class BadFake:
        def compute_score(self, sentence_pairs: Any, **kwargs: Any) -> list[float]:
            return [1.0]  # 1 score for 2 pairs

    reranker = BGEReranker(model_factory=lambda _n, _d, _f: BadFake())
    with pytest.raises(RuntimeError, match="model output mismatch"):
        reranker.rerank("q", [_candidate(text="a"), _candidate(text="b")], top_k=2)


# ---------------------------------------------------------------------------
# Lazy load + thread safety
# ---------------------------------------------------------------------------


def test_model_not_loaded_until_first_rerank_call() -> None:
    counter = {"loads": 0}

    def counting_factory(_n: str, _d: str, _f: bool) -> FakeReranker:
        counter["loads"] += 1
        return FakeReranker()

    reranker = BGEReranker(model_factory=counting_factory)
    assert counter["loads"] == 0

    reranker.rerank("q", [_candidate(text="a")], top_k=1)
    assert counter["loads"] == 1

    # Second call reuses the loaded model.
    reranker.rerank("q", [_candidate(text="b")], top_k=1)
    assert counter["loads"] == 1


def test_device_property_triggers_lazy_load() -> None:
    counter = {"loads": 0}

    def counting_factory(_n: str, d: str, _f: bool) -> FakeReranker:
        counter["loads"] += 1
        return FakeReranker()

    reranker = BGEReranker(model_factory=counting_factory, device="cpu")
    _ = reranker.device  # access triggers load
    assert counter["loads"] == 1
    assert reranker.device == "cpu"  # second access does not reload
    assert counter["loads"] == 1


def test_uses_fp16_false_on_cpu_even_when_requested() -> None:
    """Mirror the BGE-M3 encoder rule: fp16 is meaningful only on CUDA.
    Forcing fp16=True with device='cpu' must resolve to fp16=False.
    """
    captured: dict[str, Any] = {}

    def factory(_n: str, d: str, fp16: bool) -> FakeReranker:
        captured["device"] = d
        captured["fp16"] = fp16
        return FakeReranker()

    reranker = BGEReranker(device="cpu", use_fp16=True, model_factory=factory)
    _ = reranker.device  # triggers load
    assert captured["device"] == "cpu"
    assert captured["fp16"] is False
    assert reranker.uses_fp16 is False


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def test_model_name_constant_is_v2_m3() -> None:
    assert MODEL_NAME == "BAAI/bge-reranker-v2-m3"


def test_scores_to_hits_pure_helper() -> None:
    cands = [_candidate(text="a"), _candidate(text="b"), _candidate(text="c")]
    hits = _scores_to_hits(cands, [0.1, 0.9, 0.5], top_k=2)
    assert [h.chunk_id for h in hits] == [cands[1].chunk_id, cands[2].chunk_id]


def test_scores_to_hits_mismatch_raises() -> None:
    cands = [_candidate(text="a"), _candidate(text="b")]
    with pytest.raises(RuntimeError, match="Mismatched lengths"):
        _scores_to_hits(cands, [1.0], top_k=2)


# ---------------------------------------------------------------------------
# Dataclass contracts
# ---------------------------------------------------------------------------


def test_reranked_hit_is_frozen() -> None:
    h = RerankedHit(chunk_id=uuid4(), score=0.5, rrf_rank=3)
    with pytest.raises((AttributeError, TypeError)):
        h.score = 0.9  # type: ignore[misc]


def test_candidate_is_frozen() -> None:
    c = _candidate(text="x")
    with pytest.raises((AttributeError, TypeError)):
        c.text = "y"  # type: ignore[misc]
