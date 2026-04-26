"""Unit tests for :mod:`src.eval.golden`.

Tests build minimal in-memory YAML strings rather than relying on the
checked-in ``docs/eval/golden_v0.0_synthetic.yaml`` so a future edit
to that file (adding items, changing metadata) doesn't ripple into
unrelated test failures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.eval.golden import (
    DEFAULT_GOLDEN_PATH,
    GoldenItem,
    GoldenSet,
    load_golden_set,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_MIN_VALID_YAML = """\
metadata:
  version: "test-0.0"
  authoritative: false
  generated_date: "2026-04-26"
  total_items: 2

queries:
  - id: "qa_001"
    query: "What is mindfulness of breathing?"
    expected_works: ["mn118"]
    topic: "meditation"
    language: "en"
    difficulty: "easy"
    rationale: "Canonical anāpānassati sutta."

  - id: "qa_002"
    query: "Where did the Buddha first teach the four noble truths?"
    expected_works: ["sn56.11"]
    expected_segments: ["sn56.11:0.1"]
    topic: "doctrine"
    language: "en"
    difficulty: "easy"
"""


def _write(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "golden.yaml"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_load_minimal_valid_set(tmp_path: Path) -> None:
    p = _write(tmp_path, _MIN_VALID_YAML)
    gs = load_golden_set(p)

    assert isinstance(gs, GoldenSet)
    assert gs.version == "test-0.0"
    assert gs.authoritative is False
    assert gs.total_items == 2
    assert len(gs.items) == 2

    first, second = gs.items
    assert isinstance(first, GoldenItem)
    assert first.id == "qa_001"
    assert first.expected_works == ("mn118",)
    assert first.expected_segments == ()  # default empty
    assert first.rationale == "Canonical anāpānassati sutta."

    assert second.expected_segments == ("sn56.11:0.1",)
    assert second.rationale == ""  # missing → default empty


def test_loaded_dataclass_is_frozen(tmp_path: Path) -> None:
    """GoldenItem must be immutable so eval results don't mutate the source."""
    p = _write(tmp_path, _MIN_VALID_YAML)
    gs = load_golden_set(p)
    item = gs.items[0]
    with pytest.raises((AttributeError, TypeError)):
        item.query = "tampered"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_missing_file_raises_filenotfound(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_golden_set(tmp_path / "nope.yaml")


def test_root_must_be_mapping(tmp_path: Path) -> None:
    p = _write(tmp_path, "- 1\n- 2\n")
    with pytest.raises(ValueError, match="root must be a mapping"):
        load_golden_set(p)


def test_missing_queries_list_raises(tmp_path: Path) -> None:
    p = _write(tmp_path, "metadata:\n  version: x\n")
    with pytest.raises(ValueError, match="must contain a 'queries' list"):
        load_golden_set(p)


def test_total_items_mismatch_raises(tmp_path: Path) -> None:
    """A typo in metadata.total_items must not silently desync."""
    p = _write(
        tmp_path,
        """\
metadata:
  total_items: 99
queries:
  - id: "x"
    query: "q"
    expected_works: ["mn1"]
    topic: "t"
    language: "en"
    difficulty: "easy"
""",
    )
    with pytest.raises(ValueError, match="total_items=99 but 1 queries"):
        load_golden_set(p)


def test_missing_required_keys_raises(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """\
queries:
  - id: "qa_x"
    query: "q"
""",
    )
    with pytest.raises(ValueError, match="missing keys"):
        load_golden_set(p)


def test_empty_expected_works_raises(tmp_path: Path) -> None:
    """Item with no expected work would silently score 0% — surface it."""
    p = _write(
        tmp_path,
        """\
queries:
  - id: "qa_x"
    query: "q"
    expected_works: []
    topic: "t"
    language: "en"
    difficulty: "easy"
""",
    )
    with pytest.raises(ValueError, match="expected_works must be a non-empty list"):
        load_golden_set(p)


def test_non_string_in_expected_works_raises(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        """\
queries:
  - id: "qa_x"
    query: "q"
    expected_works: ["mn1", 42]
    topic: "t"
    language: "en"
    difficulty: "easy"
""",
    )
    with pytest.raises(ValueError, match="must contain only strings"):
        load_golden_set(p)


# ---------------------------------------------------------------------------
# Real synthetic file (smoke)
# ---------------------------------------------------------------------------


def test_synthetic_golden_v0_loads_cleanly() -> None:
    """The checked-in synthetic file must parse without errors.

    This guards against accidental edits to
    ``docs/eval/golden_v0.0_synthetic.yaml`` that would break day-14.
    """
    gs = load_golden_set(DEFAULT_GOLDEN_PATH)
    assert gs.total_items == 30
    assert gs.authoritative is False
    assert all(item.expected_works for item in gs.items)
    # Spot-check a couple of known items.
    by_id = {item.id: item for item in gs.items}
    assert by_id["qa_001"].expected_works == ("mn118",)
    assert "sn56.11" in by_id["qa_002"].expected_works
