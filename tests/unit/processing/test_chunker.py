"""Unit tests for the parent-child chunker.

Covers four concerns:

* Boundary behaviour: parents break on paragraph boundaries,
  children break inside parents.
* Overflow: when a single segment is bigger than a target/max,
  the algorithm doesn't loop forever and emits reasonable output.
* Metadata: ``segment_ids``, ``position``, ``position_in_parent``
  are correctly stamped — retrieval depends on them.
* Edge cases: empty input, single segment, non-numeric paragraph
  keys, Pali text with diacritics.
"""

from __future__ import annotations

import pytest

from src.processing.chunker import (
    MAX_CHILD_TOKENS,
    MAX_PARENT_TOKENS,
    SegmentInput,
    chunk_segments,
    default_token_count,
)


def _seg(segment_id: str, text: str) -> SegmentInput:
    return SegmentInput(segment_id=segment_id, text=text)


def _word(n: int) -> str:
    """Return a string with exactly ``n`` words, easy for token maths."""
    return " ".join(f"w{i}" for i in range(n))


# ---------------------------------------------------------------------------
# default_token_count heuristic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", 1),  # floor at 1 so every segment contributes
        ("hello world", 3),  # 2 words * 1.3 = 2.6 → round to 3
        ("one two three four five", 6),  # 5 * 1.3 = 6.5 → 6 (banker's rounding)
        (" ".join(["word"] * 10), 13),  # 10 * 1.3 = 13
    ],
)
def test_default_token_count(text: str, expected: int) -> None:
    assert default_token_count(text) == expected


# ---------------------------------------------------------------------------
# Empty / trivial inputs
# ---------------------------------------------------------------------------


def test_empty_input_returns_empty_list() -> None:
    assert chunk_segments([]) == []


def test_single_tiny_segment_produces_one_parent_one_child() -> None:
    result = chunk_segments(
        [_seg("mn1:1.1", "So I have heard.")],
    )
    assert len(result) == 1
    parent = result[0]
    assert parent.position == 0
    assert parent.segment_ids == ["mn1:1.1"]
    assert parent.text == "So I have heard."
    assert len(parent.children) == 1
    assert parent.children[0].segment_ids == ["mn1:1.1"]
    assert parent.children[0].position_in_parent == 0


# ---------------------------------------------------------------------------
# Parent boundary on paragraph break
# ---------------------------------------------------------------------------


def test_parent_break_at_paragraph_boundary_when_target_reached() -> None:
    """After target_parent_tokens is reached, the next paragraph triggers a break."""
    # Use 3 paragraphs, each ~120 tokens (enough that paragraph 1+2 is
    # above a 200-token target).
    segs = [
        _seg("mn1:1.1", _word(90)),  # para 1, ~117 tokens (90*1.3)
        _seg("mn1:2.1", _word(90)),  # para 2 — after para 1 we're at target
        _seg("mn1:3.1", _word(90)),  # para 3 — new parent starts here
    ]
    result = chunk_segments(
        segs,
        target_parent_tokens=200,
        max_parent_tokens=500,
        target_child_tokens=500,  # avoid child splits interfering
        max_child_tokens=500,
    )
    # Expected: parent 1 = [1.1, 2.1] (≈234 tokens, broke at para 3),
    # parent 2 = [3.1].
    assert len(result) == 2
    assert result[0].segment_ids == ["mn1:1.1", "mn1:2.1"]
    assert result[1].segment_ids == ["mn1:3.1"]
    assert result[0].position == 0
    assert result[1].position == 1


def test_parent_stays_within_paragraph_below_target() -> None:
    """If under target, do not close even on paragraph boundary."""
    segs = [
        _seg("mn1:1.1", _word(10)),
        _seg("mn1:2.1", _word(10)),
        _seg("mn1:3.1", _word(10)),
    ]
    result = chunk_segments(
        segs,
        target_parent_tokens=200,
        max_parent_tokens=500,
    )
    # All three paragraphs fit in one parent (3 * 13 = 39 tokens, way
    # below 200 target).
    assert len(result) == 1
    assert len(result[0].segment_ids) == 3


# ---------------------------------------------------------------------------
# Hard overflow safety valve
# ---------------------------------------------------------------------------


def test_parent_force_closes_at_max_even_without_paragraph_break() -> None:
    """If max is about to be exceeded, close mid-paragraph."""
    segs = [
        _seg("mn1:1.1", _word(200)),  # ~260 tokens
        _seg("mn1:1.2", _word(200)),  # adding this would exceed max=400
        _seg("mn1:1.3", _word(200)),
    ]
    result = chunk_segments(
        segs,
        target_parent_tokens=1000,  # far away
        max_parent_tokens=400,
        target_child_tokens=1000,
        max_child_tokens=1000,
    )
    # Every segment stands alone because adding a second one (≈260 + 260
    # = 520) exceeds max=400.
    assert len(result) == 3
    assert [p.segment_ids for p in result] == [
        ["mn1:1.1"],
        ["mn1:1.2"],
        ["mn1:1.3"],
    ]


# ---------------------------------------------------------------------------
# Children inside a parent
# ---------------------------------------------------------------------------


