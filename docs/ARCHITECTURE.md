# Architecture

> Integration-уровень: как устроен Dharma-RAG в целом. Per-component
> deep dive — в [`docs/concepts/`](concepts/INDEX.md), решения и
> trade-offs — в [`docs/decisions/`](decisions/), статус — в
> [`STATUS.md`](STATUS.md).

**Авторитет:** [ADR-0001](decisions/0001-phase1-architecture.md) — фиксированный стек Phase 1. Этот файл его описывает, не переопределяет.

---

## Один экран про систему

Dharma-RAG — **citation-first** retrieval-сервис над буддийским каноном (SuttaCentral, Sujato EN). На вход — вопрос, на выход — ранжированный список passage'ей со ссылками на канонические работы (`mn10`, `sn56.11`). LLM-генерация и UI — отдельные слои на день 22+ и app-day-01+.

Архитектура — три уровня:

```
┌────────────────────────────────────────────────────────┐
│  API layer        FastAPI                              │
│                   POST /api/query   POST /api/retrieve │
├────────────────────────────────────────────────────────┤
│  Service layer    RAGService → hybrid_search           │
│                   (encode, fuse, enrich, rerank?)      │
├────────────────────────────────────────────────────────┤
│  Storage layer    Postgres FRBR + FTS                  │
│                   Qdrant dharma_v2 (named vectors)     │
└────────────────────────────────────────────────────────┘
```

Pipeline view с конкретными тайминами и spans — в [`RAG_PIPELINE.md`](RAG_PIPELINE.md).

---

## Module map

### `src/api/` — HTTP layer

| Файл | Что делает | Stable? |
|---|---|---|
| `app.py` | FastAPI factory, lifespan, /health, mount роутеров | yes |
| `retrieve.py` | `POST /api/retrieve` — внутренний endpoint с полной диагностикой (rrf_score, per_channel_rank, rerank_score). Используется eval-скриптами и smoke-тулзами | **внутренний** — surface свободно эволюционирует |
| `query.py` | `POST /api/query` — публичный endpoint с замороженным контрактом. Что вызывают LLM-сервис, фронт, бот | **frozen** |

`retrieve.py` владеет singleton'ом `RetrievalResources` (encoder + reranker + Qdrant + DB pool). `query.py` берёт его через `get_resources()` — вторая копия BGE-M3 (2.3 ГБ) не грузится.

### `src/rag/` — public service layer

`POST /api/query` контракт. На app-day-02 этот модуль зафиксируется как integration point между RAG-track и App-track.

| Файл | Что |
|---|---|
| `schemas.py` | `QueryRequest`, `Source`, `QueryResponse`, `PipelineMetadata` (frozen pydantic) |
| `service.py` | `RAGService.query()` — оборачивает `hybrid_search`, нормализует score в [0, 1], применяет `forbidden_works` post-filter, строит `PipelineMetadata` |

Концепт: [`13 — RAG-service contract`](concepts/13-rag-service-contract.md).

### `src/retrieval/` — hybrid search engine

| Файл | Что |
|---|---|
| `hybrid.py` | Оркестратор. 5 stages: encode → 3 каналов параллельно → RRF → enrich (SQL JOIN с parent expansion) → optional rerank |
| `rrf.py` | Reciprocal Rank Fusion (k=60), pure-function |
| `dense.py` | Dense channel — вызов Qdrant `query_points` через named vector `bge_m3_dense` |
| `sparse.py` | Sparse channel — Qdrant `query_points` через named vector `bge_m3_sparse` |
| `bm25.py` | BM25 channel — Postgres FTS на `chunk.fts_vector` (GIN index) |
| `reranker.py` | BGE-reranker-v2-m3 cross-encoder. Lazy 1.1 ГБ |
| `schemas.py` | `ChannelHit`, `HybridHit` (с `child_text`, `expanded`) |

Концепты: [`07 — RRF`](concepts/07-rrf-hybrid-fusion.md), [`10 — reranker`](concepts/10-cross-encoder-reranking.md), [`12 — parent/child`](concepts/12-parent-child-retrieval.md).

### `src/embeddings/` — BGE-M3 + Qdrant indexing

