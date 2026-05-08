# 26 — Retrieval failure analysis (rag-day-26)

> **Статус:** реализовано в rag-day-26 (2026-05-02). Скрипт
> `scripts/eval_failure_analysis.py` + аналитический документ
> [docs/FAILURE_PATTERNS.md](../FAILURE_PATTERNS.md). Топ-15 худших
> запросов разобраны и категоризованы; recommendations пересмотрели
> приоритет следующих rag-day'ев в пользу cheap wins (chunking-audit,
> Russian/EN glossary expansion) до того как двигаться в multi-source
> ingest.

## Что это за день

**rag-day-26** — это **анализ-день**, не feature. Мы не пишем новый
retrieval, не расширяем golden set, не дообучаем модель. Мы методично
разбираем **10 худших запросов** из `golden_v0.0_extended.yaml` (100 QA)
на текущей production-конфигурации и **категоризируем failure modes** —
типы провалов retrieval'а — чтобы понять, что фиксить дальше **по
приоритету**.

> **failure mode** (тип провала retrieval'а) — устойчивая категория
> запросов, на которых система systematically не работает. Это **не
> один баг**, а **класс** запросов с общими свойствами (например, «все
> запросы с bare-romanized палийским словом», или «все запросы,
> требующие синтеза двух сутт»).

Output этого дня:

1. `docs/FAILURE_PATTERNS.md` — текстовый разбор: список топ-10 worst
   запросов, для каждого категория + объяснение, summary table по
   категориям, recommendations что фиксить в первую очередь.
2. `scripts/eval_failure_analysis.py` — небольшой утилитный скрипт
   (one-off), который читает golden + прогоняет retrieval на проде +
   печатает worst-N запросов вместе с retrieved snippet'ами для
   ручной разметки.

## Зачем

После rag-day-22 production-конфигурация — `dharma_v2 + rerank=False
+ expand_parents=True` — даёт `ref_hit@5 = 0.450` на synthetic golden
v0.0-extended (n=100). Числа из [docs/EVAL_ABLATION_v0.0e.md](../EVAL_ABLATION_v0.0e.md).

> **ref_hit@K** — recall at K. «Попала ли правильная сутта в top-K
> результатов поиска хотя бы один раз?» Если да — score=1, если нет
> — score=0. Усреднение по golden = ref_hit@K. У нас K=5, значит
> ref_hit@5 = доля запросов, для которых эталонная сутта попала
> в топ-5 retrieval'а.

`ref_hit@5 = 0.450` означает: **55% запросов не находят reference
passage в top-5**. Без понимания **какие именно** запросы проваливаются,
любые улучшения retrieval'а превращаются в **slot machine**: «дёргаем
ручку — то reranker, то glossary, то fine-tune — надеемся, что-то
помогает». Это плохой подход к качеству продукта.

> **slot machine** (игровой автомат) — здесь это метафора того, что
> разработчики называют **"random tweaking"**: подкручиваем параметры
> наугад, прогоняем eval, смотрим число, повторяем. Без модели «почему»
> улучшения становятся случайными — иногда повезёт, иногда нет.
> Категоризация failure modes превращает random tweaking в **выбор по
> приоритету ROI**.

Категоризация даёт priority list. Например (гипотетически):

> «32% провалов — это lexical-mismatch (palе bare-romanized vs
> diacritics). Это фиксится Pali glossary v2 (concept 14, частично
> сделан в rag-day-23). 25% — multi-hop, для них glossary не поможет,
> нужен knowledge graph (Phase 4). 18% — adversarial / missing
> context, тут retrieval не виноват, это политика «I don't know».»

Это превращает план дальнейших rag-day'ев в **обоснованный roadmap по
ROI**, а не в абстрактную последовательность из плана.

> **ROI** (return on investment) — отношение ожидаемого выигрыша к
> цене. Здесь: «насколько вырастет ref_hit@5» делённое на «сколько
> часов работы и денег займёт». Категория с большой долей провалов
> + дешёвый фикс → высокий ROI → делаем первым.

Аналогия — **software bug triage**. Когда у проекта 500 открытых
тикетов, опытный maintainer не идёт «по дате». Он группирует:
«security» / «data-loss» / «UX-friction» / «cosmetic», смотрит
**severity × frequency**, и работает по приоритету. Failure analysis
для retrieval — то же самое, только тикеты — это запросы.

## Что мы понимаем под failure mode (с примерами)

В нашем контексте за категории берём:

1. **Pali bare-romanized** — пользователь пишет `satipatthana` (без
   диакритик) вместо `satipaṭṭhāna`. Embedding ловит общий
   «mindfulness» context, но не тянет точную сутту MN 10 / DN 22.
   *Фикс:* Pali glossary v2 (расширение concept 14).
2. **Russian lexical** — «что такое джхана» русским транслитом.
   Корпус английский → embedding промахивается. *Фикс:* кириллический
   слой glossary (уже частично есть после rag-day-23, но coverage
   неполный).
3. **Multi-hop reasoning** — «Связаны ли jhāna и samādhi?» — ответ
   требует синтеза двух pericope'ов из разных сутт. Single-vector
   retrieval по построению не умеет «оба сразу». *Фикс:* knowledge
   graph над corpus (Phase 4) или multi-query retrieval.
4. **Citation lookup** — «Что в SN 56.11?» — нужен **точный
   sutta-index lookup**, а не embedding similarity. Семантический
   поиск может промахнуться, потому что метка `SN 56.11` слабо
   отличает между sutt'ами (везде «SN», «56.11» — короткий числовой
   токен). *Фикс:* отдельный exact-match path по `work_id` перед
   embedding-поиском.
