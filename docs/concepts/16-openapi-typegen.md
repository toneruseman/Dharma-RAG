# 16 — OpenAPI typegen для frontend (app-day-03)

> **Статус:** реализовано в app-day-03. Файл `openapi.json` лежит в
> репозитории как «единый эталон контракта», а `web/lib/api-types.ts`
> генерируется локально каждым разработчиком и **не коммитится**.

## Зачем

Backend (Python, FastAPI) и frontend (TypeScript, Next.js) — это два
разных языка, которые должны договориться: какие поля есть в запросе,
какие — в ответе, какие из них обязательные. Этот «договор» называется
**API contract** (контракт API — формальное описание того, что клиент
отдаёт серверу и что сервер возвращает в ответ).

До этого дня контракт жил «в голове» у разработчика. Чтобы дёрнуть
эндпойнт `/api/answer`, на frontend нужно было вручную писать TypeScript-
типы, повторяющие Pydantic-схемы из `src/answer/schemas.py`. Каждый раз,
когда на бэке добавлялось поле (например, `style` в rag-day-24), кто-то
должен был помнить: «надо обновить ещё и фронтовые типы».

Аналогия: договор аренды квартиры существует в двух экземплярах. Если
владелец дописал пункт «без животных», но забыл сказать жильцу — будет
конфликт. С typegen'ом мы автоматизируем переписывание: владелец правит
свой экземпляр, а копия жильца **сама** перегенерируется один-в-один.

После typegen'а цикл выглядит так:

```
src/answer/schemas.py (Pydantic)        ← единый источник истины
       ↓ pnpm gen:openapi
openapi.json (коммитится в repo)        ← заверенный экземпляр контракта
       ↓ pnpm typegen
web/lib/api-types.ts (gitignored)       ← TS-типы, генерируются 1:1
       ↓ import
web/lib/api-client.ts (коммитится)      ← тонкие типизированные обёртки
       ↓ used by
web/app/**/*.tsx                        ← UI Reading Room (app-day-04+)
```

Изменили Pydantic-модель → diff в `openapi.json` попадает в pull request →
ревьюер видит «ага, контракт меняется» → frontend ловит несовместимость
**в момент сборки**, а не в продакшене.

## Что такое OpenAPI и typegen — простыми словами

**OpenAPI** (стандарт описания HTTP-API в виде JSON или YAML — как
«техпаспорт» всех ручек сервера: какие пути есть, что они принимают,
что отдают). Это просто текстовый файл с правилами «эндпойнт
`POST /api/answer` ждёт JSON с полями `query: string` и `top_k: number`,
а возвращает `{answer, sources, citations}`».

**FastAPI** (Python-фреймворк для веб-API; та библиотека, на которой у
нас написан backend). Большая удача: FastAPI **сам** генерирует
OpenAPI-спеку из обычного Python-кода — нам не нужно писать `openapi.json`
руками.

**Pydantic** (Python-библиотека валидации данных через type hints —
описываешь модель один раз, она сама проверяет входные JSON'ы и сама же
умеет описать себя для OpenAPI). Например:

```python
class AnswerRequest(BaseModel):
    query: str
    top_k: int = 5
    style: Literal["auto", "concise", "detailed"] | None = None
```

Этого достаточно: FastAPI увидит модель, поймёт что `query` обязательное,
а `style` — одно из трёх значений или `null`, и положит это знание в
`openapi.json`.

**TypeScript** (язык программирования = JavaScript плюс типы; компилятор
проверяет что мы не передаём строку туда, где ждут число). Frontend
написан на нём, и его типы должны совпадать с тем, что на бэке.

**typegen** (англ. «type generation» — автоматическая генерация
описаний типов). В нашем случае: берём `openapi.json` и из него
делаем TypeScript-файл с интерфейсами. Аналогия: автоматический
переводчик с Python на TypeScript — не для прозы, только для подписей
на коробочках.

**openapi-typescript** (npm-пакет; конкретный инструмент, который читает
OpenAPI-JSON и выдаёт `.ts` с типами). Один npm-пакет, ноль runtime-
зависимостей в финальном bundle'е — он работает только на стадии сборки.

## Архитектура

