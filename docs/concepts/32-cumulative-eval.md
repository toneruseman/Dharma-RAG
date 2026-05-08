# 32 — Cumulative re-eval после rag-day-28/29/30

> **Статус:** реализовано (rag-day-32, 2026-05-08).
> Малый день измерения. Прогнан eval на golden v0.0_extended (n=100)
> с включёнными definitional expansion + foundational boost + BM25
> translation bridge + расширенным `foundational.yaml` (rag-day-30).
> Результат: `ref_hit@5` 0.450 → 0.480 (+3pp), `ref_hit@1` 0.190 → 0.260
> (+7pp), MRR 0.307 → 0.360. См. `docs/EVAL_RAG_DAY_32.md`.
> Decision call: **MARGINAL** (0.480 < 0.50), но `@1` jump +7pp —
> сильный сигнал на канонических definitional-запросах.

## Что это простыми словами

После rag-day-28/29/30 у нас три новых retrieval-механизма поверх
baseline'а:

1. **Definitional expansion** — ловит «What is X?» / «Что такое X?»
   и переписывает в gloss-template.
2. **Foundational boost** — curated map `term → canonical sutta`
   (23 entries), post-RRF score boost.
3. **BM25 translation bridge** — английские aliases из YAML идут в
   BM25-канал через `OR`-clauses (Sujato переводит pāli→en, голый
   pāli-токен в теле текста = 0 hits).

Каждый механизм мы проверяли точечно — для отдельных запросов
(`dukkha`, `satipaṭṭhāna`, `самадхи`). Но **никогда не мерили
кумулятивный эффект на golden v0.0_extended** (n=100). Без этого
числа решение «cut v0.2.0» — гадание.

## Зачем у нас

Phase 2 close-out gate: `v0.2.0` обещал «quality lift над v0.1.0»
(ref_hit@5 = 0.450 на golden v0.0_extended). Чтобы заявить цифру
честно, нужен **прогон в той же конфигурации** что v0.1.0, но с
включёнными новыми механизмами.

## Что считаем

Две конфигурации, обе на `dharma_v2 + rerank=False + expand_parents=True`:

| Cell | expand_pali | expand_definitional | foundational_boost | bm25_aliases |
|---|---|---|---|---|
| **A.** Pre-28 baseline | True | False | False | (n/a — нет matcher) |
| **B.** Post-30 stack | True | True | True | True |

Метрики: `ref_hit@1, @5, @10, @20`, `MRR`. Breakdown по `language`
(en / ru / pli) и по `difficulty` (если разметка есть).

## Decision rule

- **B.ref_hit@5 ≥ 0.50** → cut `v0.2.0`. Чёткий quality lift, можно
  релизить.
- **B.ref_hit@5 ∈ [0.45, 0.50)** → marginal — копать в breakdown:
  если выиграли русские, фиксируем как Russian-coverage release.
- **B.ref_hit@5 < 0.45** → регрессия. Diagnose worst cases, фикс,
  re-run. Не релизим.

## Как работает (без изменений в проде)

```
Golden v0.0_extended (100 QA)
        │
        ├──► Cell A: только pali expansion (как было до rag-day-28)
        │       │
        │       ▼
        │   hybrid_search(query, expand_parents=True)
        │       │
        │       ▼
        │   ref_hit@5 [A]
        │
        └──► Cell B: full stack (post-rag-day-30)
                │
                ├──► definitional rewrite → encoded_query
                ├──► pali glossary expansion → encoded_query
                ├──► foundational.match(query) → boost_callable
                ├──► foundational.bm25_aliases(query) → bm25_query
                │
                ▼
            hybrid_search(
              query=encoded_query,
              bm25_query=bm25_query,
              apply_post_fusion_boost=boost_callable,
              expand_parents=True,
            )
                │
                ▼
            ref_hit@5 [B]
```

Никакого нового кода в проде — `RAGService.query()` уже делает всё
это. Eval-скрипту нужно лишь mirror'ить ту же логику в обход
FastAPI-endpoint'а.

## Что добавляем в код

1. **`src/eval/runner.run_eval`** получает два опциональных параметра:
   `foundational_matcher: FoundationalMatcher | None` и
   `expand_definitional: bool = False`. Когда оба заданы — функция
   зеркалит логику `RAGService.query()` (definitional → Pāli →
   encode + bm25_query + boost).
2. **`scripts/eval_rag_day_32.py`** — скрипт-runner: грузит golden,
   прогоняет 2 ячейки, рендерит markdown-отчёт.
3. **`docs/EVAL_RAG_DAY_32.md`** — итоговый отчёт со cell-A vs
   cell-B сравнением, breakdown по language, decision-call.

## Что НЕ делаем

- **Не меняем production-defaults.** Они уже True (post-rag-day-28).
- **Не запускаем 8-cell ablation.** Это был rag-day-22; повтор не нужен.
- **Не варим reranker-cell.** rerank=False остаётся production-default
  (rag-day-17 paradox), мерить с reranker'ом — отдельный sweep.
- **Не делаем sensitivity-sweep boost-фактора.** Отложено до
  отдельного дня (если cell B недотянет до 0.50).

## GPU

Требуется dev-GPU (encoder для 100 запросов, оба cell'а). Wallclock
~30 секунд (rerank=False, encoder cached after first batch). Нужно
освободить от Whisper.

## Где в коде

| Файл | Что |
|---|---|
| `src/eval/runner.py` | +2 параметра в `run_eval` (foundational + definitional) |
| `src/eval/__init__.py` | re-export нового surface'а если требуется |
| `scripts/eval_rag_day_32.py` | новый — runner с 2-cell loop |
| `docs/EVAL_RAG_DAY_32.md` | итоговый отчёт |
| `docs/concepts/INDEX.md` | строка 32 |
| `CHANGELOG.md` / `STATUS.md` | стандартная запись |

## Связанные документы

- [docs/concepts/22 — golden v0.0_extended + ablation](../EVAL_ABLATION_v0.0e.md) — baseline 0.450
- [docs/concepts/28 — Definitional + foundational](28-definitional-expansion.md)
- [docs/concepts/29 — BM25 translation bridge](29-bm25-translation-bridge.md)
- [docs/concepts/30 — Russian foundational expansion](30-russian-foundational-expansion.md)
