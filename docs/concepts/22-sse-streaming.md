# 22 — SSE streaming для /api/answer (app-day-25)

> **Статус:** proposed (concept review). Backend WIP в commit
> 95f47bd на ветке feat/app-day-25-sse-streaming-backend; frontend,
> tests, OpenAPI re-gen, финализация — после approve концепта.

## Зачем нам streaming

Сейчас `POST /api/answer` работает «буферизованно»: backend ждёт пока
модель сгенерирует **весь** ответ, и только потом одним JSON-телом
отдаёт его на фронт. На default-модели (DeepSeek V4 Flash) это
**14-25 секунд** ожидания. Всё это время пользователь смотрит на
крутилку «Thinking…».

Аналогия: «положил заказ в окошко и ушёл пить чай — обед принесут
когда повар приготовит весь его целиком». Со streaming'ом — как в
ChatGPT: первые слова появляются за 1-2 секунды, ответ «печатается»
посимвольно. Аналогия меняется на «официант приносит блюда по мере
готовности — салат уже на столе, пока готовится горячее».

Streaming не делает суммарную генерацию быстрее (LLM всё равно
работает 14-25 сек), но **резко улучшает ощущение скорости**: первый
токен через ~1-2 сек, дальше плавный поток.

## Что такое SSE

**SSE** (Server-Sent Events — стандарт W3C для односторонней
потоковой передачи событий от сервера в браузер по одному долгоживущему
HTTP-соединению) — родной транспорт для нашего сценария.

Аналогия: SSE = **трансляция футбольного матча**. Один сервер
(стадион) шлёт обновления (голы, пасы) многим клиентам (зрителям),
никто серверу не отвечает. Один канал, одна сторона говорит.

Контраст: **WebSocket** (другой стандарт связи браузер ↔ сервер,
двусторонний канал поверх TCP) = **телефонный разговор**. Обе
стороны могут говорить когда хотят. Для LLM-стрима «сервер шлёт
токены вниз» это лишняя сложность — нам не нужен upstream-канал
от клиента.

Формат SSE на проводе — простой текст по HTTP:

```
event: token
data: {"delta":"джхана"}

event: citation
data: {"id":"mn36","position":124}

```

Каждое событие — это две строки (`event:` имя, `data:` JSON-полезная
нагрузка) и пустая строка-разделитель в конце. Браузер сам собирает
эти блоки и отдаёт обработчику; нам нужно только yield'ить такие
куски на сервере и парсить их на клиенте.

## Архитектура

```
Client (браузер)
  │  POST /api/answer/stream  (Content-Type: application/json)
  │  body: { query, top_k, style, ... }
  ▼
┌───────────────────────────────────────────────────────────────┐
│ src/api/answer.py :: answer_stream()                          │
│   EventSourceResponse(event_generator(), ping=15)             │
│   (sse-starlette: keep-alive + disconnect detection)          │
└────────────────┬──────────────────────────────────────────────┘
                 ▼
┌───────────────────────────────────────────────────────────────┐
│ AnswerService.stream_answer(req)        src/answer/service.py │
│                                                               │
│   yield RetrievalDoneEvent(sources, retrieval_latency_ms)     │
│                                                               │
│   async for chunk in AsyncOpenRouterLLM.stream(...):          │
│       yield TokenEvent(delta=chunk.delta)                     │
│       for found in scanner.feed(chunk.delta):                 │
│           yield CitationEvent(id=found.id, position=...)      │
│                                                               │
│   yield DoneEvent(answer, citations, latency_ms, metadata)    │
│   (или yield ErrorEvent(code, message) при сбое)              │
└────────────────┬──────────────────────────────────────────────┘
                 ▼
┌───────────────────────────────────────────────────────────────┐
│ AsyncOpenRouterLLM.stream()              src/answer/llm.py    │
│   chat.completions.create(stream=True,                        │
│     stream_options={"include_usage": True})                   │
│   async for upstream_chunk in stream:                         │
│       yield StreamChunk(delta=...)         (много раз)        │
│   yield StreamChunk(delta="", tokens_in=, tokens_out=, ...)   │
└───────────────────────────────────────────────────────────────┘
```