| Файл | Что |
|---|---|
| `bge_m3.py` | Wrapper над FlagEmbedding's BGEM3FlagModel. fp16 на CUDA, fp32 fallback. Возвращает `EncodedBatch(dense, sparse)` |
| `indexer.py` | Stream from Postgres → encode → upsert в Qdrant. Используется `scripts/index_qdrant.py` (v1) и `scripts/reindex_qdrant_v2.py` (v2 с context prefix) |

Концепты: [`04 — BGE-M3`](concepts/04-bge-m3-encoder.md), [`05 — Qdrant named vectors`](concepts/05-qdrant-named-vectors.md).

### `src/db/` — Postgres data layer

| Файл | Что |
|---|---|
| `base.py` | SQLAlchemy 2.x declarative base |
| `session.py` | Async engine (asyncpg) + `AsyncSession` factory |
| `models/frbr.py` | FRBR четыре уровня: `Work`, `Expression`, `Instance`, `Chunk` |
| `models/lookups.py` | `Author`, `Translator`, `License`, лоокапы |

FRBR-обоснование: [`02 — FRBR`](concepts/02-frbr-corpus-model.md). Миграции — `alembic/versions/`:

- `001_initial_frbr` — базовые таблицы
- `002_author_slug_sc_seeds` — справочники
- `003_chunk_fts_vector` — `tsvector` GENERATED + GIN index (BM25)
- `004_chunk_contextual_columns` — `chunk.context_text/version/model` (Contextual Retrieval)

### `src/ingest/` — корпус → Postgres

| Файл | Что |
|---|---|
| `suttacentral/parser.py` | Парсинг SuttaCentral bilara-data JSON |
| `suttacentral/loader.py` | Загрузка в Postgres FRBR |
| `suttacentral/models.py` | Pydantic intermediate types |

CLI-обёртка: `scripts/ingest_sc.py`.

### `src/processing/` — chunking + cleaning

| Файл | Что |
|---|---|
| `cleaner.py` | Unicode NFC, Pāli ASCII-fold (`text_ascii_fold`), HTML strip |
| `chunker.py` | Структурный: parent (1024-2048 токенов) + child (~384) с self-reference через `chunk.parent_chunk_id` |

Концепт: [`03 — chunking`](concepts/03-chunking-parent-child.md). CLI: `scripts/rechunk.py`.

### `src/contextual/` — Contextual Retrieval (Anthropic pattern)

| Файл | Что |
|---|---|
| `contextualizer.py` | `PROMPT_TEMPLATE_V2`, `ContextualizedChunk`, `format_prefixed_chunk` |
| `providers/openrouter.py` | OpenRouter (OpenAI-compatible) gateway. По умолчанию `anthropic/claude-3.5-haiku` |

Концепт: [`11 — Contextual Retrieval`](concepts/11-contextual-retrieval.md). Industrial run: `scripts/contextualize_corpus.py` → `scripts/reindex_qdrant_v2.py`.

### `src/eval/` — оценка качества

| Файл | Что |
|---|---|
| `golden.py` | YAML loader для `docs/eval/golden_v0.0_synthetic.yaml` |
| `metrics.py` | `ref_hit_at_k`, `reciprocal_rank`, `mean_reciprocal_rank` |
| `runner.py` | Прогон golden через `hybrid_search`, агрегация |

Концепт: [`09 — Eval`](concepts/09-eval-and-golden-set.md). CLI: `scripts/eval_retrieval.py` (baseline), `scripts/eval_contextual_ab.py` (A/B v1 vs v2).

**B-001:** authoritative golden v0.1 от буддолога ещё не в репо. Текущие numbers на synthetic v0.0 — directional, не authoritative.

### `src/observability/` — Phoenix tracing

| Файл | Что |
|---|---|
| `tracing.py` | OpenTelemetry setup, OTLP экспорт в Phoenix (default `localhost:4317`), `FastAPIInstrumentor` |

Per-stage spans: `hybrid.encode`, `hybrid.channels`, `hybrid.rrf`, `hybrid.enrich`, `hybrid.rerank`. Концепт: [`08 — Phoenix`](concepts/08-observability-phoenix.md).

### `src/config.py` — settings

`pydantic_settings.BaseSettings` загружает `.env`. Группы:

