# Project Status

> Единый индекс прогресса по обоим трекам разработки (RAG-ядро и App-слой).
> Обновляется вручную при закрытии каждого `*-day-NN`.
>
> **Source of truth:** git log + этот файл. Чаты не являются source of truth.

- **Версия:** 2026-04-22
- **Ветка:** `dev` (активная: `feat/rag-day-10-qdrant-indexing`)
- **Последний релиз:** `v0.0.3` — Retrieval Foundation (2026-04-22)
- **Следующий milestone:** v0.1.0 Foundation (rag-day-21)
- **Стратегия:** **B** — RAG-first до `v0.1.0` (`rag-day-21`), затем интерливинг RAG+APP

---

## Как читать этот файл

Два параллельных плана, один репо, один чат:

- [`docs/RAG_DEVELOPMENT_PLAN.md`](RAG_DEVELOPMENT_PLAN.md) — RAG-ядро (120 дней, 4 фазы)
- [`docs/APP_DEVELOPMENT_PLAN.md`](APP_DEVELOPMENT_PLAN.md) — App-слой (60 дней + Phase 7+)

Дни нумеруются раздельно: `rag-day-NN` и `app-day-NN`. Commits помечаются соответствующим префиксом.

---

## Текущий прогресс

### RAG-трек

| Day | Задача | Статус | Коммит |
|---|---|---|---|
| rag-day-01 | Docker Compose + FastAPI `/health` + config + logging | ✅ Done | `36f5846` |
| rag-day-02 | Postgres schema FRBR + Alembic миграции | ✅ Done | `d5eac80` |
| rag-day-03 | Скачать SuttaCentral bilara-data + parser dry-run | ✅ Done | `4618a5d` |
| rag-day-04 | Full ingest SuttaCentral (Sujato EN для MN/DN/SN/AN) | ✅ Done | `8ef9519` |
| rag-day-05 | **Gate:** Golden v0.1 от буддолога (30 QA) | 🚧 Blocked | Нужен буддолог на связи |
| rag-day-06 | Cleaner: Unicode NFC, Pali диакритика (IAST + ASCII-fold) | ✅ Done | `ce186c5` |
| rag-day-07 | Структурный chunker (384 child / 1024-2048 parent) | ✅ Done | `6c8ff98` |
| rag-day-08 | FlagEmbedding + BGE-M3 (dense + sparse на 100 чанках) | ✅ Done | `9f7e092` |
| rag-day-09 | Phoenix observability + OpenInference | ✅ Done | `c2defe2` |
| rag-day-10 | Qdrant collection `dharma_v1` + named vectors + full ingest (6478 child chunks, 4:40 min on 1080 Ti) | ✅ Done | `330ff30` |
| rag-day-11 | BM25 via Postgres FTS (`simple` config on `text_ascii_fold`, GIN index, generated column) | ✅ Done | `3627685` |
| rag-day-12 | Hybrid RRF (dense + sparse + BM25) + `POST /api/retrieve`, 62-96 ms/query on GPU | ✅ Done | `37df139` |
| docs/concepts | Учебная библиотека: 10 концептов на русском (RAG, FRBR, chunking, BGE-M3, Qdrant, BM25, RRF, Phoenix, eval) | ✅ Done | (this branch) |
| docs/eval/golden_v0.0 | Synthetic golden set, 30 QA, разблокирует day-14 eval без буддолога | ✅ Done | `e6d024f` |
| rag-day-13 | BGE-reranker-v2-m3 cross-encoder + Phoenix per-stage spans + `rerank` API flag | ✅ Done | (this branch) |
| … | (всего 120 дней в плане) | | |

### App-трек

| Day | Задача | Статус | Коммит |
|---|---|---|---|
| app-day-01 | pnpm monorepo + `web/` Next.js 14 scaffold + shadcn/ui | ⏳ Next | — |
| app-day-02 | `src/rag/schemas.py` + `StubRAGService` + контракт | 📋 Planned | — |
| app-day-03 | OpenAPI → TypeScript типы для фронта | 📋 Planned | — |
| app-day-04 | Next.js layout + темы + дизайн-токены | 📋 Planned | — |
| app-day-05 | Docker Compose dev-friendly (web + api + services) | 📋 Planned | — |
| app-day-06 | Postgres schema для app-таблиц (audit_log, refused_queries, feedback) | 📋 Planned | — |
| … | (всего 60 дней в плане) | | |

