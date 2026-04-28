# 09 — Eval и golden set

## Что это

**Eval** (evaluation) — автоматизированный прогон поисковика по
**заранее размеченному набору вопросов** (golden set), чтобы узнать
числом «насколько хорошо работает». Без eval мы можем **только
догадываться**, лучше ли стало после очередной правки.

**Golden set** — список пар «вопрос → ожидаемые отрывки». Это **наша
правда о том, что считается правильным ответом**.

```yaml
- query: "What is mindfulness of breathing?"
  expected_works: ["mn118"]               # эталон
```

## Зачем у нас

После day-13 (reranker), day-16 (Contextual Retrieval), day-18
(parent expansion) и других улучшений **нам нужно знать** — стало ли
лучше, или мы внесли регрессию. Без числовой метрики это **слепая
вера**.

## Уровни golden

| Версия | Кто разметил | Авторитет | Использование |
|---|---|---|---|
| **v0.0 synthetic** | Claude, по канонической базе | ❌ | Itерации pipeline (наш текущий) |
| **v0.1 buddhologist** | Буддолог, 30 QA | ✅ | Day-14 baseline eval |
| **v0.2 fine-tune** | Буддолог, 150 QA + reasoning | ✅ | Phase 2 fine-tuning BGE-M3 |

## Synthetic golden объяснён

**Синтетический** = не размечен авторитетом, сгенерирован из
**канонически известных фактов**.

Я знаю:
- MN 118 = Anāpānassati Sutta = «дыхательная медитация» — это есть в
  любом буддийском справочнике
- SN 56.11 = Dhammacakkappavattana Sutta = «первая проповедь Будды»
- DN 22 = Mahāsatipaṭṭhāna Sutta = «большое о сатипаттхане»
- DN 16 = Mahāparinibbāna Sutta = «о паринирване Будды»

Из этого знания я генерирую 30 пар «очевидный вопрос → канонически
правильная сутта». Полный файл: `docs/eval/golden_v0.0_synthetic.yaml`.

**Что synthetic golden может:**
- Быть unit-test'ом для pipeline («reranker не сломал retrieval?»)
- Дать **относительные метрики** между версиями pipeline
- Служить смоук-тестом

**Чего synthetic golden не может:**
- Быть **авторитетным** ответом «Dharma-RAG отвечает с точностью X%»
- Покрыть **тонкие** догматические различия (Theravāda vs Mahāyāna,
  abhidhamma термины, монашеские правила)
- Выявить ошибки **межсуттных** связей (когда правильный ответ — синтез
  3 сутт)

Поэтому файл помечен `# SYNTHETIC — NOT AUTHORITATIVE`.

## Метрики

### ref_hit@K (recall at K)

«Попала ли правильная сутта в top-K результатов?»

```
для каждого (query, expected_works) в golden:
  hits = retrieve(query, top_k=K)
  если хотя бы один из hits.work_canonical_id ∈ expected_works:
    score = 1
  иначе: score = 0

ref_hit@K = mean(score) по всему golden
```

| K | Использование |
|---|---|
| **ref_hit@1** | Самая строгая. «Правильная сутта первая?» |
| **ref_hit@5** | Оперативная. «В top-5?» (главная метрика плана) |
| **ref_hit@20** | Для recall перед reranker'ом |

### MRR (Mean Reciprocal Rank)

«Насколько высоко правильная сутта в результатах?»

```
если правильная сутта на позиции 1: 1.0
если на 2: 0.5
если на 3: 0.33
...
если её нет в top-K: 0

MRR = mean(reciprocal_rank) по всему golden
```

MRR > ref_hit@5 потому что учитывает, **где именно** в топе.

### Будущие метрики (после генерации, day 22+)

- **Faithfulness** — насколько ответ LLM соответствует переданным ему
  отрывкам (не галлюцинирует ли)
- **Citation validity** — правильно ли LLM указал segment_id в цитате
- **Answer relevance** — насколько ответ отвечает на вопрос (не уходит
  в сторону)

Это вычисляется через Ragas (Python lib), который под капотом использует
LLM-judge — другую LLM для оценки качества ответа.

## Относительные метрики

Допустим, на synthetic golden:

| Версия pipeline | ref_hit@5 | MRR |
|---|---|---|
| **v1** (только dense, day 10) | 60% | 0.45 |
| **v2** (+ sparse + BM25, day 12) | 73% | 0.58 |
| **v3** (+ reranker, day 13) | **81%** | **0.71** |
| **v4** (+ Contextual Retrieval, day 16) | **88%** | **0.79** |

**Сами числа** (60%, 73%, 81%) на synthetic golden **не авторитетны**
— могут быть и завышены, и занижены. Но **их разница** валидна:
**reranker дал +8 pp**, **Contextual Retrieval ещё +7 pp**. Это
относительная метрика — **достаточная для решения**, оставлять ли
компонент.

Когда буддолог переразметит golden (v0.1) — все числа сместятся, **но
разница между версиями останется**. Это позволит тоже проверять.

## Roadmap eval

| День | Что делаем |
|---|---|
| **Сегодня** | Создаём `golden_v0.0_synthetic.yaml` (30 QA) |
| **Day 14** | Первый Ragas eval baseline. Метрика-цель: `ref_hit@5 ≥ 60%` |
| **Day 17** | A/B v1 vs v2 (с/без Contextual Retrieval). Цель: +15-30 pp |
| **Когда буддолог** | Replace v0.0 → v0.1 authoritative. Запустить весь eval pipeline ещё раз. |
| **Phase 2 fine-tune** | Buddhologist v0.2 (150 QA) → fine-tune BGE-M3 |

## Где это в проекте

- Synthetic golden: [docs/eval/golden_v0.0_synthetic.yaml](../eval/golden_v0.0_synthetic.yaml) (создан в этом PR)
- Eval скрипт: пока нет, появится на day-14: `scripts/eval_retrieval.py`
- Ragas integration: появится на day-14
- Результаты baseline: появятся в `docs/EVAL_BASELINE.md` после day-14
