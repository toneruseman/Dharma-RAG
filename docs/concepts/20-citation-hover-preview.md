# 20 — Hover-preview для citations (app-day-23)

> **Статус:** реализовано в app-day-23. Малый chat-polish инкремент:
> наводишь курсор на бейдж `[mn10]` — выскакивает tooltip со snippet'ом
> из соответствующего источника.

## Зачем

После app-day-22 chat работает, но чтобы понять «о чём цитата `[mn10]`»
надо кликать в неё и переходить в Reading Room. Это лишний шаг.
Hover-preview даёт **быстрый peek** без потери контекста чата:
наводишь — видишь snippet и score, понимаешь стоит ли читать целиком.

Особенно полезно при multi-citation `[mn39, dn10]` — наводишь на
каждый бейдж по очереди, выбираешь куда углубиться.

## Архитектура

Один новый компонент-обёртка вокруг существующего citation Link:

```
AnswerView
  └─ <CitationBadge workId source />     ← новый
       ├─ Tooltip (shadcn / @base-ui/react)
       │   ├─ TooltipTrigger render={<Link>}
       │   └─ TooltipContent
       │       ├─ work_id · segment_id · score
       │       └─ snippet (.dharma-text)
```

`<TooltipProvider>` уже глобально подключён в `web/app/layout.tsx`
(app-day-04, `delay={150}`) — локальный provider не нужен.

## Ключевые решения

### 1. `Map<work_id, Source>` в `AnswerView`

Многие источники могут иметь один `work_canonical_id` — это разные
segments (фрагменты) одной работы, которые матчнули. Например, для
запроса «mindfulness» в top-5 могут быть `mn10:8.1`, `mn10:12.3`,
`mn10:46.1` — три разных segment'а одной MN10.

Для hover-preview мы выбираем **один** — с максимальным score, тот же
куда уйдёт пользователь по клику. Логика:

```typescript
const sourceByWorkId = useMemo(() => {
  const map = new Map<string, Source>();
  for (const source of response.sources) {
    const existing = map.get(source.work_canonical_id);
    if (!existing || source.score > existing.score) {
      map.set(source.work_canonical_id, source);
    }
  }
  return map;
}, [response.sources]);
```

`useMemo` — React-хук мемоизации: пересчитывает Map только когда
`response.sources` меняется. Без него Map бы пересоздавался на каждый
рендер.

### 2. `render` prop вместо `asChild`

shadcn/ui перешёл с `radix-ui` на `@base-ui/react` — у них немного
другой API. Чтобы заставить `<TooltipTrigger>` отрендериться как
`<Link>`, используется prop `render`:

```tsx
<TooltipTrigger render={<Link href={target}>{workId}</Link>} />
```

(В radix было бы `<TooltipTrigger asChild><Link>...</Link></TooltipTrigger>`.)

### 3. Graceful fallback на отсутствующий source

```typescript
if (!source) {
  return link;  // plain Link без Tooltip
}
```

Theoretically невозможен (parser в `lib/citations.ts` уже фильтрует
hallucinated work_ids), но компонент защищён от этого случая —
рендерит ссылку без подсказки, не падает.

### 4. Tooltip-content — тот же layout что в SourcesPanel card

Для consistency. Хедер: `work_id · segment_id` слева, `score` справа.
Тело: snippet в `.dharma-text` (Noto Serif). Так пользователь сразу
узнаёт формат — что в hover-preview, что в боковой панели sources
информация одинаково организована.

`max-w-sm` (384px) — достаточно для большинства snippets без переноса
строк, но при длинных — `whitespace-normal` корректно обернёт.

## Что **НЕ** сделано

| Фича | Где |
|---|---|
| Полный текст параграфа в tooltip (не snippet) | будет в app-day-26 (Pull-quote panel — это там вид нужнее) |
| Mobile: на touch-устройствах tap → tooltip, второй tap → переход | будем смотреть в перфоманс-passе app-day-37 |
| Keyboard shortcut: Tab + Enter показывает tooltip | базовое поведение из @base-ui уже работает; кастомизация позже |

## Как проверить

```
cd C:\Users\PChia\Dharma-RAG; .\.venv\Scripts\activate.ps1; $env:RAG_BACKEND="stub"; uvicorn src.api.app:app --reload --port 8000
```

Отдельное окно:

```
cd C:\Users\PChia\Dharma-RAG; pnpm --filter web dev
```

Открой `http://localhost:3001/chat`, отправь любой запрос. В ответе
будут citation-бейджи (`[mn10]`, `[sn56.11]`, `[dn22]`). Наведи курсор
на любой → через ~150мс появится tooltip:

- Заголовок: `mn10 · mn10:8.1` (моноширинный) и `0.92` справа
- Тело: snippet'a (для stub'а — «Just mindful, they breathe in...»)
- Уйдёт через ~150мс после убирания курсора

Клик по бейджу — по-прежнему ведёт в `/read/{id}#{segment_id}`.

## Files

| файл | роль |
|---|---|
| `web/components/chat/CitationBadge.tsx` | новый — Tooltip-wrapped citation |
| `web/components/chat/AnswerView.tsx` | заменён inline-Link на CitationBadge, добавлен sourceByWorkId Map |

## Связанные документы

- [docs/concepts/19-chat-mvp.md](19-chat-mvp.md) — chat MVP (база)
- [docs/concepts/17-base-layout.md](17-base-layout.md) — `.dharma-text` + TooltipProvider в layout