def test_children_split_at_segment_boundaries() -> None:
    """A long parent gets sliced into children on segment boundaries."""
    segs = [
        _seg("mn1:1.1", _word(50)),  # 65 tokens
        _seg("mn1:1.2", _word(50)),
        _seg("mn1:1.3", _word(50)),
        _seg("mn1:1.4", _word(50)),
        _seg("mn1:1.5", _word(50)),
        _seg("mn1:1.6", _word(50)),
    ]
    result = chunk_segments(
        segs,
        target_parent_tokens=10_000,  # keep everything in one parent
        max_parent_tokens=10_000,
        target_child_tokens=100,  # two segments per child (2*65=130)
        max_child_tokens=200,
    )
    assert len(result) == 1
    parent = result[0]
    # 6 segments × 65 tokens = 390 total; children ~130 each → 3 children.
    assert len(parent.children) == 3
    for i, child in enumerate(parent.children):
        assert child.position_in_parent == i
        assert len(child.segment_ids) == 2


def test_children_cover_all_parent_segments_in_order() -> None:
    """Every parent segment appears in exactly one child, same order."""
    segs = [_seg(f"mn1:1.{i}", _word(40)) for i in range(1, 11)]
    result = chunk_segments(segs)
    for parent in result:
        flat: list[str] = []
        for child in parent.children:
            flat.extend(child.segment_ids)
        assert flat == parent.segment_ids


# ---------------------------------------------------------------------------
# Metadata / positions
# ---------------------------------------------------------------------------


def test_parent_positions_are_0_indexed_and_contiguous() -> None:
    segs = [_seg(f"mn1:{p}.1", _word(200)) for p in range(1, 6)]
    result = chunk_segments(
        segs,
        target_parent_tokens=200,
        max_parent_tokens=500,
    )
    for i, parent in enumerate(result):
        assert parent.position == i


def test_parent_text_joins_segments_with_single_space() -> None:
    """No leading/trailing whitespace; segments separated by a single space."""
    segs = [
        _seg("mn1:1.1", "Hello"),
        _seg("mn1:1.2", "world"),
        _seg("mn1:1.3", "."),
    ]
    result = chunk_segments(segs)
    assert result[0].text == "Hello world ."  # join strips trailing only


def test_token_count_matches_sum_of_segments() -> None:
    segs = [
        _seg("mn1:1.1", _word(50)),
        _seg("mn1:1.2", _word(30)),
    ]
    result = chunk_segments(segs)
    parent = result[0]
    expected = default_token_count(segs[0].text) + default_token_count(segs[1].text)
    assert parent.token_count == expected


# ---------------------------------------------------------------------------
# Pali / Unicode sanity
# ---------------------------------------------------------------------------


def test_pali_diacritics_pass_through_unchanged() -> None:
    segs = [
        _seg("mn10:1.1", "Satipaṭṭhānasutta"),
        _seg("mn10:1.2", "Evaṃ me sutaṃ saññā nibbāna"),
    ]
    result = chunk_segments(segs)
    assert "Satipaṭṭhānasutta" in result[0].text
    assert "nibbāna" in result[0].text
    assert "Satipaṭṭhānasutta" in result[0].children[0].text


def test_non_numeric_paragraph_keys_fall_back_to_token_limits() -> None:
    """When paragraph can't be parsed, we only break on token limits."""
    segs = [
        _seg("mn-name:1.mn-mulapannasa", _word(100)),
        _seg("mn-name:2.mn-vagga", _word(100)),
    ]
    # With target 10k and max 10k these should stay together.
    result = chunk_segments(
        segs,
        target_parent_tokens=10_000,
        max_parent_tokens=10_000,
    )
    assert len(result) == 1
    assert len(result[0].segment_ids) == 2


# ---------------------------------------------------------------------------
# Injected token counter
# ---------------------------------------------------------------------------


def test_custom_token_counter_changes_break_points() -> None:
    """Prove the DI seam: a counter that claims huge counts forces splits."""

    def huge_counter(_: str) -> int:
        return 1000  # every segment "costs" 1000 tokens

    segs = [_seg(f"mn1:1.{i}", "x") for i in range(3)]
    result = chunk_segments(
        segs,
        target_parent_tokens=500,
        max_parent_tokens=900,
        count_tokens=huge_counter,
    )
    # Each segment alone overflows max=900 when buffered with another,
    # so we expect 3 parents.
    assert len(result) == 3


# ---------------------------------------------------------------------------
# Realistic default sizes — smoke test on a miniature sutta
# ---------------------------------------------------------------------------


def test_defaults_produce_reasonable_chunking_on_realistic_corpus() -> None:
    # Simulate an MN-style sutta: ~30 paragraphs, 5 sentences each,
    # ~15 words/sentence. About 2250 total tokens — should yield
    # 1-2 parents with several children each.
    segs = [_seg(f"mn10:{p}.{s}", _word(15)) for p in range(1, 31) for s in range(1, 6)]
    result = chunk_segments(segs)
    assert 1 <= len(result) <= 3, f"unexpected parent count: {len(result)}"
    for parent in result:
        assert parent.token_count <= MAX_PARENT_TOKENS
        assert len(parent.children) >= 1
        for child in parent.children:
            assert child.token_count <= MAX_CHILD_TOKENS