5. **Adversarial trick** — «Что Будда сказал об Иисусе?» — намеренная
   провокация, ответа в корпусе нет. Правильное поведение системы:
   вернуть «no relevant sources», не галлюцинировать. *Фикс:*
   `forbidden_works` уже есть (rag-day-19), нужна better refusal
   policy в `/api/answer`.
6. **Adversarial Pāli** — «что значит nibbāna без аннихиляции?» —
   философский вопрос, retrieval может найти нужные сутты, но
   ответ требует осторожной интерпретации. *Фикс:* prompt v2 для
   answer generation.
7. **Definitional in EN (baseline)** — «what is dukkha?» — обычно
   **работает**. Нужен как контроль: если он стал проваливаться,
   мы что-то сломали в pipeline, не в данных.
8. **Ambiguous reference** — golden пишет `expected_works: ["mn36"]`,
   но контент есть и в MN 36, и в AN 4.123, и в DN 22. Retrieval
   возвращает AN 4.123 — фактически правильный, но не «эталонный»
   по разметке. *Фикс:* буддолог разметит `expected_works` шире
   (B-001 blocker).
9. **Ground truth wrong** — synthetic golden содержит ошибку (
   `expected_works` указывает не на ту сутту). *Фикс:* фиксим
   golden file.

## Методология

Шаги дня:

### Шаг 1 — прогнать retrieval

Прогоняем `run_eval(...)` (из [src/eval/runner.py](../../src/eval/runner.py))
на `golden_v0.0_extended.yaml` в **production-конфиге**:
`collection=dharma_v2`, `rerank=False`, `expand_parents=True`. Для
каждого запроса записываем:

- `ref_rank` — позиция эталонной сутты в результатах retrieval (1, 2,
  3, ..., 100, или `∞` если не нашлась в top-100)
- `retrieved_top_5` — что модель вернула в первой пятёрке (work_id,
  score, snippet первых ~100 символов)

> **ref_rank** — это **место** эталонного work'а в отсортированном
> списке retrieved. `ref_rank=1` = эталон первый (идеально).
> `ref_rank=42` = эталон есть, но глубоко (в top-5 не попал, в top-100
> попал). `ref_rank=∞` = эталон вообще не нашёлся (даже на K=100,
> что плохо — реальный мисс).

