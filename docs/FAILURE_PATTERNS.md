# Failure analysis на golden v0.0_extended (rag-day-26)

> **RELATIVE — NOT AUTHORITATIVE.** Анализ синтетического golden v0.0e
> (n=100). Категоризация — manual review топ-15 худших запросов на
> production-конфиге `dharma_v2 + rerank=False + expand_parents=True`,
> top_k=100. Цель — превратить 55% «провалов» в обоснованный roadmap по
> ROI (см. concept [docs/concepts/26-failure-analysis.md](concepts/26-failure-analysis.md)).
>
> Для абсолютных утверждений нужен **buddhologist-curated golden v0.1**
> (B-001 blocker в `docs/STATUS.md`).

## Метаданные прогона

- **Дата:** 2026-05-02
- **Git commit:** `0162538`
- **Golden:** `docs/eval/golden_v0.0_extended.yaml` (version=0.0-synthetic-extended, n=100)
- **Production config:** `collection=dharma_v2`, `rerank=False`, `expand_parents=True`, `top_k=100`
- **Скрипт:** `scripts/eval_failure_analysis.py --top-n 15`
- **Raw output:** `tmp/failure_analysis_raw.txt`

## Headline

| Метрика | Значение |
|---|---:|
| ref_hit@5 | 0.450 |
| ref_hit@20 | 0.650 |
| Fully missed (ref_rank=∞ at top_k=100) | **24/100** |

24 запроса из 100 не находят эталонную сутту вообще ни в первой
сотне результатов. Это не near-miss («эталон в top-30, чуть-чуть не
дотянули»), а полные системные мисса. Если bы это были near-miss'ы —
помог бы reranker или больший top_k. Полный мисс означает, что
embedding **не схватывает связь** между запросом и эталонной суттой.

## Топ-15 худших — категоризация

Все 15 — `ref_rank=∞`. Раскладка по типам failure:

| # | qa_id | Запрос | Expected | Категория |
|---|---|---|---|---|
| 1 | qa_004 | Tell me about the discourse on loving-kindness | snp1.8, kn1.9 | **C — verse/short-text** |
| 2 | qa_010 | How should a layperson live? | dn31 | **A — golden-narrow** |
| 3 | qa_011 | Teachings on the four jhānas | mn10, dn22, mn27, an4.41 | **A — golden-narrow** |
| 4 | qa_027 | Teachings on monastic ethics and self-discipline | mn6, an10.61, mn39 | **B — abstract topical** |
| 5 | qa_033 | What is metta meditation? | snp1.8, sn46.54 | **C — verse/short-text** |
| 6 | qa_037 | What is the Fire Sermon? | sn35.28 | **D — English title** |
| 7 | qa_039 | Tell me about Bāhiya | ud1.10 | **A — golden-narrow** |
| 8 | qa_040 | What is satipaṭṭhāna? | mn10, dn22 | **F — definitional anomaly** |
| 9 | qa_045 | Who was Sāriputta? | mn3, mn5, sn55.4 | **A — golden-narrow** |
| 10 | qa_048 | What is the simile of the chariot? | sn5.10 | **A — golden-narrow** |
| 11 | qa_049 | Что такое самадхи? | an4.41, sn40.10 | **E — Russian lexical** |
| 12 | qa_053 | What is the role of generosity in spiritual progress? | an4.61, an5.36, an8.36 | **B — abstract topical** |
| 13 | qa_055 | What distinguishes a noble disciple from an ordinary person? | sn22.99, mn22 | **B — abstract topical** |
| 14 | qa_057 | How does the Buddha describe the path to awakening? | dn2, mn27, mn39 | **B — abstract topical** |
| 15 | qa_061 | Что Будда говорит о медитации випассана? | an4.94, mn149 | **E — Russian lexical** + A |

## Кластеры

| Категория | Count | Что означает |
|---|---:|---|
| **A — golden-narrow** (specific-vs-entity, ambiguous reference) | 5–6/15 | Эталонная разметка слишком узкая. Retrieval нашёл *легитимные* альтернативы, не «expected». Например, qa_011 «four jhānas»: golden ждёт mn10/dn22/mn27/an4.41, но retrieval вернул mn65, который **содержит полную jhāna pericope в открытом виде**. Ground truth wrong / underspecified. |
| **B — abstract topical query** | 4/15 | Запрос абстрактный про мульти-канон тему («monastic ethics», «generosity», «noble disciple», «path to awakening»). Тема покрыта десятками сутт, retrieval вернул valid'ные, но не точные expected. |
| **C — verse / short-text mismatch** | 2–3/15 | Эталон — Sutta Nipāta / Khuddaka Nikāya короткие verse-тексты (snp1.8, kn1.9, sn46.54). Embedding не выделяет их среди prose-сутт о той же теме. Возможно артефакт chunking'а: verse-стих короче child-chunk-size, перемешивается с соседями. |
| **D — English title** | 1/15 | «Fire Sermon» — английское название sn35.28. Корпус — переводы Sujato, в текстах title не написан буквально «fire sermon». Без glossary mapping `English title → canonical_id` retrieval не справляется. |
| **E — Russian lexical** | 2/15 | Кириллический транслит («самадхи», «випассана») не находит английский корпус. Glossary expansion (rag-day-23 / cyrillic.yaml) **частично работает** — qa_061 нашёл dn22+mn10 в top-5, но expected (an4.94/mn149) — другая категория сутт. |
| **F — definitional anomaly** | 1/15 | qa_040 «What is satipaṭṭhāna?» — foundational термин, expected mn10+dn22 (THE двух базовых сутт). Retrieval вернул `sn47.x` — связанные, но НЕ foundational. На русском («что такое сатипаттхана») mn10+dn22 находятся (qa_061). На английском — нет. **Серьёзный аномальный кейс**. |

