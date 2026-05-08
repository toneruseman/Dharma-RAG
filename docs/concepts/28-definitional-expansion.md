# 28 — Definitional query expansion + foundational mapping (rag-day-28)

> **Статус:** реализовано (rag-day-28 closed 2026-05-08). Закрывает
> recommendations 1+2 из
> [docs/QA040_INVESTIGATION.md](../QA040_INVESTIGATION.md). Код в
> `src/expand/`, curated mapping в `data/glossary/foundational.yaml`,
> 42 unit-теста. Re-eval на golden v0.0e — отдельный rag-day-32.

> **GPU не нужна.** Definitional expansion — это чисто
> текстовый rewrite запроса (regexp + template), foundational mapping —
> YAML-lookup и арифметика над rrf-rank. Encode/embedding в этом дне
> **не меняется** — мы только переписываем входной текст и подкручиваем
> финальный fusion.

## Что это за день

После анализа qa_040 (rag-day-27) у нас на руках конкретный
**root cause** — короткий definitional-запрос «What is satipaṭṭhāna?»
теряет foundational сутры (mn10, dn22) в dense-канале, а derivative
sn47.x их обходят, потому что в них термин повторяется буквально в
каждом фрагменте. Это **systemic** — тот же паттерн воспроизводится на
dukkha (sn56.11), anatta (sn22.59) и других «канонических» терминах.

> **systemic** vs **isolated.** Isolated — баг в одном кейсе, лечится
> точечно. Systemic — класс запросов с одной общей причиной;
> один фикс закрывает много невидимых failure'ов сразу. qa_040 —
> systemic, см. концепт [27 — qa_040 anomaly](27-qa040-anomaly.md).

rag-day-28 — это **первая реализация** двух дешёвых
детерминистических фиксов из этого анализа: **definitional query
expansion** и **curated foundational mapping**. Оба не используют LLM,
оба не требуют переиндексации корпуса (re-ingest), оба добавляются
в pipeline без изменения существующих компонентов.

> **детерминистический** — даёт один и тот же выход на одном и том же
> входе, без рандома и без вызова внешней модели. Противоположность —
> LLM-rewrite, где результат зависит от семплирования. Детерминистический
> rewrite дешевле (нет API-вызова), быстрее (миллисекунды) и
> воспроизводимее на тестах.

> **re-ingest** (переиндексация корпуса) — повторный прогон всех
> 50k+ child-чанков через encoder и заливка в Qdrant. У нас это
> ~6 часов GPU + ~$150 на Contextual Retrieval LLM-этапе. В этом дне
> ничего такого не нужно — мы трогаем только query-side.

## Зачем у нас (конкретная роль)

Две проблемы из QA040_INVESTIGATION, которые мы закрываем:

### Проблема 1 — короткие definitional-запросы (H5)

«What is satipaṭṭhāna?» — это четыре токена. BGE-M3 на коротком
тексте **усредняется к topic-cluster centroid** — точке в семантическом
пространстве, окружённой всеми чанками о satipaṭṭhāna без выделения
главных. В этой ситуации выигрывают чанки с **высокой плотностью
термина** (sn47.x), а большие prose-сутры (mn10/dn22) проигрывают —
у них термин в title и в нескольких ключевых местах, остальной текст
— конкретные практики, дрейфующие по теме.

> **BGE-M3** — наш encoder (модель, превращающая текст в вектор), см.
> концепт [04 — BGE-M3 encoder](04-bge-m3-encoder.md). На длинных
> запросах работает хорошо, на коротких — даёт «расплывающийся» эмбеддинг.

> **encode** — операция «текст → вектор». BGE-M3 принимает строку,
> возвращает 1024-мерный плотный вектор + sparse-словарь токенов с
> весами. У нас encode идёт перед каждым retrieval-запросом.

