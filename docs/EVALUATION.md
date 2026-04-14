# Evaluation Methodology

> Как мы оцениваем качество retrieval и generation в Dharma RAG.

---

## Зачем нужна оценка?

Без метрик каждое изменение архитектуры — догадка. Цели evaluation:

1. **Регрессии:** убедиться, что изменения не ломают качество
2. **Сравнение:** объективно выбирать между моделями/конфигами
3. **Доверие:** доказать пользователям, что система работает
4. **Доктринальная безопасность:** не допустить искажения учений

---

## Eval Test Set

### Текущий статус

- **150+ запросов** в `tests/eval/test_queries.yaml`
- Покрытие:
  - 30% семантических ("What is the nature of suffering?")
  - 25% лексических ("Define satipaṭṭhāna", "What does MN 10 say?")
  - 20% гибридных ("What does Thanissaro Bhikkhu say about jhāna?")
  - 15% мультиязычных (русские, испанские)
  - 10% доктринальных (различия Тхеравады/Махаяны)

### Формат запроса

```yaml
- id: q001
  query: "What is jhāna?"
  language: en
  type: semantic   # semantic | lexical | hybrid | doctrinal | multilingual
  difficulty: basic   # basic | intermediate | advanced
  expected_sources:
    - sutta: AN 9.36
      relevance: high
    - sutta: MN 39
      relevance: high
    - source: dhammatalks_org
      author: Thanissaro Bhikkhu
      title: "Wings to Awakening"
      relevance: medium
  expected_topics:
    - jhana
    - samatha
    - samadhi
  expected_terms:
    - jhāna
    - samādhi
  golden_answer: |
    Jhāna refers to states of deep meditative absorption developed
    through samatha (concentration) practice. The Buddha described
    four primary jhānas, each progressively more refined...
  contraindicated:  # вещи, которые НЕ должны появиться в ответе
    - "Hindu"
    - "yoga"
    - "Krishna"
```

### Расширение test set

Цель: **500 запросов к v1.0**.

Источники для пополнения:
- Реальные вопросы из Telegram bot (Phase 1.5+)
- Вопросы из dharma-discussion Reddit
- Вопросы от учителей-консультантов
- Edge cases, обнаруженные при разработке

---

## Метрики

### Retrieval метрики

#### `ref_hit@k`

**Что измеряет:** доля запросов, где хотя бы один из expected_sources попал в top-k retrieved.

**Формула:**
```
ref_hit@k = mean over queries of: 1 if any(expected ∈ retrieved[:k]) else 0
```

**Цели:**
- Phase 1 (день 14): >40%
- Phase 2 (день 28): >70%
- v1.0: >85%

#### `topic_hit@k`

**Что измеряет:** доля запросов, где топик ответа совпадает с expected_topics.

**Формула:**
```
topic_hit@k = mean over queries of: |retrieved_topics ∩ expected_topics| / |expected_topics|
```

#### `mrr` (Mean Reciprocal Rank)

**Что измеряет:** на какой позиции находится первый релевантный документ.

**Формула:**
```
MRR = mean over queries of: 1 / rank_of_first_relevant
```

**Цель:** >0.5 (первый релевантный документ в среднем на 2 позиции)

#### `recall@k`

**Что измеряет:** доля релевантных документов, найденных в top-k.

---

### Generation метрики

#### `faithfulness` (Ragas)

**Что измеряет:** все утверждения в ответе подтверждаются retrieved context.

**Метод:** LLM-as-judge — Claude разбивает ответ на atomic claims, проверяет каждый против context.

**Цели:**
- Phase 1 (день 42): >0.80
- v1.0: >0.92

**Критическая метрика для доктринальной безопасности!**

#### `answer_relevancy`

**Что измеряет:** насколько ответ отвечает именно на вопрос.

**Метод:** LLM генерирует questions из ответа, считается косинусная близость с original query.

#### `context_precision`

**Что измеряет:** доля retrieved chunks, действительно полезных для ответа.

#### `context_recall`

**Что измеряет:** какая доля golden_answer покрыта retrieved context.

---

### Кастомные метрики

#### `doctrinal_accuracy` ⭐

**Самая важная метрика для проекта.**

**Что измеряет:** ответ корректно представляет буддийскую доктрину, не смешивает традиции, не добавляет небуддийских идей.

**Метод:** LLM-as-judge с детальным rubric:

```python
RUBRIC = """
Evaluate answer for doctrinal accuracy on scale 1-5:

5 = Perfectly accurate. Citations match. Tradition properly attributed. No conflation.
4 = Mostly accurate. Minor imprecision (e.g., paraphrase loses nuance).
3 = Partially accurate. Some doctrinal points correct, others vague or borderline.
2 = Significantly inaccurate. Conflates traditions or misrepresents teachings.
1 = Severely inaccurate. False attribution, doctrinal errors, or syncretism.

Check:
- Are Pāli/Sanskrit terms used correctly?
- Is tradition (Theravada/Mahayana/Vajrayana) properly attributed?
- Do citations actually support the claim?
- Are there any non-Buddhist concepts inserted (e.g., "soul", "God")?
- Does it contain contraindicated terms from test_queries?
"""
```

