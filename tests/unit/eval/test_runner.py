"""Unit tests for the pure parts of :mod:`src.eval.runner`.

We do NOT invoke ``run_eval`` here — that requires a real
``hybrid_search`` (encoder + Qdrant + Postgres). Instead we test the
:func:`summarise` aggregator on hand-built ``PerQueryResult`` lists,
where the expected metric values are obvious.
"""

from __future__ import annotations

import pytest

from src.eval.golden import GoldenItem
from src.eval.runner import PerQueryResult, summarise


def _item(id_: str, *, expected: tuple[str, ...], difficulty: str, language: str) -> GoldenItem:
    return GoldenItem(
        id=id_,
        query=f"q-{id_}",
        expected_works=expected,
        topic="t",
        language=language,
        difficulty=difficulty,
    )


def _result(
    item: GoldenItem,
    retrieved: tuple[str, ...],
    *,
    latency_s: float = 0.1,
    rerank_s: float = 0.0,
) -> PerQueryResult:
    return PerQueryResult(
        item=item,
        retrieved_works=retrieved,
        hits=tuple(),
        latency_s=latency_s,
        rerank_s=rerank_s,
    )


def test_summarise_overall_metrics() -> None:
    items = [
        # qa1: hit at rank 1 → ref_hit@1 = 1, RR = 1.0
        _result(
            _item("qa1", expected=("mn118",), difficulty="easy", language="en"), ("mn118", "x", "y")
        ),
        # qa2: hit at rank 3 → ref_hit@1 = 0, ref_hit@5 = 1, RR = 1/3
        _result(
            _item("qa2", expected=("sn56.11",), difficulty="easy", language="en"),
            ("a", "b", "sn56.11", "c"),
        ),
        # qa3: miss → 0/0/0
        _result(
            _item("qa3", expected=("dn22",), difficulty="hard", language="en"), ("x", "y", "z")
        ),
    ]
    s = summarise(items, label="test")

    assert s.label == "test"
    assert s.overall.n == 3
    # ref_hit@1: only qa1 hits → 1/3
    assert s.overall.ref_hit_at_k[1] == pytest.approx(1 / 3)
    # ref_hit@5: qa1 + qa2 hit → 2/3
    assert s.overall.ref_hit_at_k[5] == pytest.approx(2 / 3)
    # MRR = (1 + 1/3 + 0) / 3
    assert s.overall.mrr == pytest.approx((1 + 1 / 3 + 0) / 3)


def test_summarise_breakdowns_by_difficulty_and_language() -> None:
    items = [
        _result(_item("e1", expected=("a",), difficulty="easy", language="en"), ("a",)),
        _result(_item("e2", expected=("b",), difficulty="easy", language="en"), ("x",)),
        _result(_item("h1", expected=("c",), difficulty="hard", language="ru"), ("c",)),
    ]
    s = summarise(items, label="t")

    # By difficulty: easy n=2, hard n=1
    assert s.by_difficulty["easy"].n == 2
    assert s.by_difficulty["easy"].ref_hit_at_k[1] == pytest.approx(0.5)
    assert s.by_difficulty["hard"].n == 1
    assert s.by_difficulty["hard"].ref_hit_at_k[1] == 1.0

    # By language: en n=2, ru n=1
    assert s.by_language["en"].n == 2
    assert s.by_language["ru"].n == 1


def test_summarise_empty_returns_zero_metrics() -> None:
    s = summarise([], label="empty")
    assert s.overall.n == 0
    assert all(v == 0.0 for v in s.overall.ref_hit_at_k.values())
    assert s.overall.mrr == 0.0
    assert s.by_difficulty == {}
    assert s.by_language == {}


def test_summarise_aggregates_total_latency() -> None:
    items = [
        _result(
            _item("a", expected=("x",), difficulty="easy", language="en"),
            ("x",),
            latency_s=1.5,
            rerank_s=1.0,
        ),
        _result(
            _item("b", expected=("y",), difficulty="easy", language="en"),
            ("y",),
            latency_s=2.0,
            rerank_s=1.5,
        ),
    ]
    s = summarise(items, label="t")
    assert s.total_latency_s == pytest.approx(3.5)
    assert s.total_rerank_s == pytest.approx(2.5)


def test_summarise_custom_k_values() -> None:
    items = [
        _result(_item("a", expected=("x",), difficulty="easy", language="en"), ("x", "y", "z")),
    ]
    s = summarise(items, label="t", k_values=(2, 3))
    assert set(s.overall.ref_hit_at_k.keys()) == {2, 3}
