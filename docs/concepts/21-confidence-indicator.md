# 21 — Confidence indicator (app-day-24)

> **Статус:** реализовано в app-day-24. Под ответом в чате — цветной
> бейдж: `well-grounded` / `synthesized` / `limited grounding` /
> `interpretive — verify with teacher` / `no sources`. Сигнал
> «насколько верить ответу» по структурным признакам, без NLP.

## Зачем

LLM-ответ выглядит одинаково уверенно независимо от того, опирается
он на 5 источников или на 0. Для буддийских текстов это особенно
опасно — если ответ интерпретативный (модель додумывает доктрину),
пользователь должен **знать** что нужна осторожность.

Industry pattern (Glean, Perplexity, NotebookLM): visible confidence
signal под ответом. Зелёный = можно использовать как-есть; красный =
проверь с учителем.

Без пользовательского feedback'а калиброваться не на чем — поэтому
делаем **структурный** heuristic (по числу citations + распределению),
а не ML-классификатор. Калибруем потом по реальным ответам.

## Логика

Pure-функция [`web/lib/confidence.ts`](../../web/lib/confidence.ts)::
`computeConfidence(answer, sources)` смотрит на:

1. **Количество уникальных work_id-citations** в тексте ответа —
   `[mn10]`, `[sn56.11]` matched через `parseAnswerCitations`
   (тот же parser что в `<AnswerView>`).
2. **Распределение** — где находится последняя цитата относительно
   длины ответа. Если все citations в первой половине — answer
   фронтально-загружен (модель сослалась во вступлении и потом
   говорит без поддержки). Если последняя цитата ≥60% от длины —
   распределена.

### Tier'ы

| Tier | Условия | Цвет | Расшифровка |
|---|---|---|---|
| `well-grounded` | ≥3 unique citations + распределение ≥60% | зелёный | надёжно, можно опираться |
| `synthesized` | ≥2 unique citations | жёлтый | синтез из нескольких — сверь с источниками |
| `limited` | ровно 1 unique citation | оранжевый | узкая база |
| `interpretive` | 0 citations в тексте | красный | модель говорит вне retrieved sources |
| `no-sources` | retrieval вернул 0 sources | красный | модель отказалась отвечать |

Пороги — стартовая калибровка. После сбора feedback (app-day-26
widget 👍/👎) можно подтюнить.

### Defensive cases

- Пустой `answer` или `sources=[]` → `no-sources` (тот же путь что
  в `<AnswerView>` — fallback message).
- Hallucinated `[mn99]` (work_id отсутствует в `sources`) — parser
  отбрасывает, не учитывается. Это **правильно**: модель сослалась
  на несуществующее, для confidence это плохой сигнал.

## Архитектура

```
chat/page.tsx
  └─ useMemo: computeConfidence(answer, sources)
       ↓
       ConfidenceBadge { tier, label, reason, ... }
           ├─ цветной dot (8px)
           ├─ label uppercase (font-semibold)
           └─ reason (короткое объяснение почему этот tier)
```

`useMemo` пересчитывает только при изменении response (не на каждый
рендер). Вычисление дешёвое (~O(n) по длине ответа), но мемоизация
бесплатная.

## Стиль бейджа

- **Border + bg + text** одного цветового семейства (emerald / amber /
  orange / rose / destructive) — light-mode и dark-mode варианты через
  `dark:text-emerald-300` и т.д.
- **Цветной dot** слева — компактный визуальный якорь, как в Linear
  status badges.
- Label uppercase + tracking-wider — отделяет от тела (reason).
- ARIA: `role="status"` + `aria-label="Confidence: {label}"` для
  screen-reader пользователей.

## Что **НЕ** сделано

| Фича | Где |
|---|---|
| Расширенная info-tooltip с описанием каждого tier'а | потенциально app-day-26 |
| ML-классификатор faithfulness (FactScore-style) | долгосрочно, после набора golden-данных feedback'а |
| Пороги per-style (concise может оправдать меньше citations) | app-day-26+, после калибровки |

## Как проверить

В chat'е (stub-режим):

```
cd C:\Users\PChia\Dharma-RAG; pnpm --filter web dev
```

Открой `/chat`, отправь любой запрос → под latency-строкой появится
бейдж.

В stub-режиме:
- 3 source'а возвращаются всегда
- Ответ содержит `[mn10][sn56.11][dn22]` распределённо → `well-grounded`
  (зелёный с reason'ом «3 sources cited and references are spread
  through the answer»)

В real-режиме (с DeepSeek V4 Flash):
- На запрос про джхану обычно ~3-4 unique citations распределённо →
  `well-grounded`
- На запрос вне корпуса — `no-sources` (модель отказывается)
- На borderline-запрос с 1 citation → `limited grounding`

## Files

| файл | роль |
|---|---|
| `web/lib/confidence.ts` | pure `computeConfidence(answer, sources)` |
| `web/components/chat/ConfidenceBadge.tsx` | визуальный бейдж с цветом по tier'у |
| `web/app/chat/page.tsx` | useMemo + рендер бейджа над `<AnswerView>` |

## Связанные документы

- [docs/concepts/19-chat-mvp.md](19-chat-mvp.md) — chat MVP (база)
- [docs/concepts/20-citation-hover-preview.md](20-citation-hover-preview.md) — hover-preview (предыдущий polish)