Pipeline (англ. «конвейер» — цепочка шагов, где выход одного шага идёт на
вход следующему) выглядит так:

```
┌──────────────────────────┐
│ Pydantic-модели          │  ← пишет backend-разработчик
│ src/answer/schemas.py    │
└──────────┬───────────────┘
           │ pnpm gen:openapi
           │ (запускает scripts/export_openapi.py)
           ▼
┌──────────────────────────┐
│ openapi.json             │  ← коммитится в git, ~20-30 KB
│ (корень репозитория)     │
└──────────┬───────────────┘
           │ pnpm typegen
           │ (запускает openapi-typescript)
           ▼
┌──────────────────────────┐
│ web/lib/api-types.ts     │  ← gitignored, перегенерируется локально
└──────────┬───────────────┘
           │ import
           ▼
┌──────────────────────────┐
│ web/lib/api-client.ts    │  ← коммитится; тонкие функции вокруг fetch
│ (ask, query, getHealth)  │
└──────────┬───────────────┘
           │ import
           ▼
┌──────────────────────────┐
│ web/app/**/*.tsx         │  ← страницы и компоненты UI
└──────────────────────────┘
```

Что здесь происходит на пальцах:

1. Backend-разработчик правит `schemas.py` — например, добавляет поле.
2. Кто-то (он же или тот, кто делает frontend-фичу) запускает `pnpm
   gen:openapi`. Скрипт стартует FastAPI **в stub-режиме** (без
   Postgres и Qdrant), просит у него `openapi.json`, и записывает на
   диск.
3. Этот `openapi.json` коммитится в pull request. Ревьюер видит diff
   контракта прямо в файлах изменений.
4. Локально (или в CI) выполняется `pnpm typegen` — он читает
   `openapi.json` и пишет `web/lib/api-types.ts` с TypeScript-типами.
5. Frontend импортирует типы из `api-types.ts` через тонкую обёртку
   `api-client.ts` и использует их в страницах.

## Ключевые решения

### 1. `openapi.json` коммитится в репо

Не «ходим за схемой на runtime через `GET /openapi.json`», а держим
зафиксированный артефакт прямо в файлах проекта.

Аналогия: нотариально заверенный экземпляр договора лежит в папке у обеих
сторон. Если владелец что-то добавит — это видно по штампу даты, и жилец
может сравнить со своей копией.

Что это даёт:

- **Reviewable diffs** (читаемые различия) — изменение контракта
  показывается в pull request как обычный файловый diff, отдельно от
  кода Pydantic-моделей. Ревьюер сразу видит «о, форма ответа поменялась».
- **Frontend-разработчик не зависит от запущенного бэкенда.** Команда
  `pnpm typegen` читает локальный `openapi.json`, ей не нужны uvicorn,
  Postgres, Qdrant. Pull'нул репо — генерируешь типы — работаешь.
- **CI guard** (англ. «защитник CI» — автоматическая проверка в
  continuous integration на каждом PR). Команда `pnpm check:openapi`
  сверяет: соответствует ли закоммиченный `openapi.json` актуальным
  Pydantic-моделям? Если нет — CI падает.

Аналогия CI guard: секретарь сверяет два экземпляра договора перед
каждой встречей. Если штампы разные — встреча отменяется, идите
синхронизируйтесь.

### 2. Генерация: `scripts/export_openapi.py`

Маленький Python-скрипт. Что он делает:

```python
app = create_app()  # FastAPI app в RAG_BACKEND=stub режиме
schema = app.openapi()
json.dump(schema, file, indent=2, sort_keys=True, ensure_ascii=False)
```

Три флага неочевидные, но критически важные:

- `indent=2` — красивое форматирование, чтобы diff читался построчно.
- `sort_keys=True` — стабильный порядок полей. Без него Python мог бы
  выдать поля в случайном порядке, и каждый запуск порождал бы шумный
  diff в git.
- `ensure_ascii=False` — кириллица сохраняется как кириллица, а не как
  `\u0434\u0436\u0445...` escape-последовательности.

Скрипт также поддерживает флаг `--check` для CI:

```bash
python scripts/export_openapi.py            # пишет ./openapi.json
python scripts/export_openapi.py --check    # exit 1 если файл устарел
```