> **dense vector** — плотный численный вектор фиксированной длины
> (1024 у нас), описывающий «смысл» текста; используется для
> cosine-similarity-поиска в Qdrant. **sparse vector** — разреженный
> «словарь» термов с весами (как BM25, но с learned весами от
> BGE-M3); тоже хранится в Qdrant в отдельном именованном слоте.

**Smoking gun из QA040_INVESTIGATION (Phase A):**

```
"What is satipaṭṭhāna?"           → mn10 на rrf_rank #126, dn22 #89
"What are the four foundations    → mn10 на rrf_rank #1,   dn22 #3
 of mindfulness?"
```

Это один и тот же запрос по смыслу, но второй вариант — длинный gloss
— даёт **идеальный retrieval**. Если автоматически переписать
короткий вариант в длинный **до encode'а** — qa_040 фиксится.

> **gloss** — пояснительная развёртка термина: вместо одного
> непрозрачного слова даётся фраза, описывающая его. «Satipaṭṭhāna»
> → «foundations of mindfulness» — это gloss. У нас уже есть
> Pāli glossary с такими развёртками (концепт
> [14 — Pāli глоссарий](14-pali-glossary.md)) — мы его переиспользуем.

### Проблема 2 — foundational vs derivative bias (H3)

Даже если definitional expansion сработает на satipaṭṭhāna, остаются
случаи где **термин в title не совпадает с фразой запроса**. Пример:

- «What is dukkha?» → ожидаем `sn56.11` (Dhammacakkappavattana — First
  Sermon, базовая сутра по Четырём Благородным Истинам). Но в title
  sn56.11 нет слова «dukkha» — оно только в content. Embedding не
  выделяет sn56.11 среди десятков сутт где dukkha встречается чаще.
- «What is anatta?» → ожидаем `sn22.59` (Anatta-lakkhaṇa). Title на
  Pali, content — описание практики. Та же проблема.

Здесь expansion alone не поможет — embedding всё равно не видит, что
sn56.11 это **корневой текст темы**, а другие сутры — производные.
Нужен **внешний сигнал**: ручной curated mapping `term → [foundational
works]`, который **бустит rrf_rank** этих work'ов в финальной фьюжн-стадии.

