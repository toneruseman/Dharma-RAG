"""Evaluation utilities for the retrieval pipeline.

Public surface
--------------
* :class:`GoldenSet` / :class:`GoldenItem` — typed access to the golden
  YAML on disk.
* :func:`load_golden_set` — parse a golden YAML file.
* :func:`ref_hit_at_k`, :func:`reciprocal_rank`, :func:`mean_reciprocal_rank`
  — pure metric primitives.
* :func:`run_eval` / :func:`summarise` — pipeline over golden + metric
  aggregation, the units the day-14 CLI calls.
"""

from src.eval.golden import (
    DEFAULT_GOLDEN_PATH,
    GoldenItem,
    GoldenSet,
    load_golden_set,
)
from src.eval.metrics import (
    mean_reciprocal_rank,
    reciprocal_rank,
    ref_hit_at_k,
)
from src.eval.runner import (
    DEFAULT_EVAL_TOP_K,
    DEFAULT_K_VALUES,
    EvalSummary,
    MetricsBlock,
    PerQueryResult,
    run_eval,
    summarise,
)

__all__ = [
    "DEFAULT_EVAL_TOP_K",
    "DEFAULT_GOLDEN_PATH",
    "DEFAULT_K_VALUES",
    "EvalSummary",
    "GoldenItem",
    "GoldenSet",
    "MetricsBlock",
    "PerQueryResult",
    "load_golden_set",
    "mean_reciprocal_rank",
    "ref_hit_at_k",
    "reciprocal_rank",
    "run_eval",
    "summarise",
]