**Цели:**
- Phase 1: >4.0 average
- v1.0: >4.5 average
- НИКАКИХ ответов с оценкой 1 или 2!

#### `citation_validity`

**Что измеряет:** все цитаты [source: SN 56.11] действительно существуют и содержат заявленную информацию.

**Метод:**
1. Парсинг цитат регулярным выражением
2. Поиск в corpus по идентификатору
3. LLM проверка: содержит ли source действительно claim?

**Цель:** >95%

#### `pali_term_accuracy`

**Что измеряет:** Pāli термины использованы правильно (правильное написание с диакритикой, правильное значение).

**Цель:** >90%

---

## Eval pipeline

### Запуск полного eval

```bash
python -m src.eval.runner --config configs/eval_full.yaml
```

### Структура runner

```python
# src/eval/runner.py

class EvalRunner:
    def __init__(self, config: EvalConfig):
        self.queries = load_queries(config.queries_path)
        self.pipeline = build_pipeline(config.pipeline)
        self.metrics = [
            RefHit(k=5),
            TopicHit(k=5),
            MRR(),
            Faithfulness(judge_llm="claude-haiku-4-5"),
            DoctrinalAccuracy(judge_llm="claude-opus-4-6"),
            CitationValidity(),
        ]

    async def run(self) -> EvalResults:
        results = []
        for query in tqdm(self.queries):
            response = await self.pipeline.query(query.text)
            scores = await self.evaluate(query, response)
            results.append(EvalResult(query=query, response=response, scores=scores))
        return EvalResults(results)
```

### Сохранение результатов

```bash
tests/eval/results/
├── 20260120_baseline_dense.json
├── 20260121_dense_v1.json
├── 20260122_hybrid_v1.json
├── 20260128_phase2_final.json
└── ...
```

### Сравнение версий

```bash
python -m src.eval.compare \
    tests/eval/results/20260120_baseline.json \
    tests/eval/results/20260128_phase2_final.json
```

Вывод:
```
Metric              Baseline   Phase2    Δ
─────────────────────────────────────────
ref_hit@5            2.0%     71.3%   +69.3pp
topic_hit@5         55.1%     87.4%   +32.3pp
faithfulness         0.78      0.89    +0.11
doctrinal_acc        3.2       4.4     +1.2
citation_validity   65.2%     94.1%   +28.9pp
```

---

## Continuous evaluation

### CI Integration

`.github/workflows/eval.yml` запускает eval на каждом PR в `dev`:

```yaml
- name: Run eval
  run: |
    python -m src.eval.runner --quick  # 30 queries только
    python -m src.eval.compare baseline.json current.json --threshold 5
```

Если регрессия >5pp по любой метрике — PR блокируется.

### Дашборд

Langfuse автоматически собирает метрики каждого запроса в production:

- p50/p95/p99 latency
- Cost per query
- Error rate
- User feedback (thumbs up/down)

Plus weekly sample of 50 production queries → manual review.

---

## Human evaluation

### Когда нужна

- Перед каждым release
- При спорных автоматических оценках
- Для doctrinal_accuracy на новых типах запросов

### Процесс

1. Sample 30 запросов случайным образом
2. Привлечь 2-3 буддийских практикующих с опытом изучения сутт
3. Каждый оценивает независимо по rubric
4. Расхождения обсуждаются
5. Усреднённая оценка → benchmark для LLM-as-judge

### Платформа

- Phase 1: Google Sheets с rubric
- Phase 2+: Label Studio (open-source) на VPS

---

## Известные ограничения

1. **LLM-as-judge bias:** Claude может favored ответы в стиле Claude. Митигация: использовать разные модели для генерации и оценки.

2. **Test set bias:** 150 запросов — мало. Может не покрывать все edge cases. Митигация: расширять до 500+ к v1.0.

3. **Fragility golden answers:** "правильный" ответ субъективен в дхарма-вопросах. Митигация: фокус на доктринальной безопасности, не на точном совпадении.

4. **Multilingual gap:** мало запросов на русском/испанском. Митигация: пополнение в Phase 2.

5. **Voice eval не покрыт:** в Phase 3 нужны отдельные метрики (latency, audio quality, interruption handling).

---

## Следующие шаги

### Phase 1 (день 14)
- Запустить baseline eval
- Установить пороги регрессии в CI

### Phase 2 (день 28)
- Расширить test set до 200
- Добавить doctrinal_accuracy с opus-4-6
- Human eval baseline

### Phase 3 (месяц 6)
- Voice-specific metrics
- A/B testing инфраструктура

### v1.0
- 500 запросов в test set
- Public eval leaderboard для других RAG систем

---

## Ссылки

- [Ragas Documentation](https://docs.ragas.io)
- [DeepEval Documentation](https://docs.confident-ai.com)
- [LangChain Evaluation](https://python.langchain.com/docs/guides/evaluation/)
- [BEIR Benchmark](https://github.com/beir-cellar/beir) — стандарт для retrieval eval