В `--check`-режиме скрипт не пишет на диск, а **сравнивает** актуальный
вывод с тем что уже лежит в файле. Если различаются — выходит с кодом 1,
и CI падает.

### 3. TypeScript-типы делает `openapi-typescript`

Индустриальный стандарт. Один npm-пакет (плюс zero runtime-зависимостей
в финальном бандле — он работает только в момент сборки). Читает
OpenAPI 3.x спецификацию, выплёвывает `.ts`-файл с тремя главными
объектами:

- `paths` — словарь «URL → методы → запросы/ответы».
- `components` — словарь всех схем (Pydantic-моделей).
- `operations` — операции по `operationId`.

Команда:

```bash
pnpm --filter web typegen
# → web/lib/api-types.ts
```

Префикс `pnpm --filter web` означает «запусти скрипт `typegen` из
package.json пакета `web` в монорепе». **pnpm** (менеджер пакетов
JavaScript — как npm, но быстрее и с меньшим дублированием на диске; у
нас выбран как стандарт).

### 4. `web/lib/api-types.ts` — gitignored

Сгенерированный файл **не коммитится**. Каждый разработчик
перегенерирует его себе локально.

Аналогия: это как локальная распечатка контракта на принтере у себя дома —
твоя копия, ты её не таскаешь по почте коллегам. Если нужно — распечатал
заново из эталона.

Почему так:

- Одно изменение бэка → один diff в `openapi.json`, а не два (json + ts).
- Меньше merge-конфликтов: если два PR одновременно меняют схему, мерджить
  TypeScript-типы было бы больно.
- Source of truth (англ. «единственный источник истины» — то место,
  откуда копируются все остальные представления) ровно один:
  `openapi.json`.

В `web/.gitignore` стоит строка `lib/api-types.ts`.

### 5. Тонкая ручная обёртка: `web/lib/api-client.ts`

Этот файл, наоборот, **коммитится**. Он использует сгенерированные типы,
чтобы дать frontend-коду удобные функции:

```typescript
import { ask, type AnswerRequest } from "@/lib/api-client";

const req: AnswerRequest = { query: "что такое джхана?", style: "detailed" };
//                                              ^^^^^^^^ TS знает: "auto"|"concise"|"detailed"|null
const response = await ask(req);
//    ^? AnswerResponse — answer / sources / citations / latency_ms / metadata
```

В этом примере если опечатаемся (`style: "deteild"`), TypeScript-
компилятор прервёт сборку с ошибкой. Это **compile-time error**
(ошибка во время компиляции — то есть ловится в момент сборки, до того
как код попадёт пользователю; противоположность — **runtime error**,
которая случается в работающем приложении и часто выглядит как «у
пользователя что-то отвалилось»).

Что внутри обёртки:

- Re-export **ergonomic types** (англ. «эргономичные типы» — короткие
  понятные имена вместо длинных вложенных путей вроде
  `paths["/api/answer"]["post"]["requestBody"]["content"]...`):
  `QueryRequest`, `AnswerRequest`, `AnswerResponse`, `Source`,
  `AnswerStyle`, `HealthResponse`.
- Функции вокруг `fetch`: `getHealth()`, `query(body)`, `ask(body)`.
- Класс `ApiError` для обработки `{detail: ...}` ответов от FastAPI.
- Функция `isApiError()` — это **type guard** (англ. «страж типа» —
  функция, которая в TypeScript говорит компилятору «доверься мне, эта
  переменная определённого типа»). Пример:

```typescript
if (isApiError(err)) {
  // здесь TS знает: err.detail существует
  console.log(err.detail);
}
```

Без type guard'а компилятор не разрешит обращение к `err.detail`, потому
что `err` имеет тип `unknown`.

### 6. Пока не делаем codegen клиента целиком

Существуют инструменты (orval, openapi-fetch), которые умеют сгенерировать
**весь** клиент со всеми функциями автоматически. Мы их не используем
сейчас по простой причине: у нас 3 эндпойнта, и ручная обёртка короче и
читабельнее автогенерата.

Когда станет 10+ эндпойнтов — мигрируем на `openapi-fetch` (он использует
тот же `paths` тип, миграция дешёвая).

### 7. NPM-скрипты

