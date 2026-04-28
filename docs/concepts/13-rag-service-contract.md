# 13 — RAG-service contract: `POST /api/query`

## Что это

`POST /api/query` — **стабильный production endpoint** retrieval-стороны. То, что будут вызывать downstream-потребители: LLM-сервис генерации (день 22+), Telegram-бот, веб-фронтенд, app-track сервисы.

В отличие от `POST /api/retrieve`, контракт `/api/query` **не меняется по тюнинговым причинам**:
- клиент не передаёт `rerank`, `expand_parents`, `per_channel_limit` — это server-side defaults
- результат не содержит `rrf_score`, `per_channel_rank`, `rerank_score`, `parent_chunk_id`, `chunk_id` — это диагностика
- `score` — нормализованный 0-1, без привязки к конкретному скорингу

## Зачем у нас

К дню 19 у нас уже есть `/api/retrieve` со 100% диагностической поверхностью — нужно для eval (день 14, 17), smoke-скриптов, A/B. Но **prod-консьюмеры не должны коуплиться к этому**.

Аналогия: в обычном REST-API между «admin endpoint» и «public endpoint» всегда есть стена. Public endpoint:
- возвращает только то, что нужно бизнес-логике
- стабилен (changelog с deprecation period)
- не утекает имплементацию (RRF score → реализация конкретного fusion-алгоритма)

День 19 ставит эту стену: `/api/retrieve` останется внутренним инструментом для тюнинга, `/api/query` — официальный production-вход.

## Контракт

### Request — `QueryRequest`

```json
{
  "query": "what is dukkha?",
  "top_k": 5,
  "language": null,
  "forbidden_works": ["mn10"]
}
```

| Поле | Тип | Default | Описание |
|---|---|---|---|
| `query` | str | required | 1-2000 символов |
| `top_k` | int | 5 | 1-20 (жестче, чем у `/api/retrieve` — sized для LLM-context) |
| `language` | str \| null | null | reserved (corpus сейчас EN-only после rag-day-04) |
| `forbidden_works` | list[str] \| null | null | post-RRF фильтр по `work_canonical_id` |

### Response — `QueryResponse`

```json
{
  "query": "what is dukkha?",
  "sources": [
    {
      "work_canonical_id": "mn10",
      "segment_id": "mn10:8.4",
      "text": "[parent passage ~1500 tokens]",
      "snippet": "[matched child fragment ~384 tokens]",
      "score": 0.87
    }
  ],
  "latency_ms": 78.3,
  "metadata": {
    "version": "dharma_v2-rerank0-parents1",
    "collection": "dharma_v2",
    "rerank": false,
    "expand_parents": true,
    "n_candidates": 8
  }
}
```

