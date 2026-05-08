# 19 — Chat MVP (app-day-22)

> **Статус:** реализовано в app-day-22 как **прототип**. Простой
> single-shot чат: textarea → `POST /api/answer` → ответ + кликабельные
> цитаты + панель источников справа. **Без** SSE-streaming, BYOK,
> confidence-индикатора, feedback-виджета — это всё app-day-23+
> инкрементально.

## Зачем

User'у нужно место где можно задать дхарма-вопрос своими словами и
получить ответ с цитатами на конкретные сутты. Существующие страницы
(`/search`, `/read/[uid]`) — это поиск и чтение, но не разговорный
интерфейс. Чат закрывает эту дырку.

По плану `APP_DEVELOPMENT_PLAN.md` чат был запланирован в Phase 4 (дни
38-45) — после Reading Room polish и Search UI. То есть **минимум 16
дней работы** до того как у пользователя появляется работающий чат.

User'у нужен чат **сейчас**, для:

- ранней обратной связи на качество ответов от LLM
- демо-показа функционала
- основы для будущих итераций (streaming, hover-preview, confidence)

Backend `POST /api/answer` уже был готов с rag-day-24 — на stub-режиме
работает за 2ms без внешних зависимостей. Frontend — единственное что
разделяло нас от живого чата.

Этот day — осознанный сдвиг с плана. Reading Room polish (outline,
glossary, bookmarks) уезжает в очередь после chat-инкрементов.

## Что такое Chat MVP

**Chat MVP** (Minimum Viable Product — минимально жизнеспособный
продукт; самая простая версия которая уже приносит пользу) — это
single-shot Q&A.

**Single-shot** значит «один вопрос → один полный ответ». Пользователь
жмёт Enter, видит «Thinking…», ждёт 14-25 секунд, потом получает
**целиком** готовый ответ. Противоположность — **streaming** (когда
ответ «печатается» на глазах буква за буквой, как в ChatGPT).

Аналогия: single-shot = «положил заказ в окошко и ушёл пить чай —
обед принесут когда повар приготовит весь его целиком». Streaming =
«официант приносит блюда по мере готовности». В app-day-22 у нас
первый вариант, в app-day-25 переедем на второй.

Чем чат отличается от обычной поисковой страницы (`/search`):

- На поиске — список результатов, ты сам читаешь и собираешь смысл.
- В чате — LLM читает результаты за тебя и пишет связный текст с
  цитатами на конкретные сутты.

То есть чат это «retrieval + LLM-обзорка с обязательными источниками»,
а не альтернатива поиску.

## Архитектура

```
web/app/chat/page.tsx               (client component, useState)
            ↓
web/components/chat/
  ├─ ChatInput.tsx                  (textarea + Enter-to-send)
  ├─ AnswerView.tsx                 (parsed answer, linkified citations)
  └─ SourcesPanel.tsx               (top-k passages → /read/[uid])
            ↓
web/lib/citations.ts                (pure parser, [mn10] → segments)
            ↓
web/lib/api-client.ts::ask(req)
            ↓
POST /api/answer                    (rag-day-24)
```

Что здесь происходит на пальцах:

1. `page.tsx` — это **client component** (страница в Next.js с
   интерактивностью; JavaScript исполняется в браузере, а не на
   сервере; помечается директивой `"use client"` сверху файла).
   Аналогия: «интерактивная анкета которая запоминает что ты ввёл», в
   отличие от server component (статическая HTML-страница, никакой
   реакции на клики).
2. State (текущий запрос, isLoading-флаг, ответ, ошибка) живёт в
   **useState** (React-хук для состояния компонента — переменная
   которая запоминается между рендерами; обычное `let x = ...` не
   подходит, потому что React постоянно вызывает функцию-компонент
   заново и обычная переменная сбрасывалась бы).
3. ChatInput ловит Enter, дёргает callback `onSubmit` родителя.
4. Родитель вызывает `ask(req)` из `api-client.ts` — обычный fetch POST
   на `/api/answer`.
5. После ответа — `AnswerView` рендерит текст с подсвеченными
   цитатами, `SourcesPanel` рендерит карточки источников справа.

## Ключевые решения

### 1. Single-shot, не SSE-streaming