Что здесь происходит на пальцах:

1. Клиент шлёт обычный `POST` с JSON-телом — никаких особых
   заголовков, кроме `Content-Type`.
2. FastAPI оборачивает наш **async-генератор** (специальная Python-
   функция, которая yield'ит значения по одному, а не сразу всё —
   аналогия: «лента в магазине, кассир кладёт чеки по мере покупок,
   а не один большой счёт в конце») в `EventSourceResponse` от
   `sse-starlette`.
3. Генератор сначала делает retrieval (поиск релевантных chunk'ов в
   Qdrant), эмитит событие `retrieval_done`, и **только потом**
   начинает звать LLM в режиме `stream=True`.
4. Каждый кусочек ответа от LLM (`delta` — несколько символов, иногда
   слово) превращается в одно событие `token`.
5. Параллельно сканнер цитат смотрит в проходящий текст и при виде
   `[mn10]` эмитит `citation`.
6. Когда LLM закончил — терминальное событие `done` с финальным
   ответом и метаданными. Если что-то сломалось — `error` вместо
   `done`.

## Пять типов событий

Все события — Pydantic-модели в `src/answer/stream_schemas.py`.
**Pydantic** — это Python-библиотека, которая в runtime проверяет
что ваши данные соответствуют объявленным типам, и заодно умеет
генерить JSON-схему. У нас она уже используется везде для
request/response-схем FastAPI.

### `retrieval_done`

«Я нашёл такие источники. Покажи их сразу пока я думаю над ответом.»

```json
{"sources":[{"work_id":"mn10",...}], "retrieval_latency_ms": 1.2, "pipeline_version":"stub-v1"}
```

