"""Loader for the synthetic golden eval set.

The on-disk format lives at ``docs/eval/golden_v0.0_synthetic.yaml`` and
is documented in :file:`docs/concepts/09-eval-and-golden-set.md`. This
module turns that YAML into typed Python objects we can iterate over.

Why a dedicated loader (vs ``yaml.safe_load`` inline)
-----------------------------------------------------
* **One place that owns the schema.** When the buddhologist's v0.1 file
  arrives with extra fields (e.g. ``forbidden_works``), this module is
  the single point that has to learn about them. Callers — eval runner,
  tests, future Ragas integration — get typed dataclasses, not dicts.
* **Strict validation up front.** A typo in ``expected_works`` is a
  silent miss in the eval; surfacing it as a parse-time ``ValueError``
  is much friendlier than an invisible 0% recall.
* **Multiple files supported by the same schema.** v0.0 (synthetic) and
  v0.1 (authoritative) will share fields; the loader doesn't care which
  one is on disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_GOLDEN_PATH: Path = Path("docs/eval/golden_v0.0_synthetic.yaml")


@dataclass(frozen=True, slots=True)
class GoldenItem:
    """One (query, expected) pair from the golden set.

    ``expected_works`` is the list of canonical IDs (e.g. ``["mn118"]``)
    that should appear in retrieval results. Matching is by
    ``HybridHit.work_canonical_id`` — exact, case-sensitive.

    ``expected_segments`` (optional) is the stricter target: not just
    "right sutta" but "right paragraph". Day-14 metrics use only
    ``expected_works``; ``expected_segments`` is reserved for future
    finer-grained evals.
    """

    id: str
    query: str
    expected_works: tuple[str, ...]
    topic: str
    language: str
    difficulty: str
    expected_segments: tuple[str, ...] = field(default_factory=tuple)
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class GoldenSet:
    """All items from one golden YAML file plus its metadata.

    ``authoritative=False`` is set for synthetic v0.0 — the eval runner
    propagates this flag into the report so a future reader can tell at
    a glance whether the numbers were validated by a domain expert.
    """

    version: str
    authoritative: bool
    generated_date: str
    total_items: int
    items: tuple[GoldenItem, ...]


def load_golden_set(path: Path | str = DEFAULT_GOLDEN_PATH) -> GoldenSet:
    """Parse a golden YAML file into a :class:`GoldenSet`.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If the YAML is malformed, missing required keys, or
        ``metadata.total_items`` disagrees with the number of items
        actually present.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Golden set not found: {p}")

    with p.open(encoding="utf-8") as f:
        raw: Any = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Golden file root must be a mapping, got {type(raw).__name__}")

    metadata = raw.get("metadata") or {}
    queries = raw.get("queries")
    if not isinstance(queries, list):
        raise ValueError("Golden file must contain a 'queries' list at the root.")

    items = tuple(_parse_item(idx, q) for idx, q in enumerate(queries))
    declared_total = metadata.get("total_items")
    if declared_total is not None and declared_total != len(items):
        raise ValueError(
            f"metadata.total_items={declared_total} but {len(items)} queries were parsed."
        )

    return GoldenSet(
        version=str(metadata.get("version", "unknown")),
        authoritative=bool(metadata.get("authoritative", False)),
        generated_date=str(metadata.get("generated_date", "")),
        total_items=len(items),
        items=items,
    )


def _parse_item(idx: int, raw: Any) -> GoldenItem:
    """Validate one query mapping and freeze it into a :class:`GoldenItem`."""
    if not isinstance(raw, dict):
        raise ValueError(f"queries[{idx}] must be a mapping, got {type(raw).__name__}")

    required = {"id", "query", "expected_works", "topic", "language", "difficulty"}
    missing = required - raw.keys()
    if missing:
        raise ValueError(f"queries[{idx}] missing keys: {sorted(missing)}")

    expected_works = raw["expected_works"]
    if not isinstance(expected_works, list) or not expected_works:
        raise ValueError(f"queries[{idx}].expected_works must be a non-empty list.")
    if not all(isinstance(w, str) for w in expected_works):
        raise ValueError(f"queries[{idx}].expected_works must contain only strings.")

    expected_segments = raw.get("expected_segments") or []
    if not isinstance(expected_segments, list) or not all(
        isinstance(s, str) for s in expected_segments
    ):
        raise ValueError(f"queries[{idx}].expected_segments must be a list of strings.")

    return GoldenItem(
        id=str(raw["id"]),
        query=str(raw["query"]),
        expected_works=tuple(expected_works),
        topic=str(raw["topic"]),
        language=str(raw["language"]),
        difficulty=str(raw["difficulty"]),
        expected_segments=tuple(expected_segments),
        rationale=str(raw.get("rationale", "")),
    )


__all__ = [
    "DEFAULT_GOLDEN_PATH",
    "GoldenItem",
    "GoldenSet",
    "load_golden_set",
]
