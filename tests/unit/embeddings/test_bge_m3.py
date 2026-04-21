"""Unit tests for the BGE-M3 encoder wrapper.

No real model is loaded anywhere in this file — every test swaps
in a ``FakeModel`` via the ``model_factory`` DI seam. That keeps the
suite under a second and avoids a 2.3 GB HuggingFace download in CI.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.embeddings.bge_m3 import (
    DENSE_DIM,
    MODEL_NAME,
    BGEM3Encoder,
    EncodedBatch,
    _extract_batch,
    _resolve_device,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeModel:
    """Structurally satisfies ``BGEM3ModelProtocol``.

    Records every encode() call so tests can assert on batch_size /
    max_length plumbing. Produces deterministic mock vectors so
    dense/sparse shape checks are meaningful.
    """

    def __init__(self, *, dim: int = DENSE_DIM) -> None:
        self.dim = dim
        self.calls: list[dict[str, Any]] = []

    def encode(
        self,
        sentences: list[str] | str,
        *,
        batch_size: int = 12,
        max_length: int = 2048,
        return_dense: bool = True,
        return_sparse: bool = True,
        return_colbert_vecs: bool = False,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "sentences": list(sentences) if isinstance(sentences, list) else [sentences],
                "batch_size": batch_size,
                "max_length": max_length,
                "return_dense": return_dense,
                "return_sparse": return_sparse,
                "return_colbert_vecs": return_colbert_vecs,
            }
        )
        n = len(sentences) if isinstance(sentences, list) else 1
        # Dense: one vector per input, filled with the input index — easy
        # to assert positional correctness.
        dense = [[float(i)] * self.dim for i in range(n)]
        # Sparse: one dict per input with a couple of token weights.
        sparse = [{"42": 0.8 + i * 0.01, "7": 0.2} for i in range(n)]
        return {"dense_vecs": dense, "lexical_weights": sparse}


def _fake_factory(_name: str, _device: str, _fp16: bool) -> FakeModel:
    return FakeModel()


# ---------------------------------------------------------------------------
# _resolve_device
# ---------------------------------------------------------------------------


def test_resolve_device_cpu_always_returns_cpu() -> None:
    assert _resolve_device("cpu") == "cpu"


def test_resolve_device_unknown_falls_back_to_cpu() -> None:
    assert _resolve_device("tpu-v5-please") == "cpu"


def test_resolve_device_auto_returns_cpu_without_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    """When torch.cuda.is_available() is False, 'auto' → 'cpu'."""
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
# Lazy loading
# ---------------------------------------------------------------------------


def test_init_does_not_load_model() -> None:
    """Constructing the encoder must not invoke model_factory."""
    calls = {"n": 0}

    def counting_factory(*_a: Any) -> FakeModel:
        calls["n"] += 1
        return FakeModel()

    BGEM3Encoder(model_factory=counting_factory)
    assert calls["n"] == 0


def test_model_loaded_once_across_multiple_encodes() -> None:
    """The DI'd factory fires exactly once — lazy + cached."""
    calls = {"n": 0}

    def counting_factory(*_a: Any) -> FakeModel:
        calls["n"] += 1
        return FakeModel()

    enc = BGEM3Encoder(device="cpu", model_factory=counting_factory)
    enc.encode(["one"])
    enc.encode(["two", "three"])
    assert calls["n"] == 1


def test_empty_input_does_not_load_model() -> None:
    """encode([]) must be a free no-op — useful for conditional batches."""
    calls = {"n": 0}

    def counting_factory(*_a: Any) -> FakeModel:
        calls["n"] += 1
        return FakeModel()

    enc = BGEM3Encoder(device="cpu", model_factory=counting_factory)
    result = enc.encode([])
    assert calls["n"] == 0
    assert result == EncodedBatch(dense=[], sparse=[])


# ---------------------------------------------------------------------------
# Encode: shapes + content
# ---------------------------------------------------------------------------


def test_encode_returns_one_dense_and_sparse_per_input() -> None:
    enc = BGEM3Encoder(device="cpu", model_factory=_fake_factory)
    result = enc.encode(["a", "b", "c"])
    assert len(result.dense) == 3
    assert len(result.sparse) == 3


def test_encode_dense_vectors_have_expected_dim() -> None:
    enc = BGEM3Encoder(device="cpu", model_factory=_fake_factory)
    result = enc.encode(["hello"])
    assert len(result.dense[0]) == DENSE_DIM


def test_encode_preserves_input_order() -> None:
    """Positional indices in fake output must match input position."""
    enc = BGEM3Encoder(device="cpu", model_factory=_fake_factory)
    result = enc.encode(["x", "y", "z"])
    # FakeModel stamps vec[0] with index; all values equal that index.
    assert result.dense[0][0] == 0.0
    assert result.dense[1][0] == 1.0
    assert result.dense[2][0] == 2.0


def test_encode_sparse_is_plain_python_types() -> None:
    """Sparse keys must be str, values must be float — not numpy types."""
    enc = BGEM3Encoder(device="cpu", model_factory=_fake_factory)
    result = enc.encode(["hi"])
    weights = result.sparse[0]
    assert all(isinstance(k, str) for k in weights.keys())
    assert all(isinstance(v, float) for v in weights.values())


# ---------------------------------------------------------------------------
# Parameter passthrough
# ---------------------------------------------------------------------------


