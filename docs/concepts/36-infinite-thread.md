# 36 — Бесконечный тред (LLM-free)

## Что это

Страница `/thread` — это альтернативный режим Q&A, где пользователь
задаёт вопрос **один раз**, а потом нажимает «Далее» сколько хочет, и
каждое нажатие выдаёт следующую канонической отрывок (chunk) из
корпуса по тому же запросу. **LLM не вызывается ни разу.**

Концептуально — это «направляемое чтение источников»: вместо того
чтобы получать пересказ, читатель листает сами суттры, в порядке
релевантности.

## Зачем у нас

В Dharma-RAG / Yoniso это **флагманская фича**, которая делает проект
уникальным относительно ChatGPT/Opus подписки. Что мы получаем:

| Свойство | Эффект |
|---|---|
| **$0 на раунд** | Можно сделать бесплатным для community без BYOK |
| **~200 ms latency** | Мгновенный feel, как Twitter feed |
| **Zero hallucination** | Каждое слово дословно из канона — критично для religious content |
| **Brand-aligned** | Само название «Yoniso» (yoniso manasikāra) = «внимание к источнику»; режим буквально это и делает |
| **Trust** | Пользователь видит сам текст, а не нашу интерпретацию |
| **Accessibility** | После first sync работает offline (на будущее) |

## Как работает

```
┌──────────┐  POST /api/thread/next        ┌─────────────────────┐
│  React   │ ── { query, excluded_ids } ─→ │  RAGService.thread  │
│ /thread  │                               │     _next()         │
│          │ ←── { cards: [...], exhausted │                     │
└──────────┘                               └─────────┬───────────┘
                                                     │
                              ┌──────────────────────┼─────────────────┐
                              │                      │                 │
                              ▼                      ▼                 ▼
                          ┌────────┐          ┌──────────┐      ┌────────────┐
                          │ Qdrant │          │ Postgres │      │ Postgres   │
                          │ dense+ │          │ BM25 FTS │      │ JOIN chunk │
                          │ sparse │          │          │      │ + ctx + tr │
                          └────────┘          └──────────┘      └────────────┘
                              └─────────┬──────────┘
                                        ▼
                                    RRF fusion (k=60)
                                    expand_parents=False
                                        │
                                        ▼
                              filter excluded_chunk_ids
                                        │
                                        ▼
                                   top_k фрешных
```

### Что в карточке

Каждый `ThreadCard` несёт:

* `chunk_id` — UUID, который клиент возвращает в следующем запросе
* `work_canonical_id` + `segment_id` (например `mn10:8.1`)
* `text` — сам канонический отрывок (~200-500 слов)
* `context_text` — **пре-сгенерированный** narrative-prefix (Haiku
  3.5, rag-day-16). Бесплатный во runtime, потому что считается на
  ингесте
* `translator` (`sujato`, `thanissaro`, `sv`...)
* `language_code` (`eng`, `rus`, `pli`)
* `score` — нормализованная релевантность

Frontend рендерит каждую карточку с разделом:
1. Бейдж раунда + work / segment + score
2. Курсивный intro (`context_text`) — если есть
3. Сам текст — verbatim, no synthesis
4. Footer: переводчик / язык + ссылка в Reading Room

### Stateless backend

Сервер ничего не помнит между запросами. Клиент сам ведёт список
`excluded_chunk_ids` (просто массив UUID'ов всех показанных карточек)
и присылает его в следующем POST. Преимущества:

* Никаких сессий, БД-state'а, redis'а
* Можно сделать любую feature над этим (share thread URL, экспорт,
  пагинация back) без backend-изменений
* Тривиальный rate-limiting (per-IP top_k * round)

## Альтернативы

| Что было можно | Почему не сделали |
|---|---|
| **LLM-thread** (продолжать ответ) | Стоимость $0.003/round, latency 14-25s, hallucination. Хорошо для broad questions, плохо для медитативного режима. Будет добавлено как toggle потом. |
| **MMR diversification** (penalty на близкие) | Тоньше, но требует encoder-side вычислений. Source-exclusion проще и достаточно для корпуса 28K чанков. |
| **Sub-question generation** (LLM → новый запрос) | Реальный thought-thread, но опять же LLM в цикле. Можно добавить как «вариант B» позже. |
| **Dimension rotation** (round 1 канон, round 2 commentary, round 3 учитель) | Ждёт мульти-source корпус. Сейчас 95% Sujato — диверсифицировать нечего. После Phase 3 (ATI / DhammaTalks / Dharmaseed) — добавим. |

## Ограничения текущего MVP

1. **Diversification только по chunk_id**. Один и тот же work может
   показываться много раз (разные chunks). Когда появится Thanissaro/
   Bodhi — добавим toggle «другой переводчик» / «другой work».
2. **Нет re-rank между раундами**. RRF order сохраняется; за раунд
   берётся top_k самых релевантных из не-excluded. Можно делать MMR
   позже.
3. **Score падает быстро**. На узком запросе после 3-4 раундов
   `top_score < 0.5` — пора показывать «End of thread» по threshold,
   а не только по `len(filtered) < top_k`. TODO.
4. **LLM-mode toggle** ещё не сделан. Сейчас это полностью отдельная
   страница `/thread`. Hybrid (синтез/source) можно добавить как
   переключатель в `/chat`.

## Где в коде

### Backend
- [src/rag/schemas.py](../../src/rag/schemas.py) — `ThreadRequest`, `ThreadCard`, `ThreadResponse`
- [src/rag/service.py](../../src/rag/service.py) — `RAGService.thread_next()`
- [src/rag/protocol.py](../../src/rag/protocol.py) — protocol contract
- [src/api/thread.py](../../src/api/thread.py) — `POST /api/thread/next` router
- [src/api/_rag_stub.py](../../src/api/_rag_stub.py) — `StubRAGService.thread_next` для frontend dev

### Frontend
- [web/app/thread/page.tsx](../../web/app/thread/page.tsx) — страница `/thread`
- [web/components/thread/PassageCard.tsx](../../web/components/thread/PassageCard.tsx) — карточка одного passage'а
- [web/lib/api-client.ts](../../web/lib/api-client.ts) — `threadNext()` функция
- [web/components/layout/Header.tsx](../../web/components/layout/Header.tsx) — nav-link «Thread»

## Что дальше

После MVP можно поднимать:
1. **Toggle режимов** в `/chat` (синтез ↔ источник)
2. **Diversification по `(work, translator)`** когда появятся параллельные переводы
3. **MMR-rerank** между раундами для тонкого баланса relevance↔novelty
4. **Score threshold** для autostop вместо счётчика
5. **Share-link** треда (`/thread?q=...&seen=...`)
6. **Дerivative fragmenting** для «глубокого» режима — каждое нажатие даёт parent (~1024 ток) вместо child (~384)