**Source**: только то, что нужно LLM и UI:
- `text` — passage для LLM (parent при `expand_parents=True`)
- `snippet` — child fragment для UI-highlight
- `score` — нормализованный 0-1 (sigmoid от reranker'а или RRF/top-RRF)
- `work_canonical_id` + `segment_id` — для citation и deep-link

**PipelineMetadata**: диагностика «что произвело ответ»:
- `version` — компактная строка `{collection}-rerank{0|1}-parents{0|1}`
- `collection`, `rerank`, `expand_parents` — те же значения, развёрнутые
- `n_candidates` — RRF pool size **до** `forbidden_works` фильтра, чтобы клиент мог логировать "запрос отдал 0 результатов потому что пул был пуст" vs "потому что всё отфильтровали"

## Архитектурные решения

### Score normalization

Внутри retrieval-движка два разных скоринга:
- **rerank_score** — raw cross-encoder logits, диапазон ~[-15, +15] (BGE-reranker-v2-m3)
- **rrf_score** — `sum(1/(k+rank))` по каналам, диапазон зависит от запроса

Обе шкалы непригодны как public score. Решение:
- если `rerank_score` есть → `sigmoid(score)` в [0, 1] (стандартный mapping для cross-encoders)
- иначе → `rrf_score / max(rrf_score)` среди hits в этом ответе

`Source.score` — **within-response** measure, не probability. Сравнивать между разными запросами **нельзя**. Это явно прописано в OpenAPI description.

### Server-side defaults

`QueryRequest` **не принимает** `rerank` или `expand_parents`. Эти параметры читаются из `Settings`:
- `retrieval_collection` (default `dharma_v2`)
- `retrieval_rerank_default` (default `False` после дня 17)
- `retrieval_expand_parents_default` (default `True` после дня 18)

Что это даёт:
- prod-cutover после A/B (день 17) — без version-bump'а API
- per-environment override через env vars (dev может поставить `RETRIEVAL_RERANK_DEFAULT=true`)
- клиент не должен «помнить», что у нас сейчас работает лучше всего

`/api/retrieve` остаётся способом форсить параметры для eval — там `rerank: bool | None` живёт.

### `forbidden_works` post-filter

Фильтр по `work_canonical_id` применяется **после** RRF, не внутри Qdrant query. Почему:
- список форбидденов специфичен для каждого запроса (per-tenant policy)
- pre-filter в Qdrant ломает scoring (channel limits становятся неточными)
- post-filter дешёв (top-30 hits, set-membership)

Минус: при длинном `forbidden_works` ответ может вернуть `<top_k` sources. Описано в docstring `top_k`.

### Resource sharing

`POST /api/query` использует **тот же** singleton `RetrievalResources`, что и `/api/retrieve`. BGE-M3 (2.3GB) и BGE-reranker (1.1GB) грузятся один раз, делятся через `src.api.retrieve.get_resources()`.

Lifespan ordering в `app.py`:
1. `install_retrieve_router(app)` — создаёт singleton
2. `install_query_router(app)` — переиспользует
3. shutdown в обратном порядке: `shutdown_query_service()` → `shutdown_retrieve_resources()`

Если query install запустится первым — `RuntimeError("Retrieval resources not initialised")`.

## Что НЕ делает день 19

- **Не делает дедупликацию** parent'ов в `sources`. Несколько children одного parent → дубли в response. Закроем на дне 20+ (если UX-проблема).
- **Не использует `language`** — поле принимается, но игнорируется. Reserved.
- **Не возвращает full provenance** — `chunk_id`, `parent_chunk_id` скрыты. Если в будущем UI понадобится «open exact chunk», добавим `Source.chunk_id` (forward-compatible add).
- **Не делает caching** — semantic cache (плановый rag-day-50+) ляжет уровнем выше, прозрачно.
- **Не вызывает LLM** — это retrieval-only endpoint. Generation (citation-aware) — отдельный endpoint день 22+.

## Альтернативы

| Альтернатива | Почему не |
|---|---|
| **Один endpoint `/api/retrieve`** для всего | Невозможно эволюционировать diagnostic surface без breaking change для prod-консьюмеров |
| **GraphQL вместо REST** | Лишняя сложность для 1 операции; FastAPI/OpenAPI достаточно для контракта |
| **Streaming response** | Retrieval быстрый (~80ms), не помогло бы; полезно будет когда добавится LLM-generation |
| **Принимать `rerank` в request** | Тогда клиент должен знать про reranker'а — leaks impl. Server-side default решает это |
| **Возвращать raw RRF + rerank scores** | Public клиент не должен делать ranking-decisions сам — у нас есть нормализованный score |

## Где в коде

- [src/rag/schemas.py](../../src/rag/schemas.py) — `QueryRequest`, `Source`, `QueryResponse`, `PipelineMetadata`
- [src/rag/service.py](../../src/rag/service.py) — `RAGService` class, `_normalise_score`, `_build_version_string`, `_hit_to_source`
- [src/api/query.py](../../src/api/query.py) — FastAPI router, `install_router`, `shutdown_service`
- [src/api/app.py](../../src/api/app.py) — wiring `install_query_router` после `install_retrieve_router`
- [src/api/retrieve.py](../../src/api/retrieve.py) — `get_resources()` accessor для shared singleton
- [tests/unit/rag/test_schemas.py](../../tests/unit/rag/test_schemas.py) — schema validation
- [tests/unit/rag/test_service.py](../../tests/unit/rag/test_service.py) — RAGService + helpers (stubs `hybrid_search`)

## Production state после дня 19

- `POST /api/retrieve` — внутренний инструмент для eval, A/B, тюнинга (полная диагностика)
- `POST /api/query` — public production endpoint (стабильный контракт)
- BGE-M3 + reranker + Qdrant + DB — один пул, два router'а
- Defaults: `dharma_v2` collection, rerank=False, expand_parents=True (per server settings)
- Latency: ~80ms/запрос (без рерэнкера, parent expansion включён)

App-track теперь имеет authoritative integration point. На app-day-02 будет зафиксирован `src/rag/schemas.py` — RAGService class реализует протокол именно с этими schemas, никаких stub'ов больше не нужно.
