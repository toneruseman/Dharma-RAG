# Retrieval evaluation baseline

> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers below come from the
> synthetic golden set v0.0; absolute quality claims require a
> buddhologist-curated v0.1 (see B-001 in `docs/STATUS.md`).

## Run metadata

- **Generated**: 2026-04-26T15:04:42+00:00
- **Git commit**: `d7de5a0`
- **Golden set**: `docs\eval\golden_v0.0_synthetic.yaml` (version `0.0-synthetic`, n=30)
- **top_k (eval)**: 20
- **Platform**: Windows-11-10.0.26200-SP0 / Python 3.12.10

## A/B comparison: with vs without reranker

| Metric | rerank=False | rerank=True | Δ |
|---|---:|---:|---:|
| ref_hit@1 | 0.133 | 0.133 | +0.000 |
| ref_hit@5 | 0.367 | 0.400 | +0.033 |
| ref_hit@10 | 0.433 | 0.433 | +0.000 |
| ref_hit@20 | 0.533 | 0.600 | +0.067 |
| MRR | 0.246 | 0.244 | -0.003 |

- Total latency: rerank=False **2.91s**, rerank=True **224.64s** (of which rerank itself: 222.74s)

## Breakdown — rerank=False

### By difficulty

| difficulty | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| easy | 10 | 0.200 | 0.500 | 0.500 | 0.600 | 0.355 |
| hard | 10 | 0.100 | 0.200 | 0.300 | 0.400 | 0.158 |
| medium | 10 | 0.100 | 0.400 | 0.500 | 0.600 | 0.227 |

### By language

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| en | 28 | 0.143 | 0.357 | 0.429 | 0.536 | 0.252 |
| ru | 2 | 0.000 | 0.500 | 0.500 | 0.500 | 0.167 |

## Breakdown — rerank=True

### By difficulty

| difficulty | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| easy | 10 | 0.100 | 0.500 | 0.500 | 0.600 | 0.264 |
| hard | 10 | 0.100 | 0.200 | 0.200 | 0.500 | 0.173 |
| medium | 10 | 0.200 | 0.500 | 0.600 | 0.700 | 0.294 |

### By language

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| en | 28 | 0.143 | 0.393 | 0.429 | 0.571 | 0.240 |
| ru | 2 | 0.000 | 0.500 | 0.500 | 1.000 | 0.295 |

---

Regenerate with `python scripts/eval_retrieval.py` (needs Qdrant + Postgres + GPU running).
