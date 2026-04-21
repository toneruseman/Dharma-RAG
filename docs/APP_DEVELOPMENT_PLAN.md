# App Development Plan

> План разработки **пользовательских приложений** Dharma-RAG: backend API,
> web frontend, mobile (PWA → Capacitor), deploy, CI/CD, observability.
>
> **Разработка RAG-ядра** (embeddings, Qdrant, chunking, reranking,
> LLM-pipeline, eval) ведётся в отдельном треке и описана в
> [`RAG_DEVELOPMENT_PLAN.md`](RAG_DEVELOPMENT_PLAN.md). Этот документ
> потребляет RAG-сервис через API-контракт, но не описывает его
> внутренности.

- **Версия плана:** 2026-04-21
- **Связанные документы:**
  - Архитектурные решения: [`docs/decisions/0001-phase1-architecture.md`](decisions/0001-phase1-architecture.md)
  - Полный контекст проекта: [`docs/Dharma-RAG.md`](Dharma-RAG.md)
  - План RAG-ядра: [`docs/RAG_DEVELOPMENT_PLAN.md`](RAG_DEVELOPMENT_PLAN.md)

---

## Оглавление

- [Что уже есть в репо](#что-уже-есть-в-репо)
- [Scope этого плана](#scope-этого-плана)
- [Архитектура app-слоя](#архитектура-app-слоя)
- [API-контракт с RAG-ядром](#api-контракт-с-rag-ядром)
- [Фазы на карте](#фазы-на-карте)
- [Phase 0: Bootstrap app-слоя (дни 1-5)](#phase-0-bootstrap-app-слоя-дни-1-5)
- [Phase 1: Backend MVP (дни 6-20)](#phase-1-backend-mvp-дни-6-20)
- [Phase 2: Reading Room (дни 21-30)](#phase-2-reading-room-дни-21-30)
- [Phase 3: Search UI (дни 31-37)](#phase-3-search-ui-дни-31-37)
- [Phase 4: Chat Q&A (дни 38-45)](#phase-4-chat-qa-дни-38-45)
- [Phase 5: Guardrails и Privacy (дни 46-52)](#phase-5-guardrails-и-privacy-дни-46-52)
- [Phase 6: Deploy и Launch v0.1.0 (дни 53-60)](#phase-6-deploy-и-launch-v010-дни-53-60)
- [Phase 7+: Mobile, Voice, Scale](#phase-7-mobile-voice-scale)
- [Параллельные треки](#параллельные-треки)
- [Критический путь и зависимости](#критический-путь-и-зависимости)
- [Операционные заметки](#операционные-заметки)

---

## Что уже есть в репо

По состоянию на **2026-04-21**, ветка `dev`:

- **Python 3.12** проект, flat `src/` layout
- `pyproject.toml` с hatchling + pinned зависимостями (FastAPI, Claude,
  BGE-M3, Qdrant, Langfuse и т. д.)
- **Day 1 done:** FastAPI `/health` endpoint, `src/api/app.py`
- `src/config.py` — Pydantic Settings из `.env`
- `src/logging_config.py` — structlog
- `src/cli.py` — entry point `dharma-rag`
- `docker-compose.yml` — Qdrant 1.12.4 + Langfuse (v2 + Postgres)
- Pre-commit hooks (ruff + mypy + detect-secrets)
- Tests: `tests/unit/test_api_health.py` + `test_config.py` + `test_logging.py`
- ADR-0001 (2026-04-21) — зафиксированы окончательные параметры Phase 1

**Что ADR важно для app-слоя:**

- Python 3.12+, flat `src/`, импорты `from src.config import …`
- BYOK паттерн для Claude (пользователь приносит свой ключ)
- Observability: миграция Langfuse → Phoenix на Day 9 Phase 1 RAG
- FP16 quantization в Qdrant, named vectors

---

## Scope этого плана

### Входит в scope (делаем здесь)

| Слой | Что | Где живёт |
|---|---|---|
| **Backend API gateway** | FastAPI routers: `/search`, `/query/stream`, `/sources/*`, `/keys`, `/privacy/*`, `/audit` | `src/api/routers/` |
| **Guardrails layer** | Crisis-classifier, wellbeing-classifier, disclaimer-injection | `src/api/guardrails/` |
| **BYOK proxy** | Валидация ключа, forward в LLM, no-store | `src/api/byok/` |
| **Rate limiting** | Per-IP и per-user, Redis-бэкенд | `src/api/middleware/` |
| **Audit log + consent ledger API** | Read-only публичные эндпойнты | `src/api/public/` |
| **Web frontend** | Next.js 14, Reading Room + Search + Chat | `web/` (новый) |
| **Mobile** | PWA поверх `web/` → Capacitor-обёртка в Phase 7+ | `web/` + `mobile/` |
| **Deploy** | Hetzner CX22, Caddy, GitHub Actions, backups | `deploy/`, `.github/` |
| **App-observability** | OpenTelemetry → Phoenix, структурные логи | `src/api/telemetry/` |

### Не входит в scope (делает RAG-чат)

- Индексация корпуса, embedding, chunking, Contextual Retrieval
- Qdrant коллекции, HNSW-параметры, named vectors
- Hybrid retrieval, RRF, reranker, MMR, parent-expansion
- LLM-роутер, prompt engineering, Citations API глубоко
- Golden set, Krippendorff α, eval-pipeline
- Pali glossary, G2P, STT/TTS

### Граница

`src/rag/` (RAG-чат) экспортирует **один async класс** — `RAGService`.
Мы его не знаем внутри, мы его **вызываем из** `src/api/routers/`. Если
он ещё не готов, используем заглушку (`src/api/_rag_stub.py`) — это даёт
возможность строить app-слой параллельно, не блокируясь.

---

## Архитектура app-слоя

```
┌──────────────────────────────────────────────────────────────┐
│  web/ (Next.js 14 + App Router + TypeScript + Tailwind)     │
│  ├─ app/read/[source_id]   Reading Room (главный surface)   │
│  ├─ app/search              Search + filters                 │
│  ├─ app/chat                Q&A (SSE streaming)              │
│  ├─ app/settings/keys       BYOK UI                          │
│  ├─ app/privacy/*           Export/delete                    │
│  ├─ app/audit               Public refused-queries log       │
│  └─ app/sources             Consent ledger viewer            │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTPS / SSE
┌──────────────────────────▼───────────────────────────────────┐
│  src/api/ (FastAPI — уже частично есть)                      │
│  ├─ app.py                  create_app() + /health           │
│  ├─ routers/                                                 │
│  │   ├─ search.py           POST /api/search                 │
│  │   ├─ explain.py          POST /api/explain                │
│  │   ├─ chat.py             POST /api/query/stream (SSE)     │
│  │   ├─ sources.py          GET /api/sources/{uid}           │
│  │   ├─ keys.py             POST /api/keys/validate          │
│  │   ├─ privacy.py          GET /api/privacy/export …        │
│  │   └─ public.py           GET /api/audit, /api/consent     │
│  ├─ guardrails/             crisis-classifier, disclaimers   │
│  ├─ byok/                   key validation + forwarding      │
│  ├─ middleware/             rate-limit, trace-id, logging    │
│  ├─ telemetry/              OpenTelemetry + Phoenix          │
│  └─ _rag_stub.py            fake RAGService для ранних дней  │
└───────────────┬────────────────────────────┬─────────────────┘
                │                            │
                ▼                            ▼
┌─────────────────────────┐      ┌─────────────────────────────┐
│  src/rag/ (RAG-чат)      │      │  Postgres (общий с RAG)     │
│  RAGService              │      │  + app-таблицы:             │
│  ├─ search()             │      │    audit_log               │
│  ├─ explain()            │      │    refused_queries         │
│  ├─ query_stream()       │      │    rate_limit_counters     │
│  └─ get_source()         │      │    (users в Phase 1 Beta)   │
└─────────────────────────┘      └─────────────────────────────┘
```

### Ключевые решения

1. **Один репо, два приложения.** `src/` (Python) и `web/` (Node/TS)
   живут рядом. `docker-compose.yml` поднимает оба.
2. **Backend остаётся на FastAPI,** как уже выбрано в репо. Next.js — на
   frontend, не BFF. Никакого tRPC — backend говорит на обычном HTTP+SSE,
   чтобы mobile и третьи приложения могли интегрироваться.
3. **BYOK — жёсткий инвариант.** Ключ никогда не персистится: только
   httpOnly cookie на фронте + `X-User-LLM-Key` header в internal вызов
   в RAG-слой. Логирование маскируется middleware-ом.
4. **Guardrails перед RAG.** Crisis-классификатор отрабатывает **до**
   дорогого retrieval. Kill-switch возвращает hardcoded response.
5. **OpenAPI — single source of truth.** FastAPI генерирует спеку, фронт
   через `openapi-typescript` получает типы — контракт не расползается.

---

## API-контракт с RAG-ядром

Это **разделительная линия** между двумя чатами. Всё внутри `src/rag/`
делает RAG-чат; всё, что вызывает `src/rag/`, делаем мы.

### Интерфейс `RAGService` (Python ABC)

Файл: `src/rag/service.py` (создаёт RAG-чат к Day 14 Phase 1).

```python
class RAGService(Protocol):
    async def search(self, req: SearchRequest) -> SearchResponse: ...
    async def explain(self, req: ExplainRequest) -> ExplainResponse: ...
    async def query_stream(
        self, req: QueryRequest, llm_key: str | None
    ) -> AsyncIterator[SSEEvent]: ...
    async def get_source(self, uid: str, lang: str | None) -> SourceDocument: ...
    async def health(self) -> dict[str, str]: ...
```

### Schemas (Pydantic, в `src/rag/schemas.py`)

| Модель | Поля ключевые |
|---|---|
| `SearchRequest` | `query: str`, `lang: str \| None`, `filters: FilterSet`, `top_k: int = 20` |
| `SearchHit` | `chunk_id`, `source_uid`, `score`, `score_breakdown: {dense, sparse, bm25, rerank}`, `text_preview`, `metadata: SourceMetadata` |
| `SearchResponse` | `hits: list[SearchHit]`, `latency_ms: int`, `sources_considered: int` |
| `ExplainRequest` | `query: str`, `chunk_ids: list[str]`, `lang: str \| None` |
| `ExplainResponse` | `answer: str`, `citations: list[Citation]`, `used_chunks: list[str]`, `unused_chunks: list[str]`, `confidence: Literal["direct","synthesized","interpretive"]` |
| `Citation` | `source_uid`, `start_char`, `end_char`, `cited_text`, `chunk_id` |
| `SSEEvent` | `event: "retrieval_done" \| "token" \| "citation" \| "done" \| "error"`, `data: Any` |
| `SourceDocument` | `uid`, `title`, `tradition`, `language`, `translator`, `license`, `body: list[Paragraph]`, `chunks: list[ChunkRef]` |

### SSE event sequence (стриминг `/api/query/stream`)

```
1. event: retrieval_done     data: {hits: [...], latency_ms: 120}
2. event: token              data: {text: "Sati"}
3. event: token              data: {text: " is"}
...
4. event: citation           data: {chunk_id, start_char, end_char, cited_text}
...
5. event: done               data: {total_tokens, cost_usd, trace_id}
```

### Error contract

`RAGServiceError` с кодами: `rag.unavailable`, `rag.timeout`,
`rag.insufficient_context`, `rag.safety_refusal`, `rag.invalid_key`.
App-слой маппит их в HTTP 503/504/422/451/401.

### Документирование

Контракт живёт в `src/rag/schemas.py`. Версионируется через поле
`api_version: Literal["1.0"]` в корне каждого response. Breaking changes
= мажорная версия + deprecated endpoint полгода.

---

## Фазы на карте

| Phase | Дни | Цель | Milestone |
|---|---|---|---|
| **0. Bootstrap** | 1-5 | Monorepo готов, mock-RAG работает, контракт зафиксирован | `web/` поднимается локально |
| **1. Backend MVP** | 6-20 | FastAPI routers, BYOK, rate-limit, guardrails каркас | `POST /api/search` на mock-RAG |
| **2. Reading Room** | 21-30 | Главный surface проекта | `/read/mn10` работает |
| **3. Search UI** | 31-37 | Search-first UX | `/search` с фильтрами и reader-pane |
| **4. Chat Q&A** | 38-45 | Streaming ответы с citations | `/chat` с кликабельными `[n]` |
| **5. Guardrails+Privacy** | 46-52 | Crisis, disclaimers, GDPR | kill-switch работает |
| **6. Deploy** | 53-60 | Production на Hetzner CX22 | v0.1.0 публично |
| **7. Beta** | Mo 3-6 | Mobile PWA→Capacitor, i18n, accounts | v0.5.0 |
| **8. Voice** | Mo 6-9 | STT→RAG→TTS pipeline | v0.8.0 |
| **9. Scale** | Mo 9-12 | Local LLM, full corpus, community | v1.0.0 |

Phase 0-6 описаны day-by-day ниже. Phase 7+ — общим обзором.

---

## Phase 0: Bootstrap app-слоя (дни 1-5)

> **Важно про нумерацию:** «Day N» в этом плане считается от **начала
> app-трека**, а не от начала всего проекта. В репо уже есть «Day 1»
> от RAG-трека (FastAPI `/health`). Во избежание путаницы в commit
> messages пишем `app-day-01`, `rag-day-08` и т. д.

### app-day-01 — Monorepo skeleton

**Цель:** две части проекта (`src/` уже есть, `web/` добавляем) живут в
одном репо под одним CI.

**Шаги:**

1. `pnpm init` в корне, `pnpm-workspace.yaml` с `web/` и опциональным
   `packages/*`.
2. `web/` создать через `pnpm create next-app@latest web --ts --app
   --tailwind --eslint --no-src-dir --import-alias '@/*'`.
3. Shadcn/ui init в `web/` (`pnpm dlx shadcn@latest init`).
4. Добавить в `.gitignore`: `web/node_modules/`, `web/.next/`,
   `web/out/`, `.pnpm-store/`.
5. В корне `package.json` с scripts: `dev:web`, `dev:api`, `dev` (конкурентно
   оба через `concurrently`).
6. Обновить `README.md` раздел «Структура» — добавить `web/`.

**Результат:** `pnpm dev:web` открывает Next.js на `:3001`, `pnpm dev:api`
поднимает FastAPI на `:8000`.

**Тесты:** вручную curl `:3001`, `:8000/health`.

### app-day-02 — RAG mock и контракт-заглушки

**Цель:** не блокироваться RAG-чатом. Строим весь app на фиктивных
данных, которые соответствуют контракту.

**Шаги:**

1. Создать `src/rag/__init__.py`, `src/rag/schemas.py` с Pydantic
   моделями из раздела «API-контракт» выше.
2. `src/api/_rag_stub.py` — `StubRAGService`, реализующий Protocol.
   Возвращает фиктивные `SearchHit`-ы из 3 захардкоженных MN-сутт.
3. `src/rag/service.py` — пустой `Protocol` + `get_rag_service()`
   factory, которая на `APP_ENV=development` возвращает Stub, иначе
   реальный (ещё не существующий).
4. Тесты: `tests/unit/test_rag_stub.py` — проверяет что schemas
   валидны и stub возвращает соответствующие им объекты.
5. Добавить в `.env.example`: `RAG_BACKEND=stub|real`.

**Результат:** app-слой может развиваться независимо от готовности
RAG-ядра. Переключение на реальный RAG — изменение одной env-переменной.

### app-day-03 — OpenAPI и типы для фронта

**Цель:** контракт не расползается между FastAPI и Next.js.

**Шаги:**

1. Запустить `python -m src.cli serve` локально, достать
   `/openapi.json`, сохранить в `web/scripts/openapi.json`.
2. Установить в `web/`: `pnpm add -D openapi-typescript`.
3. Скрипт `web/scripts/gen-api-types.ts`: генерирует
   `web/lib/api-types.ts`.
4. В `pnpm dev:web` prehook: `pnpm gen:api-types` (чтобы типы
   пересоздавались при старте).
5. Создать в `web/lib/api-client.ts` тонкую обёртку над fetch с типами.
6. Добавить pnpm-скрипт `test:contract` — запускает mypy на backend +
   tsc в web, проверяя что типы согласованы.

**Результат:** изменение Pydantic-схемы в backend ломает tsc в web — это
good failure.

### app-day-04 — Структура Next.js и базовый layout

**Цель:** правильный App Router layout с темами, i18n-заделом и
дизайн-токенами.

**Шаги:**

1. `web/app/layout.tsx` — root layout с theme provider (next-themes),
   Inter + Noto Sans Display для диакритики.
2. `web/app/globals.css` — дизайн-токены (bg, fg, muted, accent),
   typography scale, подборка `prose` для дхарма-текстов.
3. Shadcn/ui компоненты: Button, Card, Dialog, Tooltip, Sheet,
   ScrollArea, Tabs.
4. `web/components/layout/{Header,Footer,SideNav}.tsx` — скелетон.
   В футере — disclaimer placeholder.
5. `web/app/page.tsx` — landing со ссылками на `/search`, `/read`, `/chat`.
6. i18n-задел: `next-intl` установлен, но по умолчанию только `en`. RU
   добавим в Phase 7.

**Результат:** `/` открывается с правильной типографикой, тёмная
тема переключается, выглядит прилично.

### app-day-05 — Dev-friendly Docker Compose

**Цель:** `docker compose up` поднимает весь стек, включая frontend.

**Шаги:**

1. Обновить корневой `docker-compose.yml`: раскомментировать `app`
   (backend), добавить `web` сервис (Node 22-alpine, `pnpm dev`).
2. Создать минимальные Dockerfile для backend (`deploy/api.Dockerfile`)
   и web (`deploy/web.Dockerfile`) — multi-stage, но пока только dev
   target.
3. `docker-compose.override.yml` для dev с volumes-mounts, чтобы hot-reload
   работал и на фронте, и на бэке.
4. Добавить в README раздел «Local dev» с одной командой: `docker
   compose up`.

**Результат:** новый контрибьютор за 5 минут поднимает весь проект.

**Gate после Phase 0:**

- `docker compose up` поднимает Qdrant + Langfuse + Postgres + backend +
  web без ошибок
- Frontend стучится в backend, backend в stub-RAG, всё возвращает
  осмысленные заглушки
- Контракт `src/rag/schemas.py` зафиксирован, OpenAPI генерит типы
- Документация обновлена

---

## Phase 1: Backend MVP (дни 6-20)

Основная задача — довести `src/api/` до состояния, когда на нём можно
строить UI. Внутри пишем реальные роутеры, middleware, BYOK, guardrails
заглушки. RAG всё ещё через stub.

### app-day-06 — Postgres schema для app-таблиц

1. Определиться: отдельная БД или общая с RAG. **Решение:** общая
   (тот же `dharma-rag` Postgres), но app-таблицы в schema `app`, RAG
   в `public`.
2. Alembic migration `app/001_initial.py`:
   - `app.audit_log` — `trace_id, ts, endpoint, query_hash, status, duration_ms, user_hash, byok_used bool`
   - `app.refused_queries` — `ts, reason, category, query_anonymized, trace_id`
   - `app.rate_limit_counters` — `key, window_start, count` (или через Redis)
   - `app.feedback` — `trace_id, thumb int, comment, ts`
3. SQLAlchemy 2.x модели в `src/api/db/models.py`.
4. Тесты: `pytest tests/integration/test_db_migrations.py` с
   `pytest-postgres` fixture.

### app-day-07 — Middleware стек

1. `src/api/middleware/trace.py` — генерирует `X-Trace-Id`, кладёт в
   structlog contextvar.
2. `src/api/middleware/logging.py` — access log с duration, маскировка
   `authorization`, `x-user-llm-key`.
3. `src/api/middleware/rate_limit.py` — slowapi + Redis backend.
   Анонимный: 20 req/мин на IP; `/api/query/stream`: 5 req/мин.
4. `src/api/middleware/cors.py` — строгий origin whitelist в prod,
   `*` в dev.
5. Тесты на каждое middleware.

### app-day-08 — Эндпойнт `POST /api/search`

1. Router `src/api/routers/search.py`.
2. Request validation через Pydantic (из `src/rag/schemas.py`).
3. Вызов `rag.search(request)` — на stub.
4. Маппинг ошибок `RAGServiceError` → HTTP.
5. Запись в `audit_log`.
6. OpenAPI описание с примерами.
7. `tests/integration/test_api_search.py`.

### app-day-09 — Эндпойнт `POST /api/explain`

Аналогично, но вызывает `rag.explain`. Обрабатывает специальный случай
«insufficient context» → 422 с явным сообщением «The sources don't
contain enough information».

### app-day-10 — Эндпойнт `POST /api/query/stream` (SSE)

1. `sse-starlette` для streaming.
2. `async for event in rag.query_stream(req, llm_key)` →
   `EventSourceResponse`.
3. Keepalive каждые 15 сек.
4. Обработка disconnect клиента через `await request.is_disconnected()`.
5. Тест через `httpx.AsyncClient` с stream=True.

### app-day-11 — Эндпойнт `GET /api/sources/{uid}`

Reading Room data source. Возвращает полный документ (title, body,
metadata, adjacent chunks).

### app-day-12 — BYOK валидация

1. `src/api/byok/validator.py` — `async def validate_key(provider:
   Literal["anthropic","openai","deepseek"], key: str) -> KeyInfo`.
2. Делает `/v1/models` call (или эквивалент) через `httpx`.
3. Возвращает `{provider, model_list, rate_limits_known, valid: bool}`.
4. Router `POST /api/keys/validate` — принимает ключ, возвращает
   валидность. **Ключ не логируется и не сохраняется.**
5. Unit-тесты с httpx mock.
6. Security-тест: ассертим что `structlog` сообщение не содержит ключа.

### app-day-13 — BYOK cookie sessions

1. Frontend→backend: ключ передаётся через `httpOnly, Secure,
   SameSite=Strict` cookie `dharma_llm_key_v1`.
2. Шифрование на стороне backend: AES-GCM с ключом из `env.KEY_ENCRYPTION_KEY`.
3. Read: middleware декодирует в contextvar, доступен через
   `get_user_llm_key()` dependency.
4. TTL: 24 часа (пользователь переустанавливает ключ, если cookie
   истёк).
5. Endpoint `DELETE /api/keys` — удаляет cookie.
6. Явная documentation что мы **не храним** ключ в БД.

### app-day-14 — Передача BYOK ключа в RAG-слой

1. `src/api/byok/forwarder.py` — экстрагирует ключ из cookie, кладёт в
   `rag.query_stream(…, llm_key=key)`.
2. RAG-слой получает ключ через аргумент и использует его для LLM-вызова.
3. При ошибках `rag.invalid_key` — отвечаем 401 + сообщение «your key
   expired or is invalid, please reenter».
4. Integration-тест с fake LLM backend.

### app-day-15 — Crisis classifier

1. `src/api/guardrails/crisis.py` — async функция `is_crisis(text:
   str) -> tuple[bool, str | None]`.
2. Stage 1: regex на hardcoded triggers («kill myself», «убить себя»,
   «покончить с жизнью» + аналоги на EN).
3. Stage 2: опционально, дешёвый LLM-call (Haiku) через BYOK-ключ, если
   regex неуверенный. В dev-режиме выключен (дорого и не нужно для
   отладки).
4. Возвращает причину: `"suicide"`, `"self-harm"`, `"medical-crisis"`.

### app-day-16 — Crisis kill-switch интеграция

1. Middleware `crisis_check` на `/api/query/stream` и `/api/explain`.
2. Если `is_crisis == True`: не вызываем RAG, возвращаем hardcoded
   response с hotlines (RU, EN, UK, NL как минимум).
3. Запись в `refused_queries` с категорией `crisis`.
4. Пример response — в документации как `docs/guardrails/crisis-response.md`.

### app-day-17 — Meditation side-effects guardrail

Аналогично, но триггеры: «dark night», «dukkha ñāṇa», «panic during
meditation», «depersonalization from vipassana» и т. д. Response
перенаправляет на Cheetah House + Britton Lab + «Ask a human teacher».

### app-day-18 — Vajrayana restricted flag

1. `src/api/guardrails/restricted.py` — фильтр результатов retrieval.
2. Если `source.restricted == True` и нет opt-in cookie — исключаем из
   ответов, добавляем placeholder «This material requires initiation».
3. Координация с RAG-чатом: они обязаны проставлять `restricted` в
   metadata chunk-а. В контракте добавлено поле `SearchHit.metadata.restricted: bool`.

### app-day-19 — Audit log + public audit endpoint

1. Ежемесячная cron job (`cron.jobs.monthly_audit`) агрегирует
   `refused_queries` за месяц.
2. Анонимизирует: query → SHA-256(query + monthly_salt), хранит только
   категорию и hash.
3. `GET /api/audit/{year}/{month}` — публичный, возвращает агрегат.
4. Frontend `/audit` (создадим в Phase 5) читает отсюда.

### app-day-20 — GDPR endpoints

1. `GET /api/privacy/export?ip_hash=…` — возвращает JSON со всеми
   связанными записями.
2. `DELETE /api/privacy/delete` — удаляет (или 30-дневное soft-delete).
3. Rate-limit: 1 раз в день на IP.
4. Документация: `docs/PRIVACY.md` обновить с описанием эндпойнтов.

**Gate после Phase 1:**

- Все 9 эндпойнтов работают на stub-RAG
- Middleware стек полный (trace, log, rate-limit, CORS)
- BYOK работает end-to-end через cookie
- Crisis + wellbeing guardrails отрабатывают
- Audit log пишется, endpoint читается
- CI зелёный (pytest + mypy + ruff)

---

## Phase 2: Reading Room (дни 21-30)

Главный surface проекта по философии «тексты — это святое».

### app-day-21 — Страница `/read/[source_id]`

1. `web/app/read/[source_id]/page.tsx` — server component.
2. Fetch через `apiClient.getSource(params.source_id)`.
3. Рендер: `<Header><Outline/><Body/><AdjacentSidebar/></Header>`.
4. Body рендерит `paragraphs: Paragraph[]` — параграфы, стихи,
   sub-headers.
5. **Типографика:** моноширинные номера стихов слева, justify main text.
6. Loading + error states.

### app-day-22 — Outline и навигация

1. Левая sidebar с деревом `chapters → sections → verses`.
2. Sticky header с текущим местом в документе.
3. Клавиатурные шорткаты: `j/k` — след/пред параграф, `gg/G` — в
   начало/конец, `/` — поиск в документе.
4. URL синхронизирован с якорем: `/read/mn10#12.3`.

### app-day-23 — Hover-glossary

1. `web/components/glossary/PaliTooltip.tsx`.
2. Статическая YAML-таблица на 200 терминов в `packages/glossary/pali.yaml`.
3. При построении страницы — сервер парсит текст, оборачивает каждый
   известный термин в `<PaliTooltip term="satipaṭṭhāna">`.
4. Tooltip показывает: этимология, переводы, ссылки на PTS Dictionary.

### app-day-24 — Bookmarks (localStorage)

1. `web/lib/bookmarks.ts` — класс для localStorage API.
2. Кнопка «bookmark» на каждом параграфе — кладёт `{source_uid,
   paragraph_id, timestamp, note}`.
3. Страница `/bookmarks` — список всех закладок с фильтрами.
4. Экспорт в JSON (кнопка «Download bookmarks»).

### app-day-25 — Highlight

1. Кнопка «highlight» — сохраняет выделение через Range API.
2. Три цвета: жёлтый (важно), синий (разобрать), зелёный (сделано).
3. Хранение в localStorage рядом с bookmarks.

### app-day-26 — Adjacent-chunks explorer

Блок внизу документа: «соседние пассажи» через
`/api/sources/{uid}/adjacent` (добавить эндпойнт если ещё нет) —
показывает 3 chunk до и 3 после текущего.

### app-day-27 — Parallel translations split-view

1. Если для `work_uid` есть несколько `expression_uid` (переводы) —
   показать toggle «split view».
2. Два колонки с синхронной прокруткой по `segment_id`.
3. Координация с RAG-чатом: API `/api/sources/{uid}/parallels` должен
   возвращать список доступных переводов.

### app-day-28 — Print-friendly view

1. `@media print` CSS: скрыть sidebar, навигацию, увеличить шрифт.
2. Page breaks на границах глав.
3. Футер с цитированием: автор, переводчик, источник, дата доступа.

### app-day-29 — Shareable links

1. URL canonical: `/read/mn10?v=sujato-2018#12.3-5` (source + translation
   version + verse range).
2. Open Graph metadata для preview в соцсетях.
3. Кнопка «copy citation» — в буфер обмена готовое академическое
   цитирование («MN 10 §12.3-5, trans. Sujato (2018), retrieved from
   Dharma-RAG 2026-05-15»).

### app-day-30 — Reading Room performance pass

1. Lighthouse audit: цель LCP < 1.5s.
2. Image optimization (если будут миниатюры).
3. Route prefetching для outline-ссылок.
4. Server-side cache заголовков `Cache-Control: public, max-age=3600`
   для документов (их содержимое меняется редко).

**Gate после Phase 2:**

- Любую открыто-лицензированную sutta можно открыть, читать,
  делать закладки
- Поповеры для палийских терминов работают
- Print-friendly + shareable
- Lighthouse Performance ≥ 90

---

## Phase 3: Search UI (дни 31-37)

Второй по важности surface — «search-first» UX.

### app-day-31 — Страница `/search`

1. `web/app/search/page.tsx`.
2. Форма с input + dropdown «все фильтры».
3. Debounced fetch (`useDebouncedCallback` 300ms).
4. URL state: `?q=…&tradition=…&lang=…` через `useSearchParams`.

### app-day-32 — Result cards

1. `web/components/search/ResultCard.tsx`.
2. Preview 200 символов с подсветкой matched terms.
3. Metadata badges: tradition, language, translator.
4. Score indicator (4 уровня: high/medium/low/weak) — не показываем
   сырое число, показываем человеческий бейдж.
5. Клик → открывает Reader в split-view.

### app-day-33 — Split-view (desktop)

1. Layout `grid-cols-[400px_1fr]`.
2. Слева — results list, справа — Reader с выбранным chunk.
3. Highlight матчи в Reader через DOM manipulation или
   react-highlight-words.
4. На mobile (<md) — results list overlay, клик открывает Reader
   full-screen.

### app-day-34 — Filter panel

1. Sheet (слева) с фильтрами: tradition (multi-select), language
   (multi), translator (autocomplete), date range, `restricted` toggle.
2. Query params синхронизированы.
3. Кнопка «reset all» + счётчик активных фильтров.

### app-day-35 — «Explain this passage» кнопка

1. На каждой result-card — маленькая кнопка `Explain`.
2. Клик → inline expand с streaming ответом от `/api/explain`.
3. Показывает citations inline.
4. Графически выделено: «AI-generated, verify with sources».

### app-day-36 — Source transparency panel

После explain — блок «используется N источников, не используется M» в
стиле Glean. Клик по «not used» — показывает почему (low relevance
score).

### app-day-37 — Search performance

1. Serverside caching `/api/search` на 5 минут для одинаковых запросов.
2. `<Suspense>` для streaming результатов.
3. Skeleton loading.
4. Lighthouse Performance ≥ 85 на `/search`.

**Gate после Phase 3:**

- Поиск находит релевантное, фильтры работают
- Split-view открывает исходник с highlight
- Explain опциональный, не навязчивый

---

## Phase 4: Chat Q&A (дни 38-45)

### app-day-38 — Страница `/chat`

1. `web/app/chat/page.tsx` — client component (state).
2. Chat UI: message list + input + streaming indicator.
3. Session state в памяти (sessionStorage для recovery на refresh).
4. Кнопка «new chat» — очищает state.

### app-day-39 — SSE streaming integration

1. `web/lib/sse.ts` — обёртка над `EventSource` + cleanup.
2. `useStream(query, llmKey)` custom hook.
3. События `retrieval_done`, `token`, `citation`, `done`, `error` —
   разный рендер для каждого.
4. Token-by-token появление ответа.

### app-day-40 — Citations rendering

1. Парсим ответ на `[n]` маркеры.
2. `<CitationLink n={1}>` компонент с hover-card.
3. Hover показывает: source_uid, cited_text, metadata.
4. Клик → новая вкладка с Reader + highlight на spans.

### app-day-41 — Pull-quote side panel

Справа от ответа — панель «quotes» со всеми цитатами в порядке
появления. Обязательный UI для религиозных текстов, anti-hallucination
шит.

### app-day-42 — Confidence indicator

Три бейджа:

- **Direct quote** (зелёный) — faithfulness > 0.9, ≥2 citations на
  ≥50% ответа
- **Synthesized** (жёлтый) — 0.7-0.9, ≥3 citations
- **Interpretive — verify with teacher** (оранжевый) — <0.7 или <2
  citations
- **No sources** (красный hardcoded) — если RAG вернул insufficient

### app-day-43 — Feedback widget

1. Под ответом — `👍 / 👎` + optional comment.
2. `POST /api/feedback` с trace_id.
3. Запись в `app.feedback` таблицу.

### app-day-44 — BYOK UI

1. Страница `/settings/keys` с полями: provider (dropdown), key (input
   type=password).
2. Кнопка «validate» — вызывает `/api/keys/validate`.
3. После valid — кладёт в cookie, редирект обратно в чат.
4. Баннер в шапке: «No key set — [Add key]» если ключа нет.
5. В чате кнопка «use default (demo limited)» — если без BYOK, то
   15 Q/день на IP.

### app-day-45 — Disclaimer footer + «Ask a human teacher»

1. Компонент `<ChatFooter/>` — всегда виден под chat input.
2. Текст: «This is not a substitute for a teacher. If in crisis: …»
3. Кнопка «Ask a human teacher» — mailto с prefilled query+context, или
   модалка с гайдом по контактам.

**Gate после Phase 4:**

- Q&A работает end-to-end на stub-RAG
- Citations кликабельны и ведут в Reader
- BYOK UI позволяет подключить свой ключ
- Confidence indicator честно показывает уровень уверенности

---

## Phase 5: Guardrails и Privacy (дни 46-52)

### app-day-46 — Crisis UI

Красивый hardcoded response, оформлен как отдельный layout. Hotlines в
виде кликабельных кнопок (звонок на mobile). Не выглядит как обычный
chat-response — визуально другое.

### app-day-47 — Wellbeing redirect UI

При детекции dark-night-триггеров — модальное окно с:

- Явное «this is not a generic answer»
- Список ресурсов: Cheetah House, Britton Lab, Samaritans
- Кнопка «I understand, proceed anyway» для информационного ответа
  (без меdical/practice advice)
- Запись пользовательского выбора в audit

### app-day-48 — Vajrayana gating

1. Для результатов с `restricted=true` — placeholder «This material
   requires initiation from a qualified teacher».
2. `/read/[source_id]` для restricted — страница с объяснением вместо
   текста.
3. Admin-flag `DHARMA_RAG_UNLOCK_RESTRICTED=true` для self-hosted
   instance — владелец инстанса может разблокировать для себя.

### app-day-49 — `/audit` публичная страница

1. Читает `/api/audit/{year}/{month}`.
2. Показывает: общее число запросов, число refused, breakdown по
   категориям (crisis, wellbeing, insufficient, restricted), топ-10
   общих причин.
3. НЕ показывает сами запросы даже анонимизированные — только агрегат.
4. Disclaimer внизу: «This is our transparency report».

### app-day-50 — `/privacy/export` UI

1. Форма с полем «your IP hash» (объясняем как получить).
2. Кнопка «export my data» → download JSON.
3. Параллельная кнопка «delete all my data» с confirm-диалогом.

### app-day-51 — `/sources` (Consent Ledger viewer)

1. Читает YAML из `consent-ledger/` через backend эндпойнт `GET
   /api/consent`.
2. Таблица: source, license, obtained_date, conditions.
3. Клик → подробности.
4. Фильтры по license type.

### app-day-52 — Deference language pass

Глобальный review всех текстов UI и LLM prompts:

- Нет «The Buddha says…» → «Sources from the Pali Canon say…»
- Нет «You should meditate on…» → «Texts describe the practice of…»
- Footer-дисклеймер на каждой странице (не только chat)
- Чек-лист в `docs/guardrails/deference-checklist.md`

**Gate после Phase 5:**

- Crisis response — hardcoded, быстрый, не зависит от RAG
- GDPR endpoints работают, документированы
- Consent Ledger публичен
- Все user-facing тексты прошли deference-review

---

## Phase 6: Deploy и Launch v0.1.0 (дни 53-60)

### app-day-53 — Hetzner provisioning

1. CX22 (€9/мес, 4 vCPU, 8 GB RAM, 80 GB NVMe), Ubuntu 24.04, EU
   (Helsinki или Nuremberg).
2. Security baseline: SSH-ключ-only, отключить password auth,
   unattended-upgrades, UFW (22/80/443), fail2ban.
3. Non-root user `dharma`, sudo без пароля.
4. Домен: подключить к Cloudflare, DNS указан на VPS.

### app-day-54 — Caddy + TLS

1. Caddy 2.x, автоматический Let's Encrypt.
2. Конфиг `deploy/Caddyfile`: reverse proxy на backend `:8000` и web
   `:3001`, HSTS, CSP, security headers.
3. Rate limit на edge: 100 req/min на IP.
4. Access log в JSON формате.

### app-day-55 — Production Docker Compose

1. `deploy/docker-compose.prod.yml` — без volume mounts, с тегами
   (не `latest`).
2. Multi-stage Dockerfile для `web` (build → nginx static или Next.js
   standalone).
3. Backend Dockerfile с `--user dharma`, gunicorn с uvicorn-workers.
4. Env file template `.env.prod.example`.

### app-day-56 — GitHub Actions CI

1. `.github/workflows/ci.yml` — на каждый PR:
   - pytest + coverage (backend)
   - tsc + eslint + web build (frontend)
   - docker build smoke test
2. `.github/workflows/cd.yml` — на push в `main`:
   - Build images, push в GHCR
   - SSH deploy на prod (через secrets)
   - Health-check после deploy, rollback на фейле

### app-day-57 — Backups

1. Cron на VPS: `00 3 * * *` — `pg_dump → gzip → rclone` в Hetzner
   Storage Box (€4/мес, 1 ТБ).
2. Retention: 7 daily, 4 weekly, 12 monthly.
3. Тест восстановления: скрипт `scripts/restore.sh` + smoke-test в
   staging.

### app-day-58 — Observability в prod

1. Phoenix контейнер (2 GB RAM), доступ по `/phoenix` с basic-auth.
2. Backend инструментирован OpenTelemetry → Phoenix.
3. Log aggregation: structlog JSON → file → logrotate (без сторонних
   сервисов в Phase 0).
4. UptimeRobot (free) на `https://dharma-rag.org/health` каждые 5 мин.

### app-day-59 — Load test и pre-launch checklist

1. `scripts/loadtest.py` через locust: 10 concurrent, 100 req/min на
   mix эндпойнтов.
2. Проверить на prod: нет OOM, нет 5xx, p95 < 1s для search / < 3s для
   stream.
3. Checklist `docs/launch-checklist.md`:
   - TLS работает
   - /health возвращает 200
   - Crisis kill-switch отрабатывает (тест с triggers)
   - BYOK валидация работает
   - Backups крутятся
   - Phoenix пишет traces
   - Каждая страница имеет disclaimer

### app-day-60 — Public launch v0.1.0

1. Tag `v0.1.0` + CHANGELOG.md обновлён.
2. Release notes с ограничениями («Phase 0 MVP, 56k chunks, BYOK only»).
3. Анонс: r/Buddhism, r/streamentry, SuttaCentral discuss (осторожно,
   с уважением к правилам сабов).
4. Мониторинг первых 24h: каждые 2 часа проверка Phoenix + logs.
5. Быстрая реакция на issues (label `post-launch-blocker`).

**Gate после Phase 6 = v0.1.0:**

- Публичный URL работает
- TLS, backups, observability в порядке
- Первые 10 реальных пользователей прошли end-to-end без блокеров

---

## Phase 7+: Mobile, Voice, Scale

Детализируется в отдельных документах по мере приближения. Ключевые
вехи:

### Phase 7: Mobile + Beta (месяцы 3-6)

- **PWA-first:** `web/` уже готов работать как PWA. Добавляем
  `manifest.json`, service worker (offline fallback для Reading Room),
  install prompt.
- **Capacitor обёртка** после того, как PWA стабилен. iOS + Android в
  Google Play / TestFlight alpha.
- **User accounts** (опционально): email + magic-link через Resend.
  Позволяет sync bookmarks между устройствами.
- **i18n:** добавляем RU как первый не-EN язык UI. Затем PL, DE по
  запросу сообщества.
- **Filter panel v2:** фасетный поиск, saved searches.
- **Migration Langfuse → Phoenix** (если ещё не сделана в RAG-треке) —
  для app-observability.

### Phase 8: Voice (месяцы 6-9)

**Решение:** pipeline (STT → RAG → TTS), не Speech-to-Speech. Это
совпадает с решением в `docs/Dharma-RAG.md`.

- **On-device default:** browser WebSpeech API + whisper.cpp WASM для
  тех браузеров, где WebSpeech недоступен.
- **Fallback cloud:** Deepgram Nova-2 STT + ElevenLabs TTS через BYOK.
- **Pali G2P preprocessor** (координация с RAG-треком) для корректного
  произношения.
- **Push-to-talk** по умолчанию, никогда always-on.
- **Intent → RAG vs safety-shortcut** на уровне STT-output (перед RAG).

### Phase 9: Scale (месяцы 9-12)

- Native app в Google Play release / Apple App Store.
- Full corpus (900k+ chunks) если RAG-трек успел.
- Опционально: local LLM на 2× RTX 5090 серверном узле как альтернатива
  BYOK для контрибьюторов с собственным hardware.
- Community docs, contribution pipeline, i18n расширение.
- v1.0.0.

---

## Параллельные треки

Вещи, которые идут **постоянно**, не привязаны к конкретному дню:

### 1. Docs alignment pass

`CLAUDE.md`, `ROADMAP.md`, часть `docs/old/` содержат устаревшие
параметры (150/600 слов, Langfuse as primary, старая последовательность
фаз). По мере работы обновляем их или помечаем как `archived`. ADR-0001
— source of truth до замены.

### 2. User feedback loop

С Day 60 (launch) — каждые 2 недели:

- Просмотр audit log + feedback
- Выявление топ-3 проблем
- Issue в GitHub с label `user-reported`
- Приоритизация в backlog

### 3. Буддолог в цикле

После Day 60 — периодический (раз в месяц) review:

- 30 случайных запросов + ответов
- Doctrinal accuracy rubric
- Фидбек в RAG-трек на prompt tuning

### 4. Security

Каждый квартал:

- `pnpm audit` + `pip-audit`
- OWASP ZAP автоматический scan prod
- Rotate `KEY_ENCRYPTION_KEY` (с graceful migration)

---

## Критический путь и зависимости

**Блокеры для Phase 6 launch:**

1. `RAGService` хотя бы в минимальной реализации (иначе launch на stub,
   что неприемлемо).
2. Golden set не обязателен для launch, но важен для honest quality
   indicator.
3. Домен, TLS, backups — обязательно до публичного URL.
4. Crisis kill-switch — обязательно до публичного URL, ethical gate.

**Параллельность с RAG-треком:**

Дни 1-20 app-трека могут идти **параллельно** с RAG-треком — мы на
stub. Интеграционный момент — day ~14-20 RAG-трека (когда у них есть
реальный `RAGService`). После этого переключаем `RAG_BACKEND=real` и
тестируем end-to-end.

**Если RAG-трек отстаёт:**

- Launch v0.1.0 на «Reading Room only» режиме: Search и Chat отключены,
  Reading Room + Sources + Audit работают. Это честный MVP.

---

## Операционные заметки

### Коммиты и PR

- Conventional commits: `feat(api): …`, `feat(web): …`, `fix(guardrails):
  …`, `docs(adr): …`.
- PR title = commit title, body содержит «Closes #N» для трекинга.
- Каждый PR ≤ 500 LOC (предпочтительно), чтобы review был реальным.

### Branches

- `main` — production, всегда зелёный
- `dev` — текущая разработка (мы на нём сейчас)
- `feat/app-day-NN-description` для фич
- PR из feature → dev, dev → main раз в неделю или на milestone

### ADR-политика

Каждое «large-impact» решение — ADR. Минимум на:

- Выбор фреймворков (Next.js, FastAPI — задним числом)
- BYOK cookie format (шифрование, TTL)
- Схема guardrails
- Deploy target (Hetzner vs alternative)

Формат — `docs/decisions/NNNN-slug.md`, status = `proposed | accepted |
superseded`.

### Риски и митигации (app-специфичные)

| Риск | Митигация |
|---|---|
| BYOK ключ утечёт в логах | Middleware-маска + тест что ключ не в structlog output |
| Streaming SSE глючит через Cloudflare | Использовать `X-Accel-Buffering: no` + HTTP/2 |
| Next.js SSR падает при cold start | Keep-warm через UptimeRobot + `ISR` для Reader-страниц |
| Пользователь думает что AI = учитель | Явный disclaimer на каждом экране + «Ask a human» кнопка везде |
| Crisis kill-switch пропускает случай | Monthly review refused-queries + expansion regex списка |

### Что мы намеренно НЕ делаем в v0.1.0

- Социальные фичи (комментарии, обсуждения)
- Персонализация (recommendation engine)
- Монетизация (всегда free)
- Аналитика поведения (privacy-first)
- Контент-генерация пользователями (нет user content)
- Voice (откладываем на Phase 8)
- Нативные приложения (PWA сначала)

---

> Sabbe sattā sukhitā hontu.
>
> Пусть все существа будут счастливы.
