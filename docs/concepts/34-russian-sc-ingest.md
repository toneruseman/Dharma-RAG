# 34 — SuttaCentral Russian translations ingest (вместо theravada.ru scraping)

> **Статус:** реализовано (rag-day-34, 2026-05-08).
> Загружаем русские переводы из SuttaCentral bilara-data — переводы
> от Sergey V. (тот же человек что theravada.ru SV), O., Khantibalo,
> и от пары Narinyani-Evmenenko. **Без web scraping'а** — данные уже
> локально под `data/raw/suttacentral/translation/ru/`.

## Что это простыми словами

Изначальный план был scraping theravada.ru ради русских переводов. При
пред-проверке выяснилось:

1. SuttaCentral bilara-data **уже содержит** русские переводы 4
   переводчиков под общим CC0 license (одно покрытие как theravada.ru,
   плюс другие переводчики).
2. Переводчик `sv` на SC = тот же Sergey V. что и SV на theravada.ru
   (one and the same person).
3. Файлы уже скачаны локально с rag-day-03 как часть полного
   bilara-data checkout — нужно только **ingest** их с
   `--language ru --author <slug>`.

Вместо 2-3 дней работы (scraping → HTML parser → cleaner → license
review → canonical_id mapping) — получили **30 минут** ingest'а
существующим `ingest_sc.py`.

## Что добавили

Состав:

| Translator | Files | Chunks | Nikāya |
|---|---:|---:|---|
| `sv` (Sergey V.) | 885 | 3274 | AN, MN, SN, KN |
| `o` (O.) | 565 | 1236 | AN, DN, MN, SN, KN, vinaya |
| `khantibalo` | 5 | 249 | small KN |
| `narinyanievmenenko` | 0 | 0 | (filtered out — only blurbs) |
| **Total** | **1455** | **4759** | все 5 Nikāya |

`narinyanievmenenko` отдала 0 sutta-файлов — все 337 файлов оказались
name-translation или blurb-меткой, ingest loader корректно их
отфильтровал.

## Pipeline (без изменения retrieval-кода)

```
1. Alembic 006: seed author_t для sv/o/khantibalo/narinyanievmenenko
2. ingest_sc.py --language ru --author sv          → 885 → 3274 chunks
3. ingest_sc.py --language ru --author o           → 565 → 1236 chunks
4. ingest_sc.py --language ru --author khantibalo  →   5 →  249 chunks
   (narinyanievmenenko: 0 sutta-files, skipped)
5. contextualize_corpus.py                         → ~3085 children → ~$3-6
6. reindex_qdrant_v2.py                            → ~12238 points GPU 30+ min
```

Идея:

- **Same Work, multiple Expressions.** Уже существующая `Work(canonical_id='mn1')`
  имеет English Expression (Sujato) от Phase 1; rag-day-34 добавляет
  параллельные Russian Expressions (sv/o/khantibalo) под тем же Work.
- **Chunks tagged `language='rus'`** через cascade Expression →
  Instance → Chunk.
- **BGE-M3 multilingual** — кодирует Russian text напрямую, не
  переводя; русские chunks ищутся вместе с английскими в одном
  Qdrant collection `dharma_v2`.

## Решение про licenses

SuttaCentral bilara-data распространяется под **CC0** (Public Domain)
для root-text'а и под индивидуальными licenses для translations
(big-picture: free distribution для наших non-commercial / open-source
целей). Конкретно русские переводчики:

- `sv`: SC publishes CC-licensed (need to confirm specific in
  bilara-data per-author license file)
- `o`: same
- `khantibalo`, `narinyanievmenenko`: same

Нет нужды в отдельном legal review для Phase 1 / 2 (research,
non-commercial). Перед public Yoniso (когда поднимем) — explicit
license check для каждого RU автора.

## Почему это лучше theravada.ru scraping

| Аспект | SC RU ingest | theravada.ru scraping |
|---|---|---|
| Время | 30 мин | 2-3 дня |
| Web requests | 0 | тысячи (rate-limited) |
| Legal review | done (SC umbrella) | per-translator |
| Canonical_id mapping | автоматический | manual fuzzy |
| Cleaner | существующий | новый HTML→text |
| Robots.txt compliance | irrelevant | ~5 файлов исключены |
| Translator slugs | стабильные | inconsistent |

theravada.ru остаётся **kandidat** на отдельный rag-day когда нужен
будет контент за пределами того, что SC publishes — и тогда уже с
explicit legal authorization от user'а.

## Что НЕ сделали

- **Pāli root parallel** — Russian Expressions не сопровождаются
  Pāli root Instance параллельно. Сейчас retrieval работает на
  Russian text напрямую (BGE-M3 multilingual). Pāli root для
  cross-language search — Phase 3 multi-source feature.
- **Per-translator filtering** в `/api/query` — пока нет UI-knob
  «искать только в переводах SV». Phase 4.
- **Russian normalization** (ё/е, ять) — отложено пока не появятся
  query-проблемы. SC translators в основном современная ё/е, без
  pre-1918 reformы.

## Где в коде

| Файл | Что |
|---|---|
| `alembic/versions/20260508_006_russian_translator_seeds.py` | seed author_t для sv/o/khantibalo/narinyanievmenenko |
| `scripts/ingest_sc.py` | (без изменений) ingest с `--language ru --author <slug>` |
| `scripts/contextualize_corpus.py` | (без изменений) idempotent на pending children |
| `scripts/reindex_qdrant_v2.py` | (без изменений) idempotent UUID upsert |
| `scripts/smoke_ru.py` | (новый) smoke battery на русских запросах |

## Связанные документы

- [docs/concepts/02 — FRBR корпусная модель](02-frbr-corpus-model.md) — Work/Expression/Instance/Chunk hierarchy
- [docs/concepts/04 — BGE-M3 encoder](04-bge-m3-encoder.md) — multilingual embeddings
- [docs/concepts/14 — Pāli глоссарий](14-pali-glossary.md) — cyrillic.yaml уже здесь, дополнительно к Russian text
- [docs/concepts/30 — Russian foundational](30-russian-foundational-expansion.md) — Russian aliases в foundational.yaml
- [docs/concepts/33 — Khuddaka ingest](33-khuddaka-ingest.md) — parallel pipeline для KN

## Connected memories

- `project_dharma_rag_yoniso_split.md` — Russian audience priority for Yoniso
- `project_dharma_rag_context_model_plan.md` — план A/B Haiku 3.5 vs DeepSeek V4 перед большими ingest'ами