Frontend получает это событие почти сразу (~100-200ms после submit'а)
и рендерит правый `SourcesPanel` — пользователь видит «о, нашёл
тексты», пока LLM ещё думает.

### `token`

«Вот следующий кусочек ответа. Допиши к тому что у тебя уже есть.»

```json
{"delta":"джхана "}
```

Frontend хранит accumulated buffer (накопленный ответ как одну
строку), на каждый `token` делает `buffer += delta` и rerender'ит
`AnswerView`. Так и достигается эффект «печатания».

Здесь **token** — это **LLM-токен**, кусочек текста (обычно
часть слова или короткое слово), не путать с auth-токеном (ключ
для аутентификации). И **chunk** в этом контексте — это HTTP-
chunk потока, не наш `Chunk` из FRBR-модели (фрагмент дхарма-
текста после chunking'а).

### `citation`

«Только что я закончил писать `[mn10]`. Можешь подсветить этот
work_id если хочешь, но это не обязательно — ты и сам парсишь
скобки.»

```json
{"id":"mn10","position":124}
```

Сейчас frontend этот сигнал использует только для телеметрии
(логировать когда первая citation появилась). Реальная
подсветка цитат делается своим regex-парсером на TS — см.
решение №7.

### `done`

«Я закончил. Вот финальный ответ целиком плюс вся метаинформация.»

```json
{"answer":"...","citations":["mn10","sn56.11"], "latency_ms":18234, "metadata":{...}}
```

Терминальное событие на success. Frontend финализирует state
(метаданные пойдут в будущий confidence-badge), убирает индикатор
«печатает».

### `error`

«Что-то сломалось. Вот код и сообщение.»

```json
{"code":"llm_failed","message":"OpenRouter timeout"}
```

Терминальное на failure — заменяет `done`. Frontend показывает
ошибку в UI.

Контракт последовательности:

```
retrieval_done  →  (token | citation)*  →  (done | error)
```

То есть: один `retrieval_done`, потом сколько угодно `token`/
`citation` в перемешку, и ровно одно из `done` или `error` в конце.

## Семь ключевых решений

### 1. Новый эндпойнт `/api/answer/stream` рядом с `/api/answer`

Не меняем существующий — добавляем новый. Зачем: мобильные
клиенты, eval-скрипты для тестов качества, OpenAPI-контракт —
всё остаётся как есть. **OpenAPI** (спецификация для описания
REST-эндпойнтов в виде машинно-читаемого JSON; в проекте
`openapi.json` рендерится FastAPI и используется для генерации
TypeScript-типов на frontend'е) — у каждого эндпойнта своя
форма ответа: один путь = один content-type. Buffered отвечает
`application/json`, streaming — `text/event-stream`.

### 2. Используем библиотеку `sse-starlette`

Уже в `pyproject.toml`. Сама делает **keep-alive ping** (раз
в 15 секунд посылает пустую строчку чтобы прокси-сервера и CDN не
дропнули idle-соединение через 30-60 секунд), сама ловит когда
клиент отключился (отдаёт нашему генератору `CancelledError`), сама
правильно сериализует словари в SSE-формат. Свой код = +50 строк
за нулевую выгоду.

### 3. Новый метод `stream()` в LLM-клиенте, не замена `complete()`

Аддитивно: старый `complete()` для buffered эндпойнта работает как
работал. Новый `stream()` живёт рядом и возвращает **AsyncIterator**
(типизированный итератор для `async for`-цикла, выдающий значения
асинхронно — аналогия: «ты идёшь к буфету и берёшь блюда по одному,
не ждёшь пока все принесут»).

Под капотом — `chat.completions.create(stream=True,
stream_options={"include_usage": True})`. Параметр **stream_options**
с `include_usage: True` — это специальный флаг для OpenRouter:
«когда будешь заканчивать, дай мне ещё один финальный chunk с
полем `usage` — там token-counts». Без него мы не узнаем сколько
токенов потратили (важно для метаданных и биллинга).

### 4. `IncrementalCitationScanner` — отдельный класс с состоянием

В non-streaming пути regex прогоняется по полному ответу один раз.
В стриме так нельзя: токены приходят кусками, и `[mn10]` может быть
**разорвана между двумя чанками** (`partial bracket` — открывающая
скобка пришла в одном chunk'е, закрывающая в следующем): chunk_n =
`"... [mn"`, chunk_{n+1} = `"10] ..."`.

Аналогия: «человек читает книгу с карандашом и помечает ссылки
`[mn10]` как только увидит закрывающую скобку — не перечитывая
заново уже отмеченное».

```python
scanner = IncrementalCitationScanner(valid_ids={"mn10","sn56.11"})
scanner.feed("... [mn")     # → []  (скобка не закрылась — ждём)
scanner.feed("10] ...")     # → [CitationFound(id="mn10", ...)]
scanner.feed("[mn10] again")# → []  (тот же id уже видели — skip)
```

Внутри держит **buffer** (joined текст всех feed'ов — строка
которая накапливается) и **cursor** (`_scan_from` — позиция
указатель, докуда regex уже искал; следующий feed начинает
сканирование с этой позиции, не с начала). Плюс `set` уже выданных
id чтобы не дублировать.

Зачем класс, а не функция: **нужно сохранять состояние между
вызовами**. Чистая функция была бы stateless (без памяти), а нам
надо помнить «что уже видели» и «где остановились».

### 5. Frontend через `fetch` + `ReadableStream`, не через `EventSource`

**EventSource** — это родной браузерный API специально для SSE.
Открывает соединение и автоматически парсит event-stream — звучит
идеально, но не подходит:

- Умеет только GET. Наше тело запроса (`AnswerRequest` с `query`,
  `top_k`, `style`, ...) в querystring пихать уродливо и упрётся
  в URL-лимит.
- Не позволяет передавать кастомные заголовки. Это убивает **BYOK**
  (Bring Your Own Key — пользовательский OpenRouter-ключ, который
  юзер передаёт в заголовке для биллинга на свою сторону; в проекте
  это app-day-28).

Поэтому идём через **`fetch`** (стандартный браузерный API для HTTP-
запросов; делает обычный POST с JSON-body и любыми заголовками)
плюс **`ReadableStream`** (объект, представляющий поток байтов из
`response.body` — позволяет читать тело по мере поступления, не
дожидаясь всего ответа).

```ts
const res = await fetch("/api/answer/stream", { method: "POST", body, headers });
const reader = res.body!.getReader();
const decoder = new TextDecoder();
let buffer = "";
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  for (const event of parseSSEEvents(buffer)) { dispatch(event); }
  buffer = leftoverAfterLastNewline(buffer);
}
```

Что делает этот код: открываем соединение, получаем `reader` для
потока байтов, в цикле читаем кусочки, декодируем UTF-8, накапливаем
в `buffer`, и при появлении полных SSE-блоков (разделённых пустой
строкой) парсим их в события и диспатчим. Парсинг SSE-формата руками
— ~40 строк. Цена за полную свободу: POST, custom headers, abort
через `AbortController`.

### 6. Stub имитирует streaming, не отдаёт всё разом

`StubAnswerService.stream_answer()` (в `src/api/_answer_stub.py`)
эмитит фиксированный ответ кусками **по 30 символов с задержкой
40ms между чанками**. Total ~1.5 секунды.

Зачем: frontend-разработчик ловит **race condition'ы** (ситуация
когда два асинхронных события могут случиться в разном порядке и
поведение зависит от того кто успеет первым) без OpenRouter-credit'ов
и без зависимости от backend deploy'я. Например:

- что если пользователь нажал «отменить» когда половина пришла?
- что если новый запрос отправлен раньше чем старый завершился?
- корректно ли мы освобождаем `ReadableStream` reader на unmount?

Те же события, та же последовательность, тот же
`IncrementalCitationScanner` — просто с искусственными задержками.

### 7. Frontend re-парсит citations на каждый chunk простой regex-функцией

Backend шлёт `citation` event'ы — но `AnswerView.tsx` всё равно
re-парсит accumulated answer на каждый rerender через
`web/lib/citations.ts::parseAnswerCitations()`. **Regex** (regular
expression — формальный язык для описания текстовых паттернов;
например `\[([a-z]+\d+)\]` ловит `[mn10]`) на строке в пару KB
занимает миллисекунды; повторить 250 раз за весь стрим — всё равно
меньше 50ms.

Альтернатива — держать инкрементальное состояние сегментов и
обновлять по `citation` events. Дороже в коде и риск **desync**
(рассинхрон когда backend и frontend разойдутся в логике парсинга
и покажут разные citation'ы). Pure-функция = **idempotent**
(вызывая её снова с теми же входами получаешь тот же выход — без
побочных эффектов; противоположность stateful-логики), безопасный
выбор.

`CitationEvent`'ы от backend'а используются как сигналы для
телеметрии и future-proofing, но не как источник истины для render'а.

## Что НЕ делаем в этом дне

| Тема | Куда переехало |
|---|---|
| BYOK forwarding (`X-OpenRouter-Key` через заголовок) | app-day-28 |
| Retry / reconnection при разрыве сети | отложено permanently — нужен resumable stream + idempotency token (механизм при котором повторный запрос с тем же ключом не порождает дубль), большой scope |
| SSE auth (signed URLs, per-stream tokens) | вместе с rate-limit (ограничение количества запросов в единицу времени) в app-day-45 |
| Phoenix per-token spans | отложено permanently — раздуло бы trace cardinality (количество уникальных значений в трейсах — много per-token spans = шумные дашборды) |
| Замена `/api/answer` на streaming | не делаем никогда — buffered нужен для mobile/eval/admin |
| Server-side cancel в OpenRouter при disconnect | follow-up after launch; пока полагаемся на `CancelledError` + idle timeout OpenRouter'а |
| Rate-limit на streaming endpoint | app-day-45 |
| Multi-turn conversation history | вне scope MVP |

## Тесты (что планируется)

7 unit/integration-тестов:

1. **`AsyncOpenRouterLLM.stream` — terminal usage chunk.** Mock
   OpenAI-клиента, три delta + финальный usage chunk. Проверяем
   что delta склеиваются и финальный yield несёт `tokens_in`/
   `tokens_out`.
2. **`AnswerService.stream_answer` — happy path.** Мокаем
   RAG + LLM stream. Проверяем порядок: `retrieval_done` →
   N×`token` → M×`citation` → `done`.
3. **Empty sources path.** Stub возвращает пустые sources —
   ожидаем `retrieval_done(sources=[])` + сразу `done(answer="")`,
   без LLM-вызова между ними.
4. **LLM падает в середине.** После 2 token'ов yield `ErrorEvent`
   с `code="llm_failed"`, без `done`.
5. **Brackets across chunks.** Скармливаем сканнеру `"... [mn"`
   потом `"10] говорит ..."` — ровно один `CitationEvent`,
   после второго feed'а.
6. **Endpoint integration test.** TestClient + stub backend,
   парсим SSE-frame'ы, проверяем последовательность.
7. **Frontend SSE parser unit (Vitest добавится).** Синтетический
   stream разбитый на куски в произвольных местах — обработчики
   получают типизированные события.

## Как проверить локально

Команды одной строкой (PowerShell вставляет только первую строку
из multi-line блоков).

После того как backend готов — запустить в stub-режиме:

```
cd C:\Users\PChia\Dharma-RAG; .\.venv\Scripts\activate.ps1; $env:RAG_BACKEND="stub"; uvicorn src.api.app:app --reload --port 8000
```

В отдельном окне — запрос. Нюанс: в PowerShell `curl` это alias
для `Invoke-WebRequest`, который буферизует ответ. Используем
`curl.exe` (настоящий бинарник curl'а из `C:\Windows\System32\`) с
флагом `-N` (`--no-buffer`):

```
curl.exe -N -X POST http://localhost:8000/api/answer/stream -H "Content-Type: application/json" -d '{"query":"what is mindfulness?","top_k":3}'
```

Должны увидеть последовательность строк `event: ...` / `data: {...}`
приходящих с задержкой ~40ms между token'ами. Через ~1.5 секунды
последнее событие — `event: done`. Если видите всё разом одним
куском — забыли `-N`, curl буферизует stdout.

После того как frontend готов — `pnpm --filter web dev`, открыть
`http://localhost:3001/chat`, отправить запрос. В DevTools → Network
запрос `answer/stream` имеет тип `eventsource` и не закрывается до
`done`. В UI: `SourcesPanel` рендерится в первую секунду, текст
ответа «печатается» посимвольно, citation-badges подсвечиваются по
мере появления.

## Файлы

| Файл | Тип | Зачем |
|---|---|---|
| `src/answer/stream_schemas.py` | новый | 5 Pydantic-моделей для каждого типа события |
| `src/answer/llm.py` | изменён | добавлен `stream()` рядом с `complete()` + dataclass `StreamChunk` |
| `src/answer/service.py` | изменён | `stream_answer()` + `IncrementalCitationScanner` + `CitationFound` |
| `src/answer/protocol.py` | изменён | в Protocol добавлен `stream_answer()` |
| `src/api/_answer_stub.py` | изменён | имитация streaming для stub-режима |
| `src/api/answer.py` | изменён | `POST /api/answer/stream` через `EventSourceResponse` |
| `tests/answer/test_stream_*.py` | новые | unit-тесты scanner'а, llm.stream(), service.stream_answer() |
| `web/lib/sse.ts` | новый (после approve) | парсер SSE из ReadableStream |
| `web/lib/api-client.ts` | изменён (после approve) | `streamAnswer(req, onEvent, signal)` |
| `web/app/chat/page.tsx` | изменён (после approve) | переход с `ask()` на `streamAnswer()` |
| `web/openapi.json` + `web/lib/api-types.ts` | re-gen (после approve) | типы для новых событий |

## Связанные документы

- [docs/concepts/15-answer-generation.md](15-answer-generation.md) — `/api/answer` baseline (buffered)
- [docs/concepts/19-chat-mvp.md](19-chat-mvp.md) — текущий single-shot чат, который этот day апгрейдит
- [docs/concepts/16-openapi-typegen.md](16-openapi-typegen.md) — typegen pipeline (надо будет re-run после изменений)
- [docs/APP_DEVELOPMENT_PLAN.md](../APP_DEVELOPMENT_PLAN.md) — раздел про app-day-25