### Шаг 2 — отсортировать по worst

Сортируем все 100 QA по `ref_rank` **по убыванию** (`∞` сначала, потом
100, 99, ..., 6). Берём топ-10. Это и есть наши «10 худших запросов».

### Шаг 3 — категоризовать вручную

Для каждого из топ-10 проставляем категорию из списка выше (Pali
bare-romanized / Russian lexical / multi-hop / ... ). Это **manual**
работа — глаза смотрят на запрос, на retrieved top-5, и принимают
решение «почему не нашлось».

Пример решения:

> Query: «что такое джхана» → ref `mn36` ref_rank=∞.
> Retrieved top-5: всё `an4.x` про **right effort**.
> → Категория: **Russian lexical**. Кириллица «джхана» не находит
> английский корпус про jhāna.

### Шаг 4 — кластеризация

Считаем **сколько запросов в каждой категории**. Получаем таблицу:

| Категория | Count (из 10) |
|---|---:|
| Pali bare-romanized | 4 |
| Russian lexical | 2 |
| Multi-hop | 2 |
| Citation lookup | 1 |
| Ground truth wrong | 1 |

(Числа гипотетические — реальное распределение появится после прогона.)

### Шаг 5 — recommendations

Для каждой категории — **что в roadmap'е её фиксит** + **насколько
срочно** (severity × frequency).

Пример:

| Категория | Count | Recommended fix | Priority |
|---|---:|---|---|
| Pali bare-romanized | 4 | Расширить cyrillic.yaml до 500 терминов; проверить покрытие romanized→IAST в `pali.yaml` (concept 14) | **High** (40% провалов, дешёвый фикс) |
| Russian lexical | 2 | Та же расширенная glossary | High (overlap с предыдущим) |
| Multi-hop | 2 | Phase 4 knowledge graph | Low (дорого, deferred) |
| Ground truth wrong | 1 | Чинить golden | One-off |

Это и есть **обоснованный** план следующих rag-day'ев.

## Что мы НЕ делаем в этом дне

- **Не фиксим** найденные баги — только анализ. Фикс — следующий
  rag-day.
- **Не расширяем golden set** — это нужен буддолог (B-001 blocker).
- **Не пишем новую ML-модель** — категоризация чисто manual, на глазах.
- **Не оптимизируем retrieval** — оптимизация будет следующим
  rag-day'ом, выбор которого как раз **зависит** от анализа.
- **Не трогаем production config** — анализируем именно её
  (`dharma_v2 + rerank=False + expand_parents=True`).

## Скрипт `scripts/eval_failure_analysis.py`

One-off helper, ~50–100 строк. Что делает:

```python
# 1. Загрузить golden v0.0_extended.yaml
# 2. Построить retrieval pipeline в prod-конфиге
#    (dharma_v2, rerank=False, expand_parents=True)
# 3. Для каждого QA: retrieve(query, top_k=100), найти ref_rank
# 4. Сортировать QA по ref_rank по убыванию (worst первый)
# 5. Распечатать топ-N (default=10):
#    query, expected, retrieved top-5 (work_id + scores + snippet 100 ch)
# 6. Output идёт в stdout (пользователь сам копирует в FAILURE_PATTERNS.md)
```

> **one-off скрипт** — это утилита, которую запускают **один-два
> раза**, не часть production pipeline. Её не покрывают unit-тестами
> (cost-benefit плохой), не интегрируют в CI. Если придётся
> запускать регулярно — переписать как нормальный модуль с тестами.

Формат output для каждого QA:

```
=== QA #042: "что такое джхана" === ref_rank=∞ (not in top-100)
Reference: mn36 :: "When the body is calmed..."
Retrieved top-5:
  1. an4.78  (0.42) :: "The Blessed One was..."
  2. dn22    (0.38) :: "And what, monks, is right..."
  3. ...
```

