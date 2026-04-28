# Pāli glossary tuning — rag-day-23 (targeted golden, n=100)

> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers below come from
> ``golden_pali_targeted.yaml`` (100 синтетических QA, специально
> построенных для измерения пользы глоссария). Дельты между
> конфигурациями валидны для ranking, не для абсолютных утверждений.

## Что измеряем

Базовый прогон (`docs/EVAL_PALI_GLOSSARY_TARGETED.md`) выявил
recall/precision tradeoff: bare-Pāli `ref_hit@20` +13.3 pp, но
`ref_hit@1` −5 pp при `max_meanings=2`. Здесь крутим две ручки:

* **`max_meanings`**: 0 (только Pāli lemma), 1, 2 — объём
  расширения. Меньше — точнее, больше — шире покрытие.
* **`rerank`**: `False` (current prod default per day-22)
  vs `True` — гипотеза, что реранкер восстановит precision.

## Метаданные

- **Generated**: 2026-04-28T20:21:21+00:00
- **Git commit**: `80f3cd5`
- **Golden set**: `docs\eval\golden_pali_targeted.yaml` (version `0.0-pali-targeted`, n=100)
- **top_k (eval)**: 20
- **Collection**: `dharma_v2` + expand_parents=True
- **Glossary**: 50,060 DPD лемм + 284 кириллических вариантов
- **Platform**: Windows-11-10.0.26200-SP0 / Python 3.12.10

## Главный результат — 6-cell tuning matrix

| cell | gloss | max | rerank | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR | latency_s | rerank_s |
|---|:--:|:--:|:--:|---:|---:|---:|---:|---:|---:|---:|
| baseline_norerank | — | — | — | 0.090 | 0.200 | 0.330 | 0.440 | 0.150 | 7.61 | 0.00 |
| gloss2_norerank | ✓ | 2 | — | 0.040 | 0.210 | 0.340 | 0.490 | 0.126 | 6.74 | 0.00 |
| gloss1_norerank | ✓ | 1 | — | 0.070 | 0.290 | 0.360 | 0.490 | 0.162 | 6.57 | 0.00 |
| gloss0_norerank | ✓ | 0 | — | 0.070 | 0.240 | 0.380 | 0.470 | 0.150 | 6.35 | 0.00 |
| baseline_rerank | — | — | ✓ | 0.070 | 0.220 | 0.350 | 0.440 | 0.149 | 767.36 | 760.67 |
| gloss1_rerank | ✓ | 1 | ✓ | 0.100 | 0.250 | 0.390 | 0.510 | 0.185 | 764.53 | 757.81 |

## Δ vs baseline_norerank

| cell | Δ ref_hit@1 | Δ ref_hit@5 | Δ ref_hit@10 | Δ ref_hit@20 | Δ MRR |
|---|---:|---:|---:|---:|---:|
| gloss2_norerank | -5.0 | +1.0 | +1.0 | +5.0 | -0.024 |
| gloss1_norerank | -2.0 | +9.0 | +3.0 | +5.0 | +0.012 |
| gloss0_norerank | -2.0 | +4.0 | +5.0 | +3.0 | +0.000 |
| baseline_rerank | -2.0 | +2.0 | +2.0 | +0.0 | -0.002 |
| gloss1_rerank | +1.0 | +5.0 | +6.0 | +7.0 | +0.034 |

## Победители

- **Best ref_hit@5**: `gloss1_norerank` (0.290)
- **Best ref_hit@1**: `gloss1_rerank` (0.100)
- **Best MRR**: `gloss1_rerank` (0.185)

### `baseline_norerank` — по языку

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| mixed | 20 | 0.100 | 0.250 | 0.450 | 0.500 | 0.166 |
| pli | 30 | 0.033 | 0.167 | 0.300 | 0.400 | 0.112 |
| ru | 50 | 0.120 | 0.200 | 0.300 | 0.440 | 0.167 |

### `gloss2_norerank` — по языку

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| mixed | 20 | 0.050 | 0.300 | 0.450 | 0.500 | 0.153 |
| pli | 30 | 0.000 | 0.200 | 0.367 | 0.533 | 0.108 |
| ru | 50 | 0.060 | 0.180 | 0.280 | 0.460 | 0.126 |

### `gloss1_norerank` — по языку

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| mixed | 20 | 0.100 | 0.300 | 0.400 | 0.500 | 0.209 |
| pli | 30 | 0.000 | 0.300 | 0.333 | 0.467 | 0.116 |
| ru | 50 | 0.100 | 0.280 | 0.360 | 0.500 | 0.172 |

### `gloss0_norerank` — по языку

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| mixed | 20 | 0.100 | 0.300 | 0.450 | 0.500 | 0.183 |
| pli | 30 | 0.033 | 0.167 | 0.300 | 0.367 | 0.111 |
| ru | 50 | 0.080 | 0.260 | 0.400 | 0.520 | 0.161 |

### `baseline_rerank` — по языку

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| mixed | 20 | 0.050 | 0.300 | 0.450 | 0.550 | 0.176 |
| pli | 30 | 0.033 | 0.100 | 0.233 | 0.333 | 0.085 |
| ru | 50 | 0.100 | 0.260 | 0.380 | 0.460 | 0.175 |

### `gloss1_rerank` — по языку

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| mixed | 20 | 0.100 | 0.300 | 0.400 | 0.550 | 0.208 |
| pli | 30 | 0.100 | 0.200 | 0.267 | 0.433 | 0.160 |
| ru | 50 | 0.100 | 0.260 | 0.460 | 0.540 | 0.190 |

---

Regenerate: `python scripts/eval_pali_tuning.py` (needs Qdrant + Postgres + GPU, ~36 min wallclock for 4 rerank cells).