---

## Блокеры

| ID | Что | Срочность | Кто разблокирует |
|---|---|---|---|
| B-001 | Нет буддолога на связи для golden set v0.1 | Высокая (блокирует rag-day-05 и все последующие quality-метрики) | Человек, не код |
| ~~B-002~~ | ~~`docs/old/` содержит устаревшие параметры~~ | ✅ Closed | Удалено в `399bda2` |
| B-001 (re-scoped) | Buddhologist for golden eval set | Был блокером, **deferred until proof-of-concept ready** | Synthetic v0.0 покрывает iteration; v0.1 authoritative нужна перед public release |
| B-004 | Re-introduce CI using uv | Перед v0.1.0 release (day 21) | [#20](https://github.com/toneruseman/Dharma-RAG/issues/20) |

---

## Критические интеграционные точки

Моменты, когда треки встречаются и контракт должен совпасть:

1. **`src/rag/schemas.py` zafiksируется на app-day-02.** RAG-трек обязан реализовать протокол именно с этими schemas.
2. **`RAGService` имплементация появится в RAG-треке примерно на rag-day-14–21.** До этого app-трек работает на `StubRAGService`.
3. **app-day-19 (audit log) требует** Postgres schema из rag-day-02. Порядок: rag-day-02 → app-day-06 → app-day-19.
4. **Phoenix в prod (app-day-58)** использует ту же инстанцию, что RAG-трек ставит на rag-day-09.

---

## Последовательность выполнения (стратегия B)

**Фаза A (дни 1–21): строго RAG.** Phase 1 Foundation из RAG-плана без отвлечения на APP. Цель — рабочий `RAGService` на реальном корпусе SuttaCentral с baseline-метриками.

```
rag-day-02  Postgres FRBR schema + Alembic
rag-day-03  SuttaCentral bilara parser (dry-run)
rag-day-04  Full ingest SuttaCentral EN (Sujato)
rag-day-05  Golden v0.1 от буддолога (blocked)
rag-day-06  Cleaner: NFC + Pali diacritic normalization
rag-day-07  Structural chunker (384 child / 1024-2048 parent)
rag-day-08  BGE-M3 embedding inference
rag-day-09  Phoenix observability
rag-day-10  Qdrant dharma_v1 named vectors + ingest
rag-day-11  BM25 через Postgres FTS
rag-day-12  Hybrid retrieval (RRF)
rag-day-13  BGE-reranker-v2-m3
rag-day-14  Первый eval (baseline)
rag-day-15  Contextual prompt-template
rag-day-16  Full re-ingest dharma_v2
rag-day-17  A/B v1 vs v2
rag-day-18  Parent-child expansion
rag-day-19  /api/query endpoint (RAG-ядро)
rag-day-20  docs update
rag-day-21  v0.1.0 release
```

**Фаза B (дни 22+): интерливинг.** RAG Phase 2 (quality loop) идёт фоном, APP-трек стартует параллельно от `app-day-01`. Промежуточные дни смешиваются по принципу «тяжёлый RAG → лёгкий APP» или наоборот.

**Блокер B-001 (буддолог)** не останавливает всю Фазу A — `rag-day-05` выполняется в фоне, пока идут технические дни. Если к дню 14 буддолога нет, используем временный synthetic golden v0.0 для baseline, а человеческий v0.1 приходит позже.

---

## Policy

1. **Каждый закрытый day** → обновление этой таблицы + короткая запись в `CHANGELOG.md`.
2. **Каждые 5 дней** → ревью блокеров, перепланирование если нужно.
3. **Расхождение с ADR** → новый ADR (0002, 0003…).
4. **Feature branches:** `feat/rag-day-NN-slug` или `feat/app-day-NN-slug`.
5. **Коммиты:** conventional commits с префиксом трека: `feat(rag): rag-day-02 Postgres FRBR schema`.