Скрипт **не пишет в файл** — только stdout. Пользователь сам копирует
интересные записи в `docs/FAILURE_PATTERNS.md`. Это сознательное
решение: file-output подталкивает к auto-pipeline'у, а нам нужен
именно **manual review** на глазах.

## Тесты

Для скрипта **unit-тесты не пишем** — он one-off, manual analysis,
не production code. Verifyability — через manual review результатов.

Smoke-проверка:

- `scripts/eval_failure_analysis.py --top-n 5` запускается без
  ошибок против golden v0.0e.
- Output формат как описан выше (визуально).

## Как проверить локально

PowerShell single-line с активацией venv (см. memory
`feedback_powershell_terminal.md`):

```
.venv\Scripts\python.exe scripts/eval_failure_analysis.py --golden docs/eval/golden_v0.0_extended.yaml --top-n 10 > tmp/failure_analysis_raw.txt
```

Затем вручную:

1. Открыть `tmp/failure_analysis_raw.txt`.
2. Для каждой записи добавить **категорию** + **объяснение**.
3. Перенести в `docs/FAILURE_PATTERNS.md` со структурой:
   - header «Failure analysis на golden v0.0_extended (n=100)»
   - топ-10 записей с категориями
   - summary table «категория | count | recommended fix | priority»
   - recommendations: «следующие rag-day'и в порядке ROI».

> **GPU-нужда:** да. BGE-M3 на GPU для embedding'а 100 запросов.
> Прогон ~1–2 минуты при свободной GTX 1080 Ti, ~5 минут под
> Whisper-contention'ом. Сообщить пользователю заранее, что нужна
> GPU, см. memory `feedback_gpu_declaration.md`.

## Файлы

| Файл | Тип | Зачем |
|---|---|---|
| [scripts/eval_failure_analysis.py](../../scripts/eval_failure_analysis.py) | новый | one-off helper для извлечения worst-N |
| [docs/FAILURE_PATTERNS.md](../FAILURE_PATTERNS.md) | новый | результат анализа: категории + рекомендации |
| [docs/RAG_DEVELOPMENT_PLAN.md](../RAG_DEVELOPMENT_PLAN.md) | возможно изменён | если анализ перетряхнёт приоритет дней 27+ |
| [docs/STATUS.md](../STATUS.md) | обновлён | `rag-day-26` → ✅ Done после merge'а |

## Связанные документы

- [09 — Eval и golden set](09-eval-and-golden-set.md) — про golden
  set, ref_hit@K, MRR
- [docs/EVAL_ABLATION_v0.0e.md](../EVAL_ABLATION_v0.0e.md) — текущая
  baseline 8-cell ablation
- [docs/RAG_DEVELOPMENT_PLAN.md](../RAG_DEVELOPMENT_PLAN.md) (Неделя
  4, lines 139–148) — оригинальный план дня 26
- [14 — Pāli глоссарий](14-pali-glossary.md) — concept, который,
  вероятно, окажется главным beneficiary этого анализа (если Pali
  bare-romanized будет топ-категорией)
- следующие rag-day'и (Pali glossary v2 / Russian channel /
  multi-source) — приоритет которых будет переопределён результатом
  анализа

## Открытые вопросы для ревью

1. **Top-N — 10 или больше?** План говорит «10 худших». На n=100
   это 10%. Можно расширить до 20, если категорий получается мало.
2. **Включать ли «успехи»?** Иногда полезно посмотреть на топ-10
   лучших (ref_rank=1 с высоким отрывом) — чтобы понять, **что у
   нас работает**, и не сломать это в попытках починить failures.
   Пока — не включаем, можно добавить во второй итерации.
3. **Что если `ref_rank=∞` в более чем 10 записях?** На текущем
   ref_hit@5=0.450 это вполне возможно — много запросов вообще не
   находят эталон. Тогда top-10 — это произвольный срез из массы
   `∞`, нужно сортировать дополнительно по другому ключу (например,
   по категории golden, чтобы покрыть разные типы вопросов).