- LLM provider: `openrouter_api_key`, `context_model`
- Retrieval defaults (после дня 18 cutover): `retrieval_collection="dharma_v2"`, `retrieval_rerank_default=False`, `retrieval_expand_parents_default=True`
- Vector DB: `qdrant_url`
- App DB: `database_url` (asyncpg)
- Phoenix: `phoenix_otlp_endpoint`
- App: `app_env`, `app_host`, `app_port`, `log_level`

`get_settings()` — cached singleton.

### `src/cli.py` + `src/logging_config.py`

CLI обёртка для `uvicorn`/`alembic`/ad-hoc операций. `logging_config.py` — structlog setup (JSON в production, human в development).

---

## Data flow: ingest → query

### Ingest path (offline)

```
SuttaCentral bilara-data (git clone)
   │
   ▼  src/ingest/suttacentral/parser.py
JSON segments + meta
   │
   ▼  src/ingest/suttacentral/loader.py
Postgres FRBR (Work → Expression → Instance)
   │
   ▼  src/processing/cleaner.py  (NFC, ASCII-fold)
chunk.text, chunk.text_ascii_fold
   │
   ▼  src/processing/chunker.py  (structural, parent+child)
Postgres `chunk` rows (parent_chunk_id self-ref)
   │
   ├──▶ migration 003 GENERATED tsvector → BM25 ready
   │
   ▼  src/contextual/  (day 16, Anthropic Haiku 3.5 via OpenRouter)
chunk.context_text populated
   │
   ▼  src/embeddings/  (BGE-M3 fp16, GPU, 4:40 min на 6,478 children)
Qdrant `dharma_v1` (raw text)        ← legacy, day 10
Qdrant `dharma_v2` (context-prefixed) ← production, day 16
```

Все CLI-обёртки в `scripts/`. Idempotent (re-run skip rows at current `prompt_version`).

### Query path (online, ~80 ms)

```
POST /api/query  {"query": "what is dukkha?", "top_k": 5}
   │
   ▼  src/api/query.py → RAGService.query()
hybrid_search(...)
   │
   ├─▶ Stage 1: encode (BGE-M3, 1024-d dense + sparse weights)
   ├─▶ Stage 2: 3 channels parallel
   │     ├─ dense:  Qdrant query_points using=bge_m3_dense
   │     ├─ sparse: Qdrant query_points using=bge_m3_sparse
   │     └─ bm25:   Postgres FTS @@ websearch_to_tsquery
   ├─▶ Stage 3: RRF fusion (k=60)
   ├─▶ Stage 4: enrich SQL JOIN
   │     SELECT chunk.text AS child_text, parent.text AS parent_text
   │       FROM chunk LEFT JOIN chunk parent ON parent.id = chunk.parent_chunk_id
   │     → HybridHit.text = parent_text (small-to-big), child_text = own
   └─▶ Stage 5: optional rerank (BGE-reranker-v2-m3, scores child_text)
   │
   ▼  RAGService:
   - score normalization → sigmoid(rerank) | rrf/top_rrf
   - forbidden_works post-filter
   - drop diagnostic fields → Source(work_canonical_id, text, snippet, score)
   │
   ▼  QueryResponse
{
  "query": "...", "sources": [...], "latency_ms": 78.3,
  "metadata": {"version": "dharma_v2-rerank0-parents1", ...}
}
```

Подробный per-stage trace с конкретными тайминами и Phoenix spans — в [`RAG_PIPELINE.md`](RAG_PIPELINE.md).

---

## Storage

| Хранилище | Что лежит | Где админ |
|---|---|---|
| **Postgres** | FRBR корпус (`work`, `expression`, `instance`, `chunk`), `chunk.fts_vector` (GIN, BM25 channel), `chunk.context_text` (день 16), миграции через Alembic | `database_url` env, default `dharma:dharma_dev@localhost:5432/dharma` |
| **Qdrant** | `dharma_v1` (raw text encoding, legacy day 10), `dharma_v2` (context-prefixed, production день 16+). Named vectors: `bge_m3_dense` (1024-d cosine) + `bge_m3_sparse` (learned). 6,478 child chunks в каждой | `qdrant_url` env, default `localhost:6333` |
| **Phoenix** | OpenTelemetry traces, per-stage hybrid spans, FastAPI request spans | `phoenix_otlp_endpoint` (`localhost:4317`), UI `phoenix_ui_url` (`localhost:6006`) |