> **rrf_rank** — позиция work'а в финальном списке после
> hybrid-fusion'а трёх каналов. Чем меньше число — тем выше work
> в выдаче (rank #1 — самый релевантный).

> **hybrid retrieval** — наш многоканальный поиск: dense + sparse
> + BM25, объединённые через RRF. См. [01 — RAG pipeline
> overview](01-rag-pipeline-overview.md).

> **fusion** — этап объединения трёх ranked-списков от разных каналов
> в один финальный. У нас это RRF.

> **RRF (Reciprocal Rank Fusion)** — алгоритм, который усредняет
> позиции из разных каналов через формулу `score = 1 / (k + rank)`,
> `k=60` у нас по умолчанию. Подробно — концепт
> [07 — RRF hybrid fusion](07-rrf-hybrid-fusion.md).

> **BM25** — классический keyword-ranking алгоритм над Postgres FTS,
> ловит точные совпадения слов. Третий канал в нашем гибриде. См.
> концепт [06 — Postgres FTS / BM25](06-postgres-fts-bm25.md).

> **FTS** (full-text search) — встроенный в Postgres текстовый поиск
> с tsvector/tsquery. Над ним мы строим BM25-канал.

### Аналогии

**Definitional expansion** — как короткий вопрос на экзамене.
Студент видит «Что такое X?» и его инстинкт — растянуть это в полное
определение перед тем как искать в учебнике: «Что такое X? Это
концепт, описывающий... Также называется Y. Раздел учебника —
foundations of X». С такой развёрткой студент **знает**, на какие
ключевые слова смотреть. Encoder ведёт себя так же: чем длиннее и
богаче запрос — тем точнее retrieval.

**Foundational mapping** — как cheat-sheet перед экзаменом: «если
вопрос про карму — открой главу 7. Если про четыре благородные
истины — главу 3». Embedding и BM25 такого знания не имеют — они
видят только текст. А мы как авторы курса знаем: «satipaṭṭhāna в
учебнике — это MN 10 и DN 22, не сборник эпизодов sn47». Этот
ручной список и есть наш cheat-sheet, его и подсовываем в RRF.

## Как работает

### Высокоуровневая диаграмма

```
        user query
             │
             ▼
   ┌──────────────────────┐
   │ expand_query (Pāli)  │  rag-day-23, уже в проде
   │ 14 — pali-glossary   │  «джхана» → «джхана jhāna meditative absorption»
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │ expand_definitional  │  ← НОВОЕ rag-day-28 (recommendation 1)
   │ 28 — этот концепт    │  «What is X?» → длинный gloss
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │  BGE-M3 encode       │
   │  → dense + sparse    │
   └──────────┬───────────┘
              │
   ┌──────────┼──────────────────┐
   ▼          ▼                  ▼
 dense      sparse              BM25 (Postgres FTS)
 (Qdrant)   (Qdrant)            (raw query, не expanded)
   │          │                  │
   └──────────┼──────────────────┘
              ▼
   ┌──────────────────────┐
   │  RRF fusion (k=60)   │  концепт 07
   │  3 канала → 1 ranked │
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │ foundational_boost   │  ← НОВОЕ rag-day-28 (recommendation 2)
   │ 28 — этот концепт    │  если term ∈ mapping → boost rrf_score
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │ optional: rerank     │  deferred (концепт 10) — у нас prod=False
   │         expand_parents│ концепт 12
   └──────────────────────┘
```

Definitional expansion вклинивается **сразу за Pāli expansion'ом** —
до encode'а, чтобы и dense, и sparse каналы получили обогащённый
текст. Foundational boost вклинивается **после RRF**, до опционального
rerank'а — мы не меняем сам fusion, только подкручиваем финальные scores.

### Definitional expansion: что делает

Простой regexp-trigger ловит паттерны:

- `What is X?` / `What are X?`
- `Что такое X?`
- `Define X` / `X meaning` / `X definition`

(точный набор паттернов — на ревью; держим минимальный, false-positive
дороже false-negative).

Если паттерн сработал и `X` короче ~5 токенов — переписываем запрос
по template'у:

```
"What is {term}?"
   ↓
"What is {term}? Discourse on {term}.
 Foundations of {term}. Sutta on {term}."
```

Для русских — параллельно:

```
"Что такое {term}?"
   ↓
"Что такое {term}? Учение о {term}.
 Основы {term}. Сутта о {term}."
```

> **template** — это **shape**, не содержание. Мы не пишем «правильный
> ответ», мы создаём текст, который похож **по форме** на foundational-сутту:
> «Discourse on...», «Foundations of...», «Sutta on...» — это типичные
> формулировки в title и opening sections канонических сутт. Encoder,
> увидев такую форму, тянет к работам, где эта форма реально встречается.

Пример end-to-end (smoking gun из QA040):

| Шаг | Текст |
|---|---|
| Original | «What is satipaṭṭhāna?» |
| После Pāli expansion (rag-day-23) | «What is satipaṭṭhāna? mindfulness foundations of mindfulness» |
| После definitional expansion (rag-day-28) | «What is satipaṭṭhāna? Discourse on satipaṭṭhāna. Foundations of satipaṭṭhāna. Sutta on satipaṭṭhāna. mindfulness foundations of mindfulness» |
| Encode → retrieve → fusion | mn10 на rrf_rank #1, dn22 на #3 (по аналогии с A3 v2 в QA040) |

Важная тонкость: **BM25 канал получает оригинальный (или минимально
расширенный) запрос**, не raw concatenation длинной строки —
иначе BM25-precision проседает на noise-словах в template'е. Это
обсуждаемая точка на ревью; default — давать BM25 raw query, dense+sparse
получают expanded.

### Foundational mapping: что делает

Curated YAML словарь живёт в `data/glossary/foundational.yaml`. Формат
по аналогии с `data/glossary/cyrillic.yaml` (концепт 14).

**Стартовый набор для rag-day-28.** Базируется на курации Sahaya
(см. секцию «Связь с Sahaya» выше) — 12 essential suttas + темы
их топовых гайдов + связи MN 10 «If this landed». На старте ~18
пар; буддолог B-001 потом расширит до 30-50.

```yaml
# data/glossary/foundational.yaml — стартовый набор rag-day-28
# Источник кураторских пар: Sahaya (buddhistcompanion.com, май 2026)
# 12 essential suttas + 14 thematic guides + MN 10 "If this landed"

# === Sahaya 12 essential suttas ===

- term: four noble truths
  aliases: [4 noble truths, dukkha, дуккха, suffering, четыре благородные истины,
            истины о страдании, dhammacakkappavattana, first sermon]
  works: [sn56.11]
  boost: 1.5

- term: two arrows
  aliases: [second arrow, sallatha, two darts, две стрелы, вторая стрела]
  works: [sn36.6]
  boost: 1.5

- term: anatta
  aliases: [non-self, not-self, анатта, не-я, отсутствие я, anatta-lakkhana]
  works: [sn22.59]
  boost: 1.5

- term: dependent origination
  aliases: [paticcasamuppada, paṭiccasamuppāda, патиччасамуппада,
            взаимозависимое возникновение, dependent arising]
  works: [sn12.2]
  boost: 1.5

- term: satipaṭṭhāna
  aliases: [satipatthana, сатипаттхана, mindfulness foundations,
            four foundations of mindfulness, основы внимательности,
            mahasatipatthana]
  works: [mn10, dn22]
  boost: 1.5

- term: anapanasati
  aliases: [ānāpānasati, breath meditation, mindfulness of breathing,
            анапанасати, медитация на дыхании]
  works: [mn118]
  boost: 1.5

- term: balanced effort
  aliases: [right effort, sona, sona sutta, средние усилия, sammā-vāyāma]
  works: [an6.55]
  boost: 1.5

- term: metta
  aliases: [mettā, loving-kindness, метта, доброжелательность,
            karaṇīya-mettā, karaniya metta]
  works: [snp1.8]
  boost: 1.5

- term: analysis of the truths
  aliases: [saccavibhaṅga, saccavibhanga, analysis of the four noble truths,
            анализ истин]
  works: [mn141]
  boost: 1.5

- term: noble eightfold path
  aliases: [eightfold path, восьмеричный путь, magga, ariya aṭṭhaṅgika magga,
            ariyo atthangiko maggo]
  works: [sn45.8]
  boost: 1.5

- term: lay ethics
  aliases: [sigalovada, sigālovāda, лежа жизнь, lay life, householder ethics,
            этика мирянина, advice to sigala]
  works: [dn31]
  boost: 1.5

- term: foam similes
  aliases: [impermanence, anicca, аничча, непостоянство, phena, foam,
            simile of foam]
  works: [sn22.95]
  boost: 1.4

# === Дополнения из Sahaya thematic guides и MN 10 cross-refs ===

- term: vipassana
  aliases: [випассана, insight, prajna, paññā, прозрение]
  works: [mn10, dn22]
  boost: 1.4

- term: jhana
  aliases: [jhāna, джхана, meditative absorption, samādhi-jhāna,
            ниббана, поглощение]
  works: [mn118, an6.55]
  boost: 1.4

- term: right view
  aliases: [sammā-diṭṭhi, sammaditthi, правильное воззрение, mahacattarisaka]
  works: [mn117, mn41, mn9]
  boost: 1.5

- term: kamma
  aliases: [karma, карма, kammavipāka, действие и плод]
  works: [mn135, an6.63]
  boost: 1.4

- term: nibbana
  aliases: [nirvana, ниббана, нирвана, ending of dukkha, освобождение]
  works: [sn43.14, ud8.1, ud8.3]
  boost: 1.4

- term: five precepts
  aliases: [pañca-sīla, panca sila, пять обетов, пять предписаний,
            five training rules]
  works: [an8.39, sn55.7]
  boost: 1.4
```

**Заметки по seed-набору:**

- 12 верхних терминов — **прямо** из Sahaya 12 essentials (мы доверяем
  их курации; они старше нас и публичные).
- 6 нижних — **наши добавки** из частых definitional-кейсов в QA040
  и тематических гайдов Sahaya: vipassanā, jhāna, right view, kamma,
  nibbāna, пять обетов.
- `boost: 1.5` для канонических первоисточников (single foundational
  sutta), `1.4` для дополнений и multi-work случаев — чтобы стартовая
  ритмика не съедала non-definitional queries.
- `aliases` — щедро: латинизация, IAST, кириллица, английские синонимы,
  чтобы regexp matching сработал на разных формулировках запроса.

Полная curation (30-50 пар, валидация буддолога B-001) — backlog'ом.

При query-time:

1. После RRF получаем ranked-список с rrf_score для каждого work.
2. Лукапим query (после Pāli expansion, до definitional) против
   `foundational.yaml` — ищем пересечение `query.lower()` с любым
   `term` или `aliases`.
3. Если match — для каждого work из `works[]` умножаем его rrf_score
   на `boost` (~1.5 default). Это **post-fusion boost**, не
   pre-fusion — мы не вмешиваемся в каналы, только в финальные scores.
4. Пересортировываем — work'и с boost'ом поднимаются в выдаче.

Пример (case dukkha):

| До boost'а | После boost'а |
|---|---|
| 1. mn9   (rrf_score=0.045) | 1. **sn56.11** (0.018 × 1.5 = 0.027) |
| 2. sn35.226 (0.038)        | 2. mn9   (0.045 — без изменений) |
| 3. sn12.43  (0.032)        | 3. sn35.226 (0.038) |
| ...                        | ... |
| 47. **sn56.11** (0.018)    |   |

> **post-fusion boost** — буст применяется **после** объединения
> каналов, не **до**. Если бы мы бустили pre-fusion (например, в
> dense-канале), один канал получил бы непропорциональный вес и
> могли бы пострадать запросы где foundational-сутта **не**
> ожидается. Post-fusion буст безопаснее — он влияет **только
> когда query реально содержит term**.

> **rrf_score** — численная оценка, обратная к rrf_rank. Чем больше
> score, тем выше work. Подробно — концепт 07.

Tunable: `boost=1.5` — это первая итерация; на eval'е смотрим
sensitivity (1.2 / 1.5 / 2.0) и фиксируем по ref_hit@5 на golden.

> **ref_hit@K** — recall at K. Доля запросов, для которых ожидаемая
> сутта попала в top-K выдачи. У нас baseline `ref_hit@5 = 0.450`
> (см. EVAL_ABLATION_v0.0e). Цель rag-day-28 — поднять на +3-5 pp.

### Конфигурация

Оба фикса — feature-flag'и в `Settings`:

- `expand_definitional_default: bool = True` — включён в проде.
- `foundational_boost_default: bool = True` — включён в проде.
- `foundational_boost_factor: float = 1.5` — default boost.

Можно отключить per-request через query-param `expand_definitional=false`
для A/B и debug. Pattern тот же что у `expand_pali` (rag-day-23).

## Связь с Sahaya — что у них, что у нас

Sahaya (buddhistcompanion.com) — самый близкий к нам публичный проект
(buddhist RAG, английский, Theravada-канон, AI-companion с цитатами).
В мае 2026 я посмотрел как они решают definitional-запросы — это
полезный образец, потому что они старше нас и уже выкатили решение
в прод.

**Их подход — на уровне продукта, не retrieval.** Когда заходишь
в их chat, тебе предлагают практико-ориентированные запросы:
«I'm feeling restless in meditation», «How do I work with anger?» —
не «What is satipaṭṭhāna». Definitional-вопросы у них обработаны
**заранее, руками**, через три механизма:

1. **Список «12 essential suttas»** — навигация в меню. Каждая
   сутра с темой: SN 56.11 → Four Noble Truths, MN 10 → Mindfulness
   Foundations, SN 22.59 → Non-Self, и т.д. Пользователь сразу
   находит «корневую» сутру по теме без обращения к AI.
2. **Тематические гайды** (`/guides`) — отдельные написанные статьи
   на главные темы: «Four Noble Truths», «Mindfulness», «Karma в
   простом языке», «Impermanence», «Dependent Origination».
   Это не retrieval, это статический контент.
3. **«If this landed, read next»** на каждой странице сутты — ручной
   список похожих сутт. Например на MN 10 → MN 118, SN 47.10, MN 119,
   **DN 22 (расширенная версия)**. Это в точности наш foundational
   mapping, но реализованный как UI-виджет, не как retrieval-boost.

**Что это значит для нашего дня.** Их подход хорош для **просмотра**
(открыл сутту — увидел связи), наш — для **свободного поиска**
(написал любой вопрос → получил ответ с цитатами). Подходы
дополняющие, не конкурирующие.

**Практическое следствие: их список 12 сутт + темы тематических
гайдов + связи между суттами — готовый качественный seed для
нашего `foundational.yaml`.** Мы используем его как стартовый
набор на rag-day-28, дальше буддолог (B-001 в backlog'е) валидирует
и расширяет. Это устраняет нашу зависимость от curation — у нас
сразу есть рабочий набор пар «термин → сутта», верифицированный
независимым продуктом.

## Альтернативы (что отвергли)

### LLM-based query rewrite

Подход — отдать query в Claude Haiku или GPT-4o-mini с промптом
«перепиши в полную форму definition-запроса». Дешевле выглядит на
бумаге, но:

- **Latency.** Каждый retrieval-запрос += ~500-1500 ms на API-вызов.
  При SSE-stream'е (концепт 22) пользователь видит первые 1.5
  секунды вообще без сигнала.
- **Стоимость.** ~$0.0003 на запрос на Haiku → при 10k запросов в
  день $3/день, это ~$90/мес. Для donor-funded прод (см. memory
  `BYOK Deferred`) это лишняя статья.
- **Недетерминизм.** На тестах — flaky. Сложнее отлаживать.
- **Privacy.** Каждый запрос уходит в внешний API ещё до retrieval'а.

Шаблонный rewrite — деревянный, но достаточно хороший: A3 в QA040
показал что банальный gloss «What are the four foundations of
mindfulness?» уже даёт #1. Не нужна гибкость LLM, нужна стабильность
template'а.

### RAG-Fusion (multi-query expansion)

Подход — генерировать N (3-5) перефразов запроса через LLM, каждый
прогонять через retrieval, объединять. Используется в LangChain и
LlamaIndex.

Отвергли по тем же причинам: latency × N, стоимость × N, и главное —
у нас **уже есть** multi-channel fusion (RRF над dense/sparse/BM25).
Добавлять ещё один уровень fusion'а поверх — overkill для нашего
объёма (1 query → достаточно одного хорошо переписанного варианта).

### HyDE (Hypothetical Document Embeddings)

Подход — попросить LLM написать **гипотетический ответ** на запрос,
заэмбеддить этот ответ, искать в индексе по нему. Идея — гипотетический
ответ ближе к target-чанкам по эмбеддингу, чем сам запрос.

Отвергли:

- Тоже LLM-call → latency + стоимость + privacy.
- На canonical корпусе hypothetical answer часто **галлюцинирует
  имена сутт** — мы их предсказать не можем без ground truth.
- Detrministic template даёт **тот же эффект формы** дёшево (см.
  smoking gun A3 — без всякого LLM, просто длиннее запрос → mn10 #1).

### Learned sparse / SPLADE

Подход — заменить наш BGE-M3 sparse на learned-sparse модель типа
SPLADE, обученную для definitional retrieval'а.

Отвергли — это **изменение архитектуры**, требующее re-ingest всего
корпуса (~6 часов GPU). Disproportionately дорого для +3-5pp на foundational
queries. Definitional expansion + foundational boost дают тот же
прирост за **0 часов GPU**. Если эти не сработают — тогда вернёмся
к learned-sparse.

### Re-run Contextual Retrieval с новым промптом

Подход — пересгенерировать `context_text` для всех 50k чанков с новым
промптом, который явно отмечает foundational role в meta-контексте
(«this passage is from the foundational sutta on X...»). См.
recommendation #5 в QA040.

Отвергли на rag-day-28 — H1 (CR-prefix drift) была **опровергнута**
анализом. Префиксы корректные, термин уже в них есть. Re-run будет
дорогим (~$150 + 6h compute) фиксом не той причины. Если definitional
expansion и foundational boost дадут меньший прирост чем ожидаем —
тогда вернёмся к этой опции. Не раньше.

### Title-only named vector

Подход — отдельный `bge_m3_title` named vector в Qdrant, embed только
title + title_pali; на definitional queries этот канал даёт сильный
сигнал.

> **named vector** — несколько разных эмбеддингов на одной точке в
> Qdrant под разными именами (у нас сейчас `bge_m3_dense` и
> `bge_m3_sparse`). См. концепт [05 — Qdrant named vectors](05-qdrant-named-vectors.md).

Отвергли на rag-day-28 — это **четвёртый канал** в hybrid pipeline,
требует work-level индексации (а у нас сейчас только chunk-level),
и tuning RRF на 4 каналах. Не бесплатно. Recommendation #5 в QA040
с приоритетом **low** — после того как (1)+(2) выложены и измерены.

### Полностью ручной curated synonym list

Подход — вообще не expand'ить через template, а тащить полные definitions
из ручного словаря: `satipaṭṭhāna → "mn10 mahasatipatthana sutta on the
four foundations of mindfulness anapanasati ..."`.

Отвергли — это уже **не expansion**, а полу-ответ. И требует ручной
работы на 50k+ терминов. Template-expansion даёт 80% эффекта на 1%
усилий.

## Где в коде

| Файл | Тип | Зачем |
|---|---|---|
| `src/expand/__init__.py` | новый | модуль, объединяющий expansion-стратегии |
| `src/expand/definitional.py` | новый | детектор паттернов + template rewrite |
| `src/expand/foundational.py` | новый | YAML-loader + boost-функция |
| `data/glossary/foundational.yaml` | новый | curated mapping (5-10 seed на rag-day-28, до 30-50 на B-001) |
| `src/processing/glossary.py` | изменён | подключение `expand_definitional` после Pāli expansion |
| `src/retrieval/hybrid.py` | изменён | вызов `apply_foundational_boost` после RRF, до rerank |
| `src/config.py` | изменён | три новых Settings: `expand_definitional_default`, `foundational_boost_default`, `foundational_boost_factor` |
| `src/api/query.py` | изменён | новые query-params для override per-request |
| [docs/concepts/14-pali-glossary.md](14-pali-glossary.md) | смежный | Pāli glossary, выполняется ДО definitional expansion |
| [docs/concepts/07-rrf-hybrid-fusion.md](07-rrf-hybrid-fusion.md) | смежный | RRF, ПОСЛЕ которого применяется boost |
| [docs/concepts/27-qa040-anomaly.md](27-qa040-anomaly.md) | предшественник | анализ-день, давший recommendations 1+2 |
| [docs/QA040_INVESTIGATION.md](../QA040_INVESTIGATION.md) | предшественник | сами recommendations |

## Что НЕ делаем в этом дне

- **Не правим BM25 диакритику** — это recommendation #3 из QA040,
  отдельная задача rag-day-29 (technical fix, не related к definitional
  expansion).
- **Не делаем title-only named vector** — recommendation #5, low
  priority, отложено до измерения эффекта (1)+(2).
- **Не re-run'им Contextual Retrieval** — H1 опровергнута, не нужно.
- **Не пишем full curated foundational mapping** — на rag-day-28
  только формат + 5-10 seed-пар для smoke. Full curation (30-50)
  — backlog B-001, требует буддолога.
- **Не меняем encoder, не меняем Qdrant collection, не меняем чанкинг**
  — query-side only.
- **Не делаем LLM-rewrite, RAG-Fusion, HyDE** — см. альтернативы выше.
- **Не trial'им разные значения `boost` на проде** — sensitivity-eval
  на golden v0.0e отдельным шагом перед merge'ом.

## Открытые вопросы для ревью

1. **Какие паттерны ловит regexp definitional-trigger'а?** Минимальный
   set — `What is X`, `What are X`, `Что такое X`, `Define X`, `X
   definition`, `X meaning`. Стоит ли добавить `Tell me about X`,
   `Explain X`, «расскажи о X»? Риск false-positive (длинные
   non-definitional запросы тоже могут содержать «tell me about»).

2. **BM25 канал получает expanded или raw query?** Default — raw, чтобы
   не утопить precision на template-словах. Но возможно стоит давать
   BM25 **частично** expanded — без template'а, но с Pāli expansion.
   Это уже текущее поведение; не меняется.

3. **Foundational boost factor.** Default `1.5` — первая прикидка.
   Eval-sweep `[1.2, 1.5, 2.0, 3.0]` на golden v0.0e — должен
   определить final value. Если 3.0 ломает non-definitional queries
   (сутты с term'ом в title всегда выходят #1) — оставляем 1.5.

4. **Должен ли foundational boost применяться ко всем терминам
   глоссария, или только к тем что в `foundational.yaml`?** Default —
   только к курированным. Расширять автоматически нельзя — теряется
   сигнал «именно эта сутра канонична для термина».

5. **Что делать если у term'а несколько foundational works (mn10 + dn22)
   — бустить оба или только первый?** Default — оба с одинаковым
   boost'ом. Если mn10 ranked выше dn22 в исходной выдаче — оба
   поднимутся, естественный order сохранится.

6. **Логирование в Phoenix.** В трассировке `/api/query` нужны
   spans `expand_definitional` и `foundational_boost` со списком
   matched terms и applied boost'ов — для observability и offline
   debug'а. Это добавляется в этом же дне или отдельным backlog'ом?
   **Default: в этом дне, дёшево.**

## Связанные документы

- [docs/concepts/27 — qa_040 anomaly investigation](27-qa040-anomaly.md)
  — анализ-день, давший root cause и recommendations 1+2
- [docs/QA040_INVESTIGATION.md](../QA040_INVESTIGATION.md) —
  сами recommendations с smoking-gun данными
- [docs/concepts/14 — Pāli глоссарий](14-pali-glossary.md) —
  предшествующий expansion-этап в pipeline
- [docs/concepts/07 — RRF hybrid fusion](07-rrf-hybrid-fusion.md) —
  где применяется foundational boost (после fusion'а)
- [docs/concepts/01 — RAG pipeline overview](01-rag-pipeline-overview.md)
  — общая картина, куда встраиваются оба новых шага
- [docs/EVAL_ABLATION_v0.0e.md](../EVAL_ABLATION_v0.0e.md) —
  baseline `ref_hit@5 = 0.450`, против которого меряем эффект
- [docs/RAG_DEVELOPMENT_PLAN.md](../RAG_DEVELOPMENT_PLAN.md) —
  обновлённый план: rag-day-28 (этот) → rag-day-29 (BM25 диакритика)
  → rag-day-30 (Russian glossary) → rag-day-32 (re-eval)
