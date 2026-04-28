# Pāli glossary mini-eval — rag-day-23 (synthetic golden v0.0-extended, n=100)

> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers below come from
> ``golden_v0.0_extended.yaml`` (100 синтетических QA). Абсолютные
> утверждения о качестве требуют валидации буддологом — см. B-001 в
> ``docs/STATUS.md``. Дельты между конфигурациями остаются валидными
> на синтетических данных — ровно для этого файл и сделан.

## Метаданные

- **Generated**: 2026-04-28T20:22:54+00:00
- **Git commit**: `80f3cd5`
- **Golden set**: `docs\eval\golden_v0.0_extended.yaml` (version `0.0-synthetic-extended`, n=100)
- **top_k (eval)**: 20
- **Production cell**: `dharma_v2` + rerank=False + expand=True
- **Glossary**: 50,060 DPD лемм + 284 кириллических вариантов
- **Platform**: Windows-11-10.0.26200-SP0 / Python 3.12.10

## Главный результат

| cell | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR | latency_s |
|---|---:|---:|---:|---:|---:|---:|
| baseline_no_glossary | 0.190 | 0.450 | 0.540 | 0.650 | 0.308 | 7.57 |
| candidate_with_glossary | 0.190 | 0.450 | 0.540 | 0.650 | 0.307 | 6.72 |

**Δ ref_hit@5 = +0.0 pp**, **Δ MRR = -0.001**

## Вывод

Глоссарий **нейтрален** на overall (Δ=0.0 pp). Default остаётся `False` — не флипаем без явного выигрыша. Возможно есть локальный лифт на bare-Pāli/RU подмножестве — см. breakdown по языку ниже.

### baseline_no_glossary — по языку

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| en | 91 | 0.209 | 0.473 | 0.560 | 0.681 | 0.330 |
| pli | 2 | 0.000 | 0.000 | 0.500 | 0.500 | 0.071 |
| ru | 7 | 0.000 | 0.286 | 0.286 | 0.286 | 0.095 |

### candidate_with_glossary — по языку

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| en | 91 | 0.209 | 0.473 | 0.571 | 0.681 | 0.329 |
| pli | 2 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| ru | 7 | 0.000 | 0.286 | 0.286 | 0.429 | 0.104 |

### Δ ref_hit@5 по языку

| language | n | baseline | candidate | Δ pp |
|---|---:|---:|---:|---:|
| en | 91 | 0.473 | 0.473 | +0.0 |
| pli | 2 | 0.000 | 0.000 | +0.0 |
| ru | 7 | 0.286 | 0.286 | +0.0 |

## Failure-анализ (top-5)

Глоссарий **починил** 1 запросов, **сломал** 1.

### Fixed by glossary

| id | lang | query | expected | candidate top-5 |
|---|---|---|---|---|
| qa_021 | en | What is the relationship between sati and samādhi? | mn117, an4.41, sn47.4 | dn10, sn47.4, an3.101, dn10, dn10 |

### Regressed by glossary

| id | lang | query | expected | baseline top-5 | candidate top-5 |
|---|---|---|---|---|---|
| qa_046 | en | Who was Mahā Moggallāna? | mn37, sn40.1 | sn51.31, sn40.1, sn51.14, an6.34, an6.34 | an1.188-197, sn40.5, sn40.7, sn6.5, mn107 |

---

Regenerate: `python scripts/eval_pali_glossary.py` (Qdrant + Postgres + GPU, ~30 s).