В корневом `package.json` живут оркестрирующие скрипты:

| script | действие |
|---|---|
| `pnpm gen:openapi` | Python скрипт пишет `openapi.json` |
| `pnpm check:openapi` | проверяет актуальность `openapi.json` (для CI) |
| `pnpm gen:api-types` | `gen:openapi` + `pnpm --filter web typegen` |
| `pnpm dev` | `concurrently` запускает web (3001) + api (8000) |

В `web/package.json` — локальный шаг:

| script | действие |
|---|---|
| `pnpm typegen` | `openapi-typescript ../openapi.json -o ./lib/api-types.ts` |

Главная команда для frontend-разработчика — `pnpm gen:api-types`. Она
делает всё подряд: перегенерирует JSON и из него же типы.

## Что НЕ делаем

| Тема | Куда переехало |
|---|---|
| Runtime-валидация ответов через `zod` | отложено permanently — Pydantic уже валидирует на бэке; добавим если фронту понадобится валидировать пользовательский ввод до отправки |
| Полноценный codegen клиента (orval / openapi-fetch) | отложено до 10+ эндпойнтов — пока ручная обёртка проще |
| GitHub Actions CI guard на `pnpm check:openapi` | будет добавлено первой проверкой когда настроим Actions |
| Генерация SDK для других языков (mobile/Python-клиент) | вне scope MVP |

## Как проверить

Команды одной строкой (в PowerShell терминал вставляет только первую
строку из multi-line блоков, поэтому всё цепочкой через `;`).

Сгенерировать `openapi.json` с нуля и подтянуть его в TS-типы:

```
cd C:\Users\PChia\Dharma-RAG; .\.venv\Scripts\activate.ps1; pnpm gen:api-types
```

Ожидаем: видно две строки про `openapi.json` (записан) и `api-types.ts`
(сгенерирован). После — файлы существуют, причём `openapi.json` лежит в
корне, а `web/lib/api-types.ts` в подпапке.

Проверить, что `openapi.json` синхронизирован с актуальными
Pydantic-моделями (так же делает CI):

```
cd C:\Users\PChia\Dharma-RAG; .\.venv\Scripts\activate.ps1; python scripts/export_openapi.py --check
```

Ожидаем: exit code 0 и строчка `openapi.json is up to date`. Если кто-то
поменял схему и забыл коммитить json — выйдет с кодом 1 и diff-разницей.

Проверить, что typescript-компилятор видит сгенерированные типы:

```
cd C:\Users\PChia\Dharma-RAG\web; pnpm tsc --noEmit
```

Ожидаем: молча завершается без ошибок. Если в коде есть несовпадение с
контрактом — компилятор укажет файл и строку.

## Файлы

| файл | роль |
|---|---|
| `scripts/export_openapi.py` | Python-генератор `openapi.json` с флагом `--check` |
| `openapi.json` | коммитится; артефакт-контракт ~20-30 KB |
| `web/package.json` | `openapi-typescript` в devDeps + скрипт `typegen` |
| `web/lib/api-types.ts` | **генерируется, gitignored** |
| `web/lib/api-client.ts` | коммитится; тонкая обёртка с типизированными `ask`, `query`, `getHealth`, `ApiError`, `isApiError` |
| `package.json` | корневые скрипты `gen:openapi`, `check:openapi`, `gen:api-types`, `dev` |
| `web/.gitignore` | строка `lib/api-types.ts` |

## Связанные документы

- [docs/CONTRACT_ANSWER.md](../CONTRACT_ANSWER.md) — публичный API
  контракт `/api/answer`
- [docs/concepts/13-rag-service-contract.md](13-rag-service-contract.md) —
  контракт `/api/query`
- [docs/concepts/15-answer-generation.md](15-answer-generation.md) —
  слой LLM-генерации (источник Pydantic-моделей `AnswerRequest` /
  `AnswerResponse`)
- [docs/concepts/22-sse-streaming.md](22-sse-streaming.md) — после
  изменений SSE-эндпойнта надо re-run `pnpm gen:api-types`, чтобы
  событийные модели попали в TS
- [docs/APP_DEVELOPMENT_PLAN.md](../APP_DEVELOPMENT_PLAN.md) — раздел
  про app-day-03
