# Концепты Dharma-RAG

Учебная библиотека по архитектуре проекта. Пишется по ходу разработки —
каждый завершённый «день» из плана добавляет 1-2 концепта.

## Зачем эта папка

Эта папка — **твоя справочная**. Когда ты открываешь файл из проекта и
не помнишь, зачем там та или иная штука — приходишь сюда, читаешь
соответствующий концепт, возвращаешься к коду уже с пониманием.

Каждый файл устроен одинаково:

1. **Что это** — простыми словами, без жаргона
2. **Зачем у нас** — конкретная роль в проекте
3. **Как работает** — диаграмма + пара примеров
4. **Альтернативы** — что было можно сделать иначе и почему не сделали
5. **Где в коде** — ссылки на файлы (не сам код, ты его не читаешь)

## Что уже описано

| Концепт | Соответствует дню | Готовность |
|---|---|---|
| [01 — RAG pipeline overview](01-rag-pipeline-overview.md) | весь проект | ✅ |
| [02 — FRBR корпусная модель](02-frbr-corpus-model.md) | день 2 | ✅ |
| [03 — Чанкинг parent/child](03-chunking-parent-child.md) | дни 6-7 | ✅ |
| [04 — BGE-M3 encoder](04-bge-m3-encoder.md) | день 8 | ✅ |
| [05 — Qdrant named vectors](05-qdrant-named-vectors.md) | день 10 | ✅ |
| [06 — Postgres FTS / BM25](06-postgres-fts-bm25.md) | день 11 | ✅ |
| [07 — RRF hybrid fusion](07-rrf-hybrid-fusion.md) | день 12 | ✅ |
| [08 — Observability через Phoenix](08-observability-phoenix.md) | день 9 | ✅ |
| [09 — Eval и golden set](09-eval-and-golden-set.md) | день 14, ongoing | ✅ |
| [10 — Cross-encoder reranking](10-cross-encoder-reranking.md) | день 13 | ✅ |
| [11 — Contextual Retrieval](11-contextual-retrieval.md) | дни 15-17 | ✅ (prompt v1) |

## Что появится позже

| Концепт | План |
|---|---|
| 12 — Parent-document retrieval | день 18 |
| 13 — LLM generation + prompt caching | дни 22-30 |
| 14 — Citation verification | день 30+ |
| 15 — Production deployment | дни 50+ |

## Если ты в новом чате

Покажи новому ассистенту ссылки:

- Этот INDEX
- [docs/RAG_DEVELOPMENT_PLAN.md](../RAG_DEVELOPMENT_PLAN.md) — общий план
- [docs/STATUS.md](../STATUS.md) — что закрыто, что в работе
- [docs/decisions/0001-phase1-architecture.md](../decisions/0001-phase1-architecture.md) — авторитетное архитектурное решение

Этого достаточно, чтобы новый ассистент понял проект.
