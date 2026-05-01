# 19 — Chat MVP (app-day-22)

> **Статус:** реализовано в app-day-22 как **прототип**. Простой
> single-shot chat: textarea → `POST /api/answer` → answer + clickable
> citations + sources panel. **Без** SSE-streaming, BYOK, confidence
> indicator, feedback widget — это всё app-day-23+ инкрементально.

## Зачем сейчас, не на app-day-38 как в плане

Original APP_DEVELOPMENT_PLAN.md клал чат в Phase 4 (дни 38-45) — после
Reading Room polish (22-30) и Search UI (31-37). Это значит **минимум
16 дней работы** до того момента когда у пользователя появляется
рабочий chat-surface.

User'у нужен chat **сейчас**, для:

- ранней обратной связи на качество ответов
- демо-показа функционала
- основы для дальнейших итераций (streaming, citations UX, BYOK)

Backend (`POST /api/answer`) был готов с rag-day-24. На stub-режиме
работает за 2 ms без внешних зависимостей. Frontend — единственное что
разделяло нас от живого чата.

Этот day — **deviation от плана**, документированный здесь для будущего
читателя. Reading Room polish (outline, glossary, bookmarks) сдвигаются
в очередь после chat-инкрементов.

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

## Ключевые решения

### 1. Single-shot, не SSE-streaming

`ask(req)` — обычный `fetch` POST. Ответ показывается целиком после
LLM завершения работы. На default-модели DeepSeek V4 Flash ~14-25
секунд latency, на stub-режиме <5 ms.

Streaming — отдельный заход (rag-day-25 backend SSE + app-day-23
frontend `EventSource`). Сейчас «Thinking…» баннер закрывает gap.

### 2. Citation parser — pure function, не in-render

[`web/lib/citations.ts`](../../web/lib/citations.ts) изолирован от
рендера. Сигнатура:

```typescript
parseAnswerCitations(answer: string, knownIds: ReadonlySet<string>):
  ({ type: "text"; text: string } | { type: "citation"; ids: string[] })[]
```

Знание о том какие work_ids существуют (из `response.sources`) живёт
в `Set<string>`. Если LLM написал `[mn99]` (галлюцинация), этого ID нет
в sources → segment остаётся как text, не превращается в broken link.

Поддержка multi-citation: `[mn39, dn10]` → `{ ids: ["mn39", "dn10"] }`.
Splitter — comma + trim.

### 3. AnswerView — citation как inline badge, не footnote

```jsx
<span className="bg-accent/60 px-1.5 py-0.5 font-mono text-xs">mn10</span>
```

Inline (не нумерованная сноска [1] [2] [3]) — по двум причинам:

- **Reading-Room context.** Каждый citation — прямая ссылка на сутту,
  не на список references внизу. Inline сразу видно куда уйдёшь.
- **Multi-citation.** `[mn39, dn10]` рендерится как два бейджа рядом
  через запятую — без необходимости в footnote-нумерации.

Hover-card / preview — Phase 4 (app-day-40 в плане).

### 4. SourcesPanel — клик ведёт на segment-anchor

```tsx
const target = source.segment_id
  ? `/read/${source.work_canonical_id}#${encodeURIComponent(source.segment_id)}`
  : `/read/${source.work_canonical_id}`;
```

Reading Room (app-day-21) выставлял `id={segment_id}` на каждом
параграфе. Это деплинк цепочка работает end-to-end: chat-source →
правильный параграф в правильной сутте.

### 5. Error handling — surface FastAPI's `{detail}`

`ApiError.body` (из api-client.ts) содержит распарсенный FastAPI
response. Извлекаем `detail` если есть, иначе показываем `e.message`.
Стандартный shape для stub/real одинаков.

### 6. Стиль текста — `.dharma-text` class

И textarea, и AnswerView, и SourcesPanel snippets используют
`.dharma-text` (Noto Serif + kern/liga/calt). Pāli-диакритика в
ответах LLM рендерится корректно (важно для slabel: `satipaṭṭhāna`
не должно становиться `satipa??hana`).

См. концепт [17 — Базовый layout](17-base-layout.md).

## Что **НЕ** сделано (намеренно)

| Фича | Где |
|---|---|
| SSE token streaming | rag-day-25 backend + app-day-23 frontend |
| BYOK UI (cookie + validate endpoint) | app-day-44 (или раньше если нужно) |
| Confidence indicator (direct/synthesized/interpretive) | app-day-42 |
| Feedback widget (👍/👎) | app-day-43 |
| Hover-preview citations | app-day-40 |
| Pull-quote side panel | app-day-41 |
| Disclaimer footer + "Ask a human teacher" | app-day-45 (но minimal disclaimer уже в Footer) |
| Conversation history (multi-turn) | вне MVP — single-shot Q&A |

## Как проверить

### Stub-режим (без OpenRouter ключа)

```
cd C:\Users\PChia\Dharma-RAG; .\.venv\Scripts\activate.ps1; $env:RAG_BACKEND="stub"; uvicorn src.api.app:app --reload --port 8000
```

В отдельном окне:

```
cd C:\Users\PChia\Dharma-RAG; pnpm --filter web dev
```

Открыть `http://localhost:3001/chat`:

- Ввести «what is mindfulness?» → Enter
- Ожидаем: «Thinking…» секунду, потом answer (stub возвращает
  fixture-текст с `[mn10]`, `[sn56.11]`, `[dn22]`-citations)
- Citations подсвечены, клик → `/read/{id}` с правильным anchor
- SourcesPanel справа: 3 source-card'а с work_id + segment + score

### Real-режим (с OpenRouter)

Тот же flow, но:

```
$env:RAG_BACKEND="real"
$env:OPENROUTER_API_KEY="sk-or-..."
uvicorn src.api.app:app --reload --port 8000
```

Latency: 14-25 сек (DeepSeek V4 Flash). Ответы — настоящие, с цитатами
из live корпуса.

## Files

| файл | роль |
|---|---|
| `web/app/chat/page.tsx` | client page, state (query, isLoading, response, error) |
| `web/components/chat/ChatInput.tsx` | textarea + Enter-to-send |
| `web/components/chat/AnswerView.tsx` | linkified answer rendering |
| `web/components/chat/SourcesPanel.tsx` | source-card list (right column on desktop) |
| `web/lib/citations.ts` | pure parser `[work_id]` → segments |

## Связанные документы

- [docs/concepts/15-answer-generation.md](15-answer-generation.md) — `/api/answer` контракт
- [docs/concepts/17-base-layout.md](17-base-layout.md) — `.dharma-text` typography
- [docs/concepts/18-reading-room.md](18-reading-room.md) — куда ведут citations
- [docs/APP_DEVELOPMENT_PLAN.md](../APP_DEVELOPMENT_PLAN.md) — Phase 4 целиком (полный chat в app-day-38..45)