## Critical insight

**Большая часть «провалов» — артефакт synthetic-разметки, а не реальный quality gap retrieval'а.**

Если буддолог разметит `expected_works` шире (категория A — 5–6/15) и
abstract topical (B — 4/15) сольёт в «multiple valid answers» — то
~9–10 из 15 топ-failures **перестанут считаться failures**. На
synthetic golden v0.1 (с буддологической разметкой) `ref_hit@5`
может вырасти до 0.55–0.65 без любых ML-улучшений retrieval'а.

Это не значит, что retrieval идеален. Это значит, что **до буддолога
дальнейший «slot machine» ML-tuning тратит время впустую** — мы
оптимизируем под шум разметки.

## Recommendations — следующие rag-day'и по ROI

| Категория | Count | Priority | Fix |
|---|---:|---|---|
| **A + B (golden-narrow / abstract topical)** | 9–10/15 | **One-off (B-001 blocker)** | Buddhologist-curated golden v0.1: разметить `expected_works` шире (≥3 valid suttas per query), добавить `acceptable_works` поле для multi-canonical topics. Без этого все cheap fixes ниже частично невидимы. |
| **C — verse / short-text** | 2–3/15 | **High** | Audit chunking для Sutta Nipāta / Khuddaka Nikāya / Dhammapada / Udāna. Гипотеза: короткие verse-сутты падают как child-chunks, перемешиваются с prose-соседями. Возможен fix: **отдельная стратегия чанкинга для verse** (chunk = entire sutta когда n_tokens < threshold). Дешёвый, локальный, может фикснуть >2 visible failures + скрытые. |
| **D — English title** | 1/15 | **Medium** | Mapping table «английских titles → canonical_id»: Fire Sermon → sn35.28, Heart of Wisdom Discourse → mn26, etc. Маленькая yaml в `data/glossary/en_titles.yaml`, query expansion как Pali glossary. Низкий volume в golden, но real-world пользователи будут использовать ~часто. |
| **E — Russian lexical** | 2/15 | **High** | Расширить `data/glossary/cyrillic.yaml` ключевыми терминами: самадхи, випассана, метта, дхамма, ниббана, аскетизм/аскеза, нравственность, страдание, воздаяние, etc. Дешёвый фикс. Параллельно проверить — почему qa_049 «самадхи» не работает, хотя rag-day-23 cyrillic glossary существует (вероятно термина нет в файле). |
| **F — qa_040 satipaṭṭhāna anomaly** | 1/15 | **High** | Deep dive: ручной retrieve mn10/dn22 на запросе «What is satipaṭṭhāna?». Проверить: попадают ли они вообще в top-100? Какие child-chunks матчатся (или не матчатся)? Контекстуальный prompt v2 — может ли он быть проблемой? Single anomaly, но foundational case — если найдём root cause, фикс может улучшить много скрытых failures. |
| Multi-source ingest (Phase 3 — ATI / DhammaTalks / Russian) | n/a | **Medium** | Анализ показал что **качество gap не сводится к content coverage**. Сначала чиним chunking + glossary (cheap wins), потом ingest. |
| Knowledge graph (Phase 4) | n/a | **Low** | Ни один из топ-15 — не multi-hop reasoning. Отложено как и было. |
| Reranker / fine-tuning | n/a | **Low** | Не помогут полным miss'ам (ref_rank=∞ в top-100): reranker не вытащит из ниоткуда. Dataload-проблема, не ranking. |

## Предлагаемая последовательность следующих rag-day'ев

1. **rag-day-27 — Investigate qa_040 anomaly** (1 день). Глубокий разбор «What is satipaṭṭhāna?». Если найдём системный баг — может фикснуть скрытые failures. Если нет — данные для буддолога.
2. **rag-day-28 — Russian glossary expansion** (1 день). Расширить cyrillic.yaml: ~30 ключевых терминов. Проверить retrieval на qa_049, qa_061 после.
3. **rag-day-29 — English titles glossary** (0.5 дня). yaml + integration в query expansion. Lookup before encoding.
4. **rag-day-30 — Verse-aware chunking** (2–3 дня, если приоритет подтверждается). Audit Sutta Nipāta / Dhammapada / Udāna; отдельная стратегия для коротких verse-сутт.
5. **rag-day-31 — Golden v0.1 от буддолога** (B-001 blocker). После — повторный failure analysis на v0.1; ожидание ref_hit@5 ≥ 0.60.
6. **Multi-source ingest** (Phase 3) — после v0.1, чтобы baseline'ы были устойчивы перед расширением корпуса.

## Связанные документы

- [docs/concepts/26-failure-analysis.md](concepts/26-failure-analysis.md) — концепт-док метода
- [docs/EVAL_ABLATION_v0.0e.md](EVAL_ABLATION_v0.0e.md) — 8-cell ablation, baseline ref_hit@5=0.450
- [docs/concepts/09-eval-and-golden-set.md](concepts/09-eval-and-golden-set.md) — про golden set и метрики
- [docs/concepts/14-pali-glossary.md](concepts/14-pali-glossary.md) — Pali / cyrillic glossary (impact: категория E)
- [docs/RAG_DEVELOPMENT_PLAN.md](RAG_DEVELOPMENT_PLAN.md) — план следующих фаз; результаты этого анализа меняют приоритет дней 27+
- [docs/STATUS.md](STATUS.md) — B-001 (buddhologist-curated golden v0.1)

## Reproduce

PowerShell single-line:

```
.venv\Scripts\python.exe scripts/eval_failure_analysis.py --top-n 15 > tmp/failure_analysis_raw.txt
```

Затем перенести записи + категоризовать вручную (как в этом документе).