`ask(req)` — обычный `fetch` POST. Ответ показывается целиком после
того как LLM закончил работу. На default-модели (DeepSeek V4 Flash)
~14-25 секунд latency, на stub-режиме <5ms.

Почему single-shot а не streaming сразу: streaming требует SSE-парсера
на frontend'е, async-генератора на backend'е, новой схемы событий и
обработки race condition'ов (когда два асинхронных события могут
случиться в разном порядке). Это +2-3 дня работы. На MVP важнее иметь
**рабочий чат за один день**, а UX-доработка через streaming — отдельный
заход (rag-day-25 backend + app-day-25 frontend, см. концепт 22).

Сейчас «Thinking…» баннер закрывает gap.

### 2. Citation parser — чистая функция, отдельно от рендера

**Citation** (цитата-ссылка) — маркер вида `[mn10]` в тексте ответа,
который указывает на work_id (идентификатор суттa, например MN10 =
Satipaṭṭhāna Sutta) из Pāli-канона.

Аналогия: **citation — это именная карточка-ссылка в книжном обзоре**,
ведёт на конкретную страницу первоисточника. В нашем случае — на
параграф в `/read/mn10`.

**Citations parser** (функция вытаскивающая `[mn10]` маркеры из текста)
живёт в `web/lib/citations.ts` и не зависит от React. Сигнатура:

```typescript
parseAnswerCitations(answer: string, knownIds: ReadonlySet<string>):
  ({ type: "text"; text: string } | { type: "citation"; ids: string[] })[]
```

На вход — текст ответа и **`Set<string>`** (структура данных в
JavaScript: коллекция уникальных строк с быстрой проверкой `has()`).
Аналогия: **Set vs Array — это алфавитный указатель в книге vs
длинная очередь**. В алфавитном указателе ты сразу прыгаешь на букву
«М» и проверяешь есть ли «mn10» — за миллисекунду. В очереди надо
пройти по всем элементам подряд. Для парсера каждой цитаты у нас
такая проверка может выполняться сотни раз за рендер, поэтому Set.

На выход — массив сегментов: либо `text` (обычный текст), либо
`citation` (одна или несколько work_id-ов).

### 3. Hallucinated citation guard

