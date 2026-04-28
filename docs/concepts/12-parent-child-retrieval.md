# 12 — Parent/child retrieval (small-to-big)

## Что это

**Small-to-big retrieval** — паттерн: эмбеддинги и поиск **на маленьких чанках** (children, ~384 токена — точнее), а в LLM/UI отдаются **большие куски** (parents, ~1024-2048 токенов — богаче контекстом).

Один JOIN в Postgres связывает их через `chunk.parent_chunk_id` (self-reference). Пользователь видит «вот этот фрагмент сыграл» (`child_text`), а LLM получает целый абзац/раздел (`text`).

## Зачем у нас

День 14 baseline и день 17 A/B оба меряют **`ref_hit@K`** — попала ли правильная сутта в top-K. Это про **точность поиска**. Но retrieval-результат не существует в вакууме — на дне 22+ его получит LLM, который должен **сослаться** на источник и **обосновать** ответ.

С маленьким child'ом (~384 токена) у LLM мало контекста:

```
Без parent expansion:
  "Bhikkhus, when consciousness ceases, name and form cease. ..."
  [end of chunk]
```

С parent expansion:

```
"... 'And what is the noble truth of the cessation of suffering?
 When ignorance fades away and ceases with nothing left over, choices
 cease. When choices cease, consciousness ceases. When consciousness
 ceases, name and form cease. When name and form cease, the six
 sense fields cease. ...'"
 [end of parent passage — full reverse-order paṭiccasamuppāda]
```

LLM получает **смыслово-завершённый** отрывок: сутта, раздел, цепочка рассуждения целиком. Он может цитировать без обрыва на полуслове.

## Как работает у нас

```
1. Encode query (BGE-M3)
2. Search 3 channels (dense + sparse + BM25) → top-30 child chunk_ids
3. RRF fusion → top-30
4. ENRICH:                           ← День 18 main change
   SELECT chunk.id, chunk.text AS child_text,
          parent.text AS parent_text, ...
   FROM chunk
   JOIN ... (work/expression/instance)
   LEFT JOIN chunk parent ON parent.id = chunk.parent_chunk_id
   WHERE chunk.id IN (...)

   For each row:
     if parent_text is not NULL:
        HybridHit.text = parent_text   (small-to-big!)
        HybridHit.child_text = chunk's own text
        HybridHit.expanded = True
     else:
        HybridHit.text = child_text
        HybridHit.child_text = child_text
        HybridHit.expanded = False     (top-level chunk, no parent)
5. (Optional) rerank
6. Return
```

**Один SQL-запрос**, тот же что был в дне 12. LEFT JOIN значит: дети без parent'а (top-level) не теряются — fallback на их собственный текст.

## Что меняется в API

`POST /api/retrieve` теперь возвращает на каждый hit:
- `text` — passage (parent при expansion=True, иначе child)
- `child_text` — точный child fragment, для UI-highlight
- `expanded` — True если parent был подставлен

И принимает в request:
- `expand_parents: bool = True` — выключить если нужен старый day-12 формат

## Reranker и parent expansion

После дня 17 A/B было обнаружено: **BGE-reranker-v2-m3 деградирует качество на context-prefixed embeddings**. Логично, что reranker должен видеть **тот же текст**, что embedder — а если embedder работал на context+child, reranker scoring искажается.

Решение в нашем коде: reranker **всегда** получает `child_text` (не parent), независимо от parent expansion. Это:
- Сохраняет совместимость с тренировочными данными BGE-reranker'а
- Делает rerank-decision независимым от parent expansion
- Позволяет независимо включать/выключать оба флага

Но в production-default reranker всё равно отключён (`settings.retrieval_rerank_default = False`) после дня 17.

## Edge cases

**Несколько children одного parent в результатах**: каждый hit возвращается отдельно с **тем же** `parent_text`. Это технически дубль — но семантически разные **child snippets** этого parent. Дедупликация — фича на день 19+ (если пользователь увидит 5 одинаковых passage'ей, это плохо для UX).

**Parent очень большой** (~2048 токенов × top_k=8 = ~16K токенов в LLM): укладывается в Claude/GPT context window (200K+ для Sonnet 4.6). Если в будущем перейдём на меньшие модели — нужно truncation, но сейчас не блокер.

**Top-level chunks без parent**: legacy ingest или специальные документы. Fallback на own text работает прозрачно. `expanded=False` сообщает клиенту что parent expansion не сработал — UI может показать одинаковые `text` и `child_text`.

## Альтернативы

| Альтернатива | Почему не |
|---|---|
| **Sentence-window retrieval** (LlamaIndex) | Тоже small-to-big, но окно — фиксированное число sentences вокруг hit'а. У нас parent — это семантически структурированный кусок (раздел сутты), а не window. Структурный контекст лучше |
| **Hierarchical reranker** | Reranker оценивает parent-level. Дороже, не помогло на day-17 A/B |
| **Возвращать только child** (status quo до дня 18) | LLM получает обрывок, цитирование становится фрагментарным |
| **Не использовать parent expansion, эмбеддить parent**ы | Низкая precision: parents 1024-2048 токенов покрывают слишком много тем для одного embedding |

Small-to-big — каноничный pattern для RAG. Нашу реализацию сделали через self-JOIN (не отдельная коллекция, не лишний запрос).

## Где в коде

- [src/retrieval/schemas.py](../../src/retrieval/schemas.py) — `HybridHit.child_text`, `expanded` поля
- [src/retrieval/hybrid.py](../../src/retrieval/hybrid.py) — `_enrich(expand_parents=True)` SQL JOIN на parent
- [src/retrieval/hybrid.py](../../src/retrieval/hybrid.py) — `hybrid_search(expand_parents=...)` параметр
- [src/api/retrieve.py](../../src/api/retrieve.py) — `RetrieveRequest.expand_parents`, `RetrieveResultItem.child_text/expanded`
- [src/config.py](../../src/config.py) — `retrieval_expand_parents_default`
- [tests/unit/retrieval/test_hybrid.py](../../tests/unit/retrieval/test_hybrid.py) — тесты с обновлённым fake_enrich

## Производственный эффект

После дня 18 cutover:
- `RetrievalResources` использует `dharma_v2` + `rerank=False` + `expand_parents=True` по умолчанию
- Latency: ~65ms/запрос (как и без parent expansion — JOIN дешёвый)
- LLM получит богатый контекст когда дойдёт до дня 22 — без необходимости выкатывать дополнительный шаг