def test_batch_size_and_max_length_reach_model() -> None:
    captured = FakeModel()

    def factory(*_a: Any) -> FakeModel:
        return captured

    enc = BGEM3Encoder(device="cpu", model_factory=factory)
    enc.encode(["hi"], batch_size=4, max_length=512)
    call = captured.calls[0]
    assert call["batch_size"] == 4
    assert call["max_length"] == 512


def test_colbert_is_never_requested() -> None:
    """Phase 1 does not need multi-vectors; make sure we don't pay for them."""
    captured = FakeModel()
    enc = BGEM3Encoder(device="cpu", model_factory=lambda *_: captured)
    enc.encode(["hi"])
    assert captured.calls[0]["return_colbert_vecs"] is False
    assert captured.calls[0]["return_dense"] is True
    assert captured.calls[0]["return_sparse"] is True


# ---------------------------------------------------------------------------
# fp16 selection
# ---------------------------------------------------------------------------


def test_fp16_defaults_to_true_on_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    captured: dict[str, Any] = {}

    def factory(name: str, device: str, fp16: bool) -> FakeModel:
        captured.update({"name": name, "device": device, "fp16": fp16})
        return FakeModel()

    enc = BGEM3Encoder(device="auto", model_factory=factory)
    enc.encode(["x"])
    assert captured["device"] == "cuda"
    assert captured["fp16"] is True
    assert captured["name"] == MODEL_NAME


def test_fp16_defaults_to_false_on_cpu() -> None:
    captured: dict[str, Any] = {}

    def factory(name: str, device: str, fp16: bool) -> FakeModel:
        captured.update({"device": device, "fp16": fp16})
        return FakeModel()

    enc = BGEM3Encoder(device="cpu", model_factory=factory)
    enc.encode(["x"])
    assert captured["device"] == "cpu"
    assert captured["fp16"] is False


def test_explicit_fp16_override_beats_default_on_cuda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit ``use_fp16=False`` on CUDA overrides the auto-True default."""
    import torch

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    captured: dict[str, Any] = {}

    def factory(_n: str, _d: str, fp16: bool) -> FakeModel:
        captured["fp16"] = fp16
        return FakeModel()

    enc = BGEM3Encoder(device="auto", use_fp16=False, model_factory=factory)
    enc.encode(["x"])
    assert captured["fp16"] is False
    assert enc.uses_fp16 is False


# ---------------------------------------------------------------------------
# _extract_batch error paths
# ---------------------------------------------------------------------------


def test_extract_batch_rejects_missing_dense() -> None:
    with pytest.raises(RuntimeError, match="incomplete output"):
        _extract_batch({"lexical_weights": []})


def test_extract_batch_rejects_missing_sparse() -> None:
    with pytest.raises(RuntimeError, match="incomplete output"):
        _extract_batch({"dense_vecs": []})


def test_extract_batch_rejects_size_mismatch() -> None:
    """A size-mismatched FlagEmbedding response must fail loudly.

    Guards against future FlagEmbedding versions that might return
    more or fewer sparse weights than dense vectors — silently zipping
    misaligned outputs into Qdrant would poison retrieval.
    """
    with pytest.raises(RuntimeError, match="mismatched dense/sparse batch sizes"):
        _extract_batch(
            {
                "dense_vecs": [[0.1] * DENSE_DIM],
                "lexical_weights": [{"1": 0.5}, {"2": 0.3}],  # 2 sparse vs 1 dense
            }
        )


# ---------------------------------------------------------------------------
# Empty string input
# ---------------------------------------------------------------------------


def test_empty_string_input_produces_empty_sparse_dict() -> None:
    """Real BGE-M3 gives an empty lexical weights dict for ``""``. Wrapper copes."""

    class EmptyOutputFake:
        def encode(self, sentences: list[str] | str, **_: Any) -> dict[str, Any]:
            n = len(sentences) if isinstance(sentences, list) else 1
            return {
                "dense_vecs": [[0.0] * DENSE_DIM for _ in range(n)],
                "lexical_weights": [{} for _ in range(n)],
            }

    enc = BGEM3Encoder(device="cpu", model_factory=lambda *_: EmptyOutputFake())
    result = enc.encode([""])
    assert len(result.dense) == 1
    assert result.sparse == [{}]


# ---------------------------------------------------------------------------
# fp16 lie on CPU — regression for reviewer Must Fix #1
# ---------------------------------------------------------------------------


def test_fp16_true_on_cpu_is_reported_as_false() -> None:
    """FlagEmbedding silently forces fp16=False on CPU.

    Our wrapper must mirror that truth so dashboards don't report
    fp16=True while the real model runs fp32.
    """
    captured: dict[str, Any] = {}

    def factory(_n: str, _d: str, fp16: bool) -> FakeModel:
        captured["fp16_passed_to_model"] = fp16
        return FakeModel()

    enc = BGEM3Encoder(device="cpu", use_fp16=True, model_factory=factory)
    enc.encode(["x"])
    # We passed use_fp16=True but device resolved to cpu → real fp16
    # must be False, and the property must agree with the model.
    assert captured["fp16_passed_to_model"] is False
    assert enc.uses_fp16 is False


# ---------------------------------------------------------------------------
# Device property surfacing
# ---------------------------------------------------------------------------


def test_device_property_returns_resolved_value() -> None:
    enc = BGEM3Encoder(device="cpu", model_factory=_fake_factory)
    assert enc.device == "cpu"
    assert enc.uses_fp16 is False
