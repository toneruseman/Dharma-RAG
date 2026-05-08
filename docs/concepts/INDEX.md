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
| [12 — Parent/child retrieval (small-to-big)](12-parent-child-retrieval.md) | день 18 | ✅ |
| [13 — RAG-service contract (`/api/query`)](13-rag-service-contract.md) | день 19 | ✅ |
| [14 — Pāli глоссарий и query expansion](14-pali-glossary.md) | rag-day-23 | ✅ |
| [15 — Answer generation (`/api/answer`)](15-answer-generation.md) | rag-day-24 | ✅ |
| [16 — OpenAPI typegen для frontend](16-openapi-typegen.md) | app-day-03 | ✅ |
| [17 — Базовый layout `web/`](17-base-layout.md) | app-day-04 | ✅ |
| [18 — Reading Room MVP](18-reading-room.md) | app-day-21 | ✅ |
| [19 — Chat MVP](19-chat-mvp.md) | app-day-22 (re-prioritised from day-38) | ✅ |
| [20 — Hover-preview для citations](20-citation-hover-preview.md) | app-day-23 | ✅ |
| [21 — Confidence indicator](21-confidence-indicator.md) | app-day-24 | ✅ |
| [22 — SSE streaming](22-sse-streaming.md) | app-day-25 | ✅ |
| [23 — Feedback widget 👍/👎](23-feedback-widget.md) | app-day-26 | ✅ |
| [24 — Pull-quote side panel](24-pull-quote-side-panel.md) | app-day-27 | ✅ |
| [25 — BYOK UI](25-byok-ui.md) | app-day-28 | ⏸ deferred (см. ниже) |
| [26 — Retrieval failure analysis](26-failure-analysis.md) | rag-day-26 | ✅ |
| [27 — qa_040 anomaly investigation](27-qa040-anomaly.md) | rag-day-27 | ✅ |
| [28 — Definitional expansion + foundational mapping](28-definitional-expansion.md) | rag-day-28 | ✅ |
| [29 — BM25 translation bridge](29-bm25-translation-bridge.md) | rag-day-29 | ✅ |
| [30 — Russian foundational expansion](30-russian-foundational-expansion.md) | rag-day-30 | ✅ |
| [32 — Cumulative re-eval (28+29+30)](32-cumulative-eval.md) | rag-day-32 | ✅ |
| [33 — Khuddaka Nikāya ingest](33-khuddaka-ingest.md) | rag-day-33 | ✅ |
| [34 — Russian SC translations ingest](34-russian-sc-ingest.md) | rag-day-34 | ✅ |
| [35 — Failure-driven curation + Context A/B](35-failure-driven-curation.md) | rag-day-35 | ✅ |

## Что появится позже

| Концепт | План |
|---|---|
| 21 — Reading Room outline + hover-glossary | переехало на app-day-25+ |
| 22 — Search UI с фильтрами | app-day-31+ |
| 23 — Citation verification | rag-day-30+ |
| 24 — Production deployment | app-day-53+ |

> **Концепт 25 (BYOK UI) — deferred.** Решение 2026-05-02: BYOK-модель
> убивает onboarding для не-tech аудитории; в prod пока крутится единый
> OPENROUTER_API_KEY владельца. Возвращаемся к концепту когда появится
> public-launch с грантом / sponsorship'ом / donor-моделью —
> rate-limit + budget-cap layer станет критичным, BYOK будет
> опциональным upgrade для power-users.

## Сводный layer над концептами

Если нужен **integration view** (всё вместе), а не deep-dive по одному концепту — это два документа уровнем выше:

- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — модули, data flow, storage, dependencies
- [docs/RAG_PIPELINE.md](../RAG_PIPELINE.md) — runtime trace одного `POST /api/query` со spans и diagram'ами

Concepts здесь объясняют **зачем** каждый кусок устроен именно так; ARCHITECTURE/PIPELINE объясняют **как они вместе работают**.

## Если ты в новом чате

Покажи новому ассистенту ссылки:

- [docs/ARCHITECTURE.md](../ARCHITECTURE.md) — single-page обзор системы
- Этот INDEX
- [docs/RAG_DEVELOPMENT_PLAN.md](../RAG_DEVELOPMENT_PLAN.md) — общий план
- [docs/STATUS.md](../STATUS.md) — что закрыто, что в работе
- [docs/decisions/0001-phase1-architecture.md](../decisions/0001-phase1-architecture.md) — авторитетное архитектурное решение

Этого достаточно, чтобы новый ассистент понял проект.