**Hallucinated citation** (галлюцинированная цитата) — это когда LLM
выдумал ссылку: написал `[mn99]`, но этого work_id нет в наших
sources (источниках возвращённых retrieval'ом). Модель «выдумала»
ссылку на несуществующую сутту.

Парсер это ловит:

```typescript
const knownIds = new Set(response.sources.map(s => s.work_canonical_id));
const segments = parseAnswerCitations(response.answer, knownIds);
```

Передаём в парсер только work_id'ы из `response.sources`. Если LLM
написал `[mn99]`, а `knownIds` не содержит `"mn99"` — этот сегмент
остаётся как обычный `text`, не превращается в кликабельную ссылку
(которая вела бы в никуда, в 404).

Поддержка multi-citation: `[mn39, dn10]` парсится как `{ ids: ["mn39",
"dn10"] }`. Splitter — comma + trim.

### 4. AnswerView — citation как inline-бейдж, не сноска

```jsx
<span className="bg-accent/60 px-1.5 py-0.5 font-mono text-xs">mn10</span>
```

Inline-бейдж рендерится прямо в потоке текста (а не вынесен в
нумерованную сноску `[1] [2] [3]` внизу) по двум причинам:

- **Reading-Room context.** Каждая цитата — прямая ссылка на сутту, не
  на список references внизу страницы. Inline сразу видно куда уйдёшь.
- **Multi-citation.** `[mn39, dn10]` рендерится как два бейджа рядом
  через запятую — без необходимости в footnote-нумерации.

Hover-card / preview (всплывающее окно с превью сутта при наведении) —
Phase 4, app-day-23 в нашем графике.

### 5. `.dharma-text` класс для шрифта

Pāli-диакритика (особые знаки над буквами: `ā`, `ṭ`, `ñ`) часто
ломается в дефолтных шрифтах: `satipaṭṭhāna` превращается в
`satipa??hana`. Класс `.dharma-text` подключает Noto Serif с
включёнными `kern` (кернинг — расстояние между буквами), `liga`
(лигатуры — слитное написание `fi`, `fl`) и `calt` (контекстные
альтернативы).

И textarea, и AnswerView, и SourcesPanel snippets — все используют
`.dharma-text`. Подробнее в концепте [17 — Базовый layout](17-base-layout.md).

### 6. ChatInput с Enter-to-send + Shift+Enter для новой строки

Textarea ловит keydown. Enter без Shift'а отправляет, Shift+Enter
переносит строку.

```tsx
const onKeyDown = (e: KeyboardEvent) => {
  if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
    e.preventDefault();
    onSubmit();
  }
};
```

Что здесь важно — **`isComposing` guard для IME composition**. **IME**
(Input Method Editor — система ввода для языков с большим алфавитом:
китайский, японский, корейский, плюс эмодзи на mobile) собирает символ
из нескольких нажатий. Промежуточные Enter'ы во время composition'а
**подтверждают выбор иероглифа**, а не отправляют форму. Если на них
сработает `onSubmit()` — отправится недопечатанный запрос, а IME
сломается.

Сам textarea — это **controlled input** (поле ввода чьё значение
полностью управляется React-state'ом; `value={query}` + `onChange`).
Аналогия: «электронный ценник в магазине, цена которого приходит из
центральной системы — само поле не помнит ничего, только показывает
что ему сказали».

### 7. SourcesPanel — клик ведёт на segment-anchor

```tsx
const target = source.segment_id
  ? `/read/${source.work_canonical_id}#${encodeURIComponent(source.segment_id)}`
  : `/read/${source.work_canonical_id}`;
```

Reading Room (концепт 18, app-day-21) выставлял `id={segment_id}` на
каждом параграфе. Эта деплинк-цепочка работает end-to-end: клик по
source-card в чате → правильный параграф в правильной сутте.

`encodeURIComponent` нужен потому что segment_id может содержать точки
и специальные символы (`mn10.1.2`), а они должны быть escape'нуты в
URL-fragment.

### 8. Error handling через `ApiError.body.detail`

**ApiError class** (наш custom Error с полями status / body / response;
определён в `api-client.ts`) — это специальный класс ошибки, который
бросается когда API вернул не-2xx статус. Оборачивает сырой response,
чтобы UI мог достать структурированную информацию.

**FastAPI** (Python web-фреймворк на котором построен наш backend) при
ошибке возвращает стандартный shape: `{"detail": "сообщение об
ошибке"}`. Это поле **`detail`** — соглашение FastAPI для
человекочитаемого сообщения.

```tsx
catch (e) {
  if (e instanceof ApiError && e.body?.detail) {
    setError(e.body.detail);
  } else {
    setError(e instanceof Error ? e.message : "Unknown error");
  }
}
```

Что делает этот код: если поймали `ApiError` и в нём есть `detail` —
показываем именно его (например «Rate limit exceeded»). Иначе fallback
на generic `e.message`. Stub и real-режим возвращают одинаковый shape,
поэтому код не различает их.

Это пока не **error boundary** (обёртка ловящая ошибки в React-дереве —
когда компонент упал во время рендера). Error boundary — это для
багов в самом React-коде. У нас тут API-ошибка, обычный try/catch.

### 9. Layout — `grid-cols-[1fr_280px]` на desktop'е

```tsx
<div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
  <main>{/* ChatInput + AnswerView */}</main>
  <aside>{/* SourcesPanel */}</aside>
</div>
```

На mobile (single-column) — input и ответ сверху, sources снизу. На
desktop (≥1024px) — две колонки: основная — flexible (`1fr` —
fractional unit, забирает всё оставшееся место), правая — фиксированные
280px. SourcesPanel помещается, ответ остаётся читаемым (~720px при
типичной ширине окна).

### 10. useMemo для парсинга citations

```tsx
const segments = useMemo(
  () => parseAnswerCitations(response.answer, knownIds),
  [response.answer, knownIds]
);
```

**useMemo** (React-хук для мемоизации вычислений — кэшируем результат
пока зависимости не изменились) — это «не пересчитывай парсер при
каждом нажатии клавиши на input'е, пока сам ответ не поменялся».

Аналогия: **useMemo = «закладка с готовым ответом — не пересчитываем
если ничего не изменилось»**. Без него каждый rerender (а они
случаются на любое изменение state'а — печатаешь в input, тоже
rerender) парсер прогонялся бы заново. Парсинг 2KB-ответа — пара
миллисекунд, не катастрофа, но привычка беречь работу есть привычка
беречь работу.

## Что НЕ делаем

| Фича | Куда переехало |
|---|---|
| SSE token streaming | rag-day-25 backend + app-day-25 frontend (концепт 22) |
| Hover-preview citations (всплывающее превью сутта) | app-day-23 (концепт 20) |
| Confidence indicator (метка direct/synthesized/interpretive) | app-day-24 (концепт 21) |
| BYOK UI (Bring Your Own Key — пользовательский OpenRouter-ключ) | app-day-28 |
| Feedback widget (кнопки 👍/👎) | app-day-43 |
| Pull-quote side panel | app-day-41 |
| Disclaimer footer + "Ask a human teacher" | app-day-45 (минимальный disclaimer уже в Footer) |
| Conversation history (multi-turn — последовательность реплик с памятью) | вне MVP — single-shot Q&A |

## Как проверить

Все команды в одну строку — PowerShell вставляет только первую строку
из multi-line блоков.

### Stub-режим (без OpenRouter ключа)

Backend в первом окне:

```
cd C:\Users\PChia\Dharma-RAG; .\.venv\Scripts\activate.ps1; $env:RAG_BACKEND="stub"; uvicorn src.api.app:app --reload --port 8000
```

Frontend в отдельном окне:

```
cd C:\Users\PChia\Dharma-RAG; pnpm --filter web dev
```

Открыть `http://localhost:3001/chat`:

- Ввести «what is mindfulness?» → нажать Enter
- Ожидаем: «Thinking…» секунду, потом ответ (stub возвращает
  fixture-текст с `[mn10]`, `[sn56.11]`, `[dn22]`-citations)
- Citations подсвечены жёлтым, клик → `/read/{id}` с правильным anchor
- SourcesPanel справа: 3 source-карточки с work_id + segment_id + score

### Real-режим (с OpenRouter)

Тот же flow, но:

```
cd C:\Users\PChia\Dharma-RAG; .\.venv\Scripts\activate.ps1; $env:RAG_BACKEND="real"; $env:OPENROUTER_API_KEY="sk-or-..."; uvicorn src.api.app:app --reload --port 8000
```

Latency: 14-25 секунд (DeepSeek V4 Flash, без streaming'а пользователь
смотрит на «Thinking…» весь этот промежуток). Ответы — настоящие, с
цитатами из живого корпуса.

### Проверка hallucinated guard'а

Чтобы убедиться что несуществующие work_id не превращаются в битые
ссылки: спросить у LLM что-то очень общее, добавить в системный
промпт fake citation для теста. Проще — поправить fixture в
`src/api/_answer_stub.py`, добавить туда `[mn99999]` и проверить что в
UI оно осталось текстом, не стало `<a>`.

## Файлы

| Файл | Роль |
|---|---|
| `web/app/chat/page.tsx` | Client page, state (query, isLoading, response, error) |
| `web/components/chat/ChatInput.tsx` | Textarea + Enter-to-send + IME guard |
| `web/components/chat/AnswerView.tsx` | Linkified answer rendering через segments |
| `web/components/chat/SourcesPanel.tsx` | Список source-карточек (правая колонка на desktop'е) |
| `web/lib/citations.ts` | Чистый парсер `[work_id]` → segments |
| `web/lib/api-client.ts` | `ask(req)` — fetch wrapper + ApiError class |

## Связанные документы

- [docs/concepts/15-answer-generation.md](15-answer-generation.md) — `/api/answer` контракт (backend)
- [docs/concepts/17-base-layout.md](17-base-layout.md) — `.dharma-text` typography
- [docs/concepts/18-reading-room.md](18-reading-room.md) — куда ведут citation-ссылки
- [docs/concepts/20-citation-hover-preview.md](20-citation-hover-preview.md) — следующий шаг по UX цитат (app-day-23)
- [docs/concepts/21-confidence-indicator.md](21-confidence-indicator.md) — confidence-метка (app-day-24)
- [docs/concepts/22-sse-streaming.md](22-sse-streaming.md) — streaming-апгрейд (app-day-25)
- [docs/APP_DEVELOPMENT_PLAN.md](../APP_DEVELOPMENT_PLAN.md) — Phase 4 целиком
