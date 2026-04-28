# 16 — OpenAPI typegen для frontend (app-day-03)

> **Статус:** реализовано в app-day-03. `openapi.json` коммитится в
> repo как source-of-truth, `web/lib/api-types.ts` генерируется
> локально из него и **не коммитится**.

## Зачем

До этого дня frontend был type-blind относительно API: чтобы вызвать
`/api/answer`, нужно было **вручную писать TypeScript-типы**, которые
повторяют Pydantic-схемы из `src/answer/schemas.py`. Каждое изменение
бэкенда (например, добавление поля `style` в rag-day-24) требует
**ручной синхронизации** на frontend'е — иначе либо забыли поле, либо
поле есть, но `typescript` не знает о нём.

С typegen'ом цикл такой:

```
src/answer/schemas.py (Pydantic)        ← single source of truth
       ↓ (pnpm gen:openapi)
openapi.json (committed in repo)        ← reviewable contract artifact
       ↓ (pnpm typegen)
web/lib/api-types.ts (gitignored)       ← TS types generated 1:1
       ↓ import
web/lib/api-client.ts (committed)       ← thin typed wrappers
       ↓ used by
web/app/**/*.tsx                        ← Reading Room UI (app-day-04+)
```

Любое изменение Pydantic-схемы → diff в `openapi.json` в PR → ревьюер
явно видит контракт-изменение → frontend ловит его в compile-time.

## Архитектура

### 1. `openapi.json` коммитится

Не «ходим за schema на runtime в `/openapi.json`», а **держим артефакт
в repo**. Преимущества:

- **Reviewable diffs.** Ревьюер видит контракт-изменения как обычный
  файловый diff — отдельно от Pydantic-кода.
- **Frontend dev не нужен бэкенд.** `pnpm typegen` читает локальный
  `openapi.json` без uvicorn, Postgres, Qdrant.
- **CI guard.** Команда `pnpm check:openapi` проверяет что зафиксированный
  `openapi.json` синхронизирован с текущим состоянием Pydantic-схем —
  ловит drift до merge.

Файл: `openapi.json` в корне репо, ~20-30 KB.

### 2. Генерация: `scripts/export_openapi.py`

Python-скрипт загружает `src.api.app:create_app()` (в `RAG_BACKEND=stub`
режиме — не нужны Postgres/Qdrant), вызывает `app.openapi()`, сериализует
с `indent=2 + sort_keys=True + ensure_ascii=False` чтобы diff'ы были
минимальные. Поддерживает `--check` flag для CI.

```bash
python scripts/export_openapi.py            # writes ./openapi.json
python scripts/export_openapi.py --check    # exit 1 if file is stale
```

### 3. TypeScript-типы: `openapi-typescript`

Индустриальный стандарт-инструмент. Один npm-пакет, читает OpenAPI 3.x
spec, выплёвывает чистый `.ts` файл с `paths`, `components` и
`operations` интерфейсами — никаких runtime-зависимостей в bundle'е.

Генерация:
```bash
pnpm --filter web typegen
# → web/lib/api-types.ts
```

Файл `web/lib/api-types.ts` **gitignored** — пере-генерируется на каждый
запуск. Single source of truth — `openapi.json`.

### 4. Тонкая обёртка: `web/lib/api-client.ts`

Hand-rolled, **коммитится**. Использует сгенерированные типы для:

- Re-export ergonomic типов: `QueryRequest`, `AnswerRequest`,
  `AnswerResponse`, `Source`, `AnswerStyle`, `HealthResponse`
- Функции: `getHealth()`, `query(body)`, `ask(body)`
- Класс `ApiError` для surfaces FastAPI'-ных `{detail: ...}` ответов
- `isApiError()` type guard

```typescript
import { ask, type AnswerRequest } from "@/lib/api-client";

const req: AnswerRequest = { query: "что такое джхана?", style: "detailed" };
//                                              ^^^^^^^^ TS знает что valid: "auto"|"concise"|"detailed"|null
const response = await ask(req);
//    ^? AnswerResponse — answer / sources / citations / latency_ms / metadata
```

Почему не codegen клиента целиком (orval, openapi-fetch):
- Сейчас 3 endpoint'а, ручная обёртка проще и читабельнее
- Когда станет 10+ — мигрируем на `openapi-fetch` (использует тот
  же `paths` тип)

### 5. NPM-скрипты

В корневом `package.json`:

| script | действие |
|---|---|
| `pnpm gen:openapi` | Python скрипт → пишет `openapi.json` |
| `pnpm check:openapi` | проверяет что `openapi.json` соответствует текущим Pydantic-схемам (для CI) |
| `pnpm gen:api-types` | `gen:openapi` + `pnpm --filter web typegen` |
| `pnpm dev` | `concurrently` запускает web (3001) + api (8000) |

В `web/package.json`:

| script | действие |
|---|---|
| `pnpm typegen` | `openapi-typescript ../openapi.json -o ./lib/api-types.ts` |

## Использование

### Frontend dev workflow

```bash
# Активировать venv (нужен для `python scripts/export_openapi.py`).
# В PowerShell: `.\.venv\Scripts\activate.ps1`
# В bash:      `source .venv/Scripts/activate`

# После клона / pull'а — генерируем типы один раз:
pnpm gen:api-types

# Дальше работаем как обычно:
pnpm --filter web dev    # uvicorn не нужен, для UI dev'а

# Когда меняем Pydantic-схему на бэке:
pnpm gen:api-types       # обновляем openapi.json + api-types.ts
git add openapi.json     # commit'им изменение контракта
```

### CI workflow (планируется)

```yaml
- pnpm install
- pnpm check:openapi      # fails if openapi.json stale
- pnpm gen:api-types
- pnpm --filter web build
```

## Что НЕ делаем сегодня

- **Runtime валидация** через `zod` — типы только compile-time. Pydantic
  на бэке валидирует входные данные. Если frontend'у нужно валидировать
  ввод пользователя до отправки — добавим `zod` + конвертер из OpenAPI
  в zod-schemas. Не сейчас.
- **Полноценный codegen клиента** (orval / openapi-fetch). Слишком
  early — у нас 3 endpoint'а.
- **CI guard** на `pnpm check:openapi`. Когда настроим GitHub Actions —
  добавим первой проверкой.

## Файлы

| файл | роль |
|---|---|
| `scripts/export_openapi.py` | Python генератор `openapi.json` |
| `openapi.json` | committed contract artifact, ~20 KB |
| `web/package.json` | `openapi-typescript` в devDeps + `typegen` script |
| `web/lib/api-types.ts` | **generated, gitignored** |
| `web/lib/api-client.ts` | committed wrapper с типизированными функциями |
| `package.json` | root scripts: `gen:openapi`, `check:openapi`, `gen:api-types` |
| `web/.gitignore` | exclude `lib/api-types.ts` |

## Связанные документы

- [docs/CONTRACT_ANSWER.md](../CONTRACT_ANSWER.md) — публичный API контракт `/api/answer`
- [docs/concepts/13-rag-service-contract.md](13-rag-service-contract.md) — `/api/query` контракт
- [docs/concepts/15-answer-generation.md](15-answer-generation.md) — слой LLM-генерации