Всё запускается через `docker-compose.yml` локально (см. [README](../README.md)).

---

## External dependencies

| Внешний сервис | Зачем | Failure mode |
|---|---|---|
| **OpenRouter** | Contextual Retrieval (Haiku 3.5 generates `chunk.context_text`). Будет также LLM-generation на день 22+ | Idempotent re-run (skip существующие rows). Без него query path **не блокируется** — `dharma_v2` уже в Qdrant |
| **SuttaCentral bilara-data** (GitHub) | Корпус. Один git clone | Локальная копия в `data/`. Без него ingest blocked, query — нет |
| **HuggingFace Hub** | BGE-M3 + BGE-reranker weights download | Кэш в `~/.cache/huggingface`. Offline после первого старта |
| **Phoenix OTLP** | Optional. Empty endpoint → tracing disabled | App работает без него. Dev/CI ставят `PHOENIX_OTLP_ENDPOINT=""` |

---

## Зависимости и boundary'и

```
api ─────┬───▶ rag (service+schemas)
         │       │
         │       ▼
         └───▶ retrieval (hybrid + rrf + dense/sparse/bm25 + reranker)
                 │
                 ├───▶ embeddings (BGE-M3 wrapper)
                 │
                 ├───▶ db (FRBR models, async session)
                 │
                 └───▶ observability (tracing)

ingest ──▶ db, processing
processing ──▶ db
contextual ──▶ db, providers/openrouter
eval ──▶ retrieval, db
```

Правила:
- `api/` ничего не знает про SQL — всё через `rag/` и `retrieval/`
- `rag/` ничего не знает про Qdrant — всё через `retrieval/hybrid_search`
- `retrieval/` принимает encoder + qdrant client + session как DI args (testable без реальных сервисов)
- `db/` — чистые модели, никакой бизнес-логики

---

## Testing

| Слой | Где | Сколько |
|---|---|---|
| Unit (hermetic, fakes) | `tests/unit/{api,rag,retrieval,embeddings,processing,contextual,eval,observability,ingest}/` | **285 тестов** на день 19, ~3 сек |
| Integration (live Postgres) | `tests/integration/` (BM25, FRBR queries) | ~10 тестов, нужен docker-compose up |
| Smoke (live full stack) | `scripts/smoke_*.py` | curl-style проверки на канонических запросах |

CI: pre-commit hooks (ruff, ruff-format, mypy strict, detect-secrets, mixed-line-ending). GitHub Actions сейчас off — re-introduction tracked как **B-004** перед v0.1.0 (см. [STATUS](STATUS.md)).

---

## Эволюция

День 19 закрывает Phase 1 retrieval. Что дальше:

- **День 21:** v0.1.0 release tag.
- **Phase 2 (дни 22+):** LLM-generation поверх `/api/query`. Citation verification (день 30+), prompt caching, fine-tuning evals.
- **App-track (app-day-01+):** Next.js UI, Telegram бот, audit log. Integration через `src/rag/schemas.py` (frozen на app-day-02).
- **Phase 3+:** Whisper-транскрипция dharmaseed talks (расширение корпуса), голосовой interface.

Авторитетный план: [`docs/RAG_DEVELOPMENT_PLAN.md`](RAG_DEVELOPMENT_PLAN.md), [`docs/APP_DEVELOPMENT_PLAN.md`](APP_DEVELOPMENT_PLAN.md).

---

## Где что искать

| Хочу понять… | Иди в… |
|---|---|
| Зачем именно так | [`docs/decisions/0001-phase1-architecture.md`](decisions/0001-phase1-architecture.md) |
| Конкретный концепт (FRBR, RRF, BGE-M3, …) | [`docs/concepts/INDEX.md`](concepts/INDEX.md) |
| Что произошло на запросе X | Phoenix UI на :6006, span tree в [`RAG_PIPELINE.md`](RAG_PIPELINE.md#phoenix-span-tree) |
| Что закрыто, что в работе | [`docs/STATUS.md`](STATUS.md) |
| Что было сделано в коммите | `git log` + [`CHANGELOG.md`](../CHANGELOG.md) |
| Метрики и numbers | [`docs/EVAL_BASELINE.md`](EVAL_BASELINE.md), [`docs/EVAL_CONTEXTUAL_AB.md`](EVAL_CONTEXTUAL_AB.md) |
