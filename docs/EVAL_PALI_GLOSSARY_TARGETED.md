# Pāli glossary mini-eval — rag-day-23 (synthetic golden v0.0-extended, n=100)

> **RELATIVE METRICS — NOT AUTHORITATIVE.** Numbers below come from
> ``golden_v0.0_extended.yaml`` (100 синтетических QA). Абсолютные
> утверждения о качестве требуют валидации буддологом — см. B-001 в
> ``docs/STATUS.md``. Дельты между конфигурациями остаются валидными
> на синтетических данных — ровно для этого файл и сделан.

## Метаданные

- **Generated**: 2026-04-28T19:38:16+00:00
- **Git commit**: `3c6e744`
- **Golden set**: `docs\eval\golden_pali_targeted.yaml` (version `0.0-pali-targeted`, n=100)
- **top_k (eval)**: 20
- **Production cell**: `dharma_v2` + rerank=False + expand=True
- **Glossary**: 50,060 DPD лемм + 284 кириллических вариантов
- **Platform**: Windows-11-10.0.26200-SP0 / Python 3.12.10

## Главный результат

| cell | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR | latency_s |
|---|---:|---:|---:|---:|---:|---:|
| baseline_no_glossary | 0.090 | 0.200 | 0.330 | 0.440 | 0.150 | 7.77 |
| candidate_with_glossary | 0.040 | 0.210 | 0.340 | 0.490 | 0.126 | 6.89 |

**Δ ref_hit@5 = +1.0 pp**, **Δ MRR = -0.024**

## Вывод

Глоссарий **нейтрален** на overall (Δ=1.0 pp). Default остаётся `False` — не флипаем без явного выигрыша. Возможно есть локальный лифт на bare-Pāli/RU подмножестве — см. breakdown по языку ниже.

### baseline_no_glossary — по языку

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| mixed | 20 | 0.100 | 0.250 | 0.450 | 0.500 | 0.166 |
| pli | 30 | 0.033 | 0.167 | 0.300 | 0.400 | 0.112 |
| ru | 50 | 0.120 | 0.200 | 0.300 | 0.440 | 0.167 |

### candidate_with_glossary — по языку

| language | n | ref_hit@1 | ref_hit@5 | ref_hit@10 | ref_hit@20 | MRR |
|---|---:|---:|---:|---:|---:|---:|
| mixed | 20 | 0.050 | 0.300 | 0.450 | 0.500 | 0.153 |
| pli | 30 | 0.000 | 0.200 | 0.367 | 0.533 | 0.108 |
| ru | 50 | 0.060 | 0.180 | 0.280 | 0.460 | 0.126 |

### Δ ref_hit@5 по языку

| language | n | baseline | candidate | Δ pp |
|---|---:|---:|---:|---:|
| mixed | 20 | 0.250 | 0.300 | +5.0 |
| pli | 30 | 0.167 | 0.200 | +3.3 |
| ru | 50 | 0.200 | 0.180 | -2.0 |

## Failure-анализ (top-5)

Глоссарий **починил** 10 запросов, **сломал** 9.

### Fixed by glossary

| id | lang | query | expected | candidate top-5 |
|---|---|---|---|---|
| qa_016 | ru | Что такое осознанность в буддизме? | mn10, dn22 | dn10, mn10, sn47.18, mn39, dn22 |
| qa_019 | ru | Что такое анапанасати? | mn118 | mn62, mn118, mn118, sn54.19, sn54.4 |
| qa_043 | ru | Что такое равностность в практике? | mn7, an4.125 | sn42.13, mn140, mn105, an11.454-501, an4.125 |
| qa_058 | pli | ānāpānasati | mn118 | mn62, mn118, mn118, sn54.3, sn54.4 |
| qa_059 | pli | satipaṭṭhāna kāye | mn10, dn22 | sn47.18, sn47.4, sn47.44, mn10, sn47.43 |
| qa_073 | pli | saṃyojana orambhāgiya | an10.13 | an9.67, an10.13, sn45.179, sn55.25, sn22.120 |
| qa_078 | pli | kamma vipāka | mn136, an4.232 | an10.218, an6.63, an10.217, mn136, mn60 |
| qa_079 | pli | saṃsāra anamatagga | sn15.1, sn15.3 | sn15.9, sn15.2, sn15.11, sn15.8, sn15.1 |
| qa_083 | mixed | Как практиковать ānāpānasati? | mn118 | mn62, mn118, mn118, mn62, sn54.3 |
| qa_097 | mixed | Чем брахмавихара отличается от джханы? | mn7, mn36 | an3.63, mn97, mn99, an3.63, mn7 |

### Regressed by glossary

| id | lang | query | expected | baseline top-5 | candidate top-5 |
|---|---|---|---|---|---|
| qa_006 | ru | Что такое благородный восьмеричный путь? | mn117, sn45.8 | sn45.8, mn103, sn38.3, mn103, an10.133 | sn45.39, sn45.19, sn45.40, sn43.11, sn45.153 |
| qa_032 | ru | Что такое карма в буддизме? | mn135, an3.34 | mn135, mn103, sn3.20, mn103, mn57 | an10.217, an4.234, an4.233, mn57, an4.234 |
| qa_035 | ru | Как карма работает после смерти? | mn136, mn143 | mn136, mn103, mn136, mn103, mn135 | an10.217, mn57, an10.218, an4.233, an4.234 |
| qa_048 | ru | Что говорил Будда о смерти? | mn143, sn3.22 | an4.184, mn103, sn3.22, mn103, dn16 | mn1, dn29, mn123, dn16, sn46.52 |
| qa_053 | pli | paṭiccasamuppāda | sn12.1, sn12.2 | an10.92, sn12.1, sn12.60, sn35.113, sn12.37 | sn35.113, an10.92, mn38, sn12.24, sn12.23 |
| qa_056 | pli | anattalakkhaṇa sutta | sn22.59 | sn22.11, sn22.59, sn12.55, mn35, mn24 | an3.47, an5.141, an4.73, mn113, an5.146 |
| qa_069 | pli | brahmavihāra bhāvanā | mn7, dn13 | mn99, dn27, mn7, mn118, an3.63 | mn99, dn25, sn42.13, dn33, an11.15 |
| qa_070 | pli | mettābhāvanā | an11.16, an4.125 | an11.15, an8.1, an4.125, sn42.13, an11.16 | an11.15, an8.1, sn42.13, sn20.4, sn20.3 |
| qa_086 | mixed | В каких суттах говорится о nibbāna? | an9.34, mn26 | an3.55, an9.48, sn38.1, an6.101, an9.34 | an9.48, an7.55, an3.55, sn38.1, an6.101 |

---

Regenerate: `python scripts/eval_pali_glossary.py` (Qdrant + Postgres + GPU, ~30 s).
