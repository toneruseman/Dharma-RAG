# RAG Development Plan

> План разработки **RAG-ядра** Dharma-RAG: от нуля до production-качества.
> Разработка приложений (web UI, mobile, voice pipeline, Telegram bot)
> ведётся в отдельном треке и этим документом не покрывается.

- **Версия плана:** 2026-04-21
- **Связанные документы:**
  - Архитектурные решения: [`docs/decisions/0001-phase1-architecture.md`](decisions/0001-phase1-architecture.md)
  - Полный контекст проекта: [`docs/Dharma-RAG.md`](Dharma-RAG.md)

---

## Оглавление

- [Общая карта фаз](#общая-карта-фаз)
- [Бюджет времени и реалистичность](#бюджет-времени-и-реалистичность)
- [Фаза 0: Подготовка (дни −7 до 0)](#фаза-0-подготовка-дни-7-до-0)
- [Фаза 1: Foundation (дни 1-21)](#фаза-1-foundation-дни-1-21)
- [Фаза 2: Quality Loop (дни 22-45)](#фаза-2-quality-loop-дни-22-45)
- [Фаза 3: Multi-source (дни 46-75)](#фаза-3-multi-source-дни-46-75)
- [Фаза 4: Advanced RAG (дни 76-120+)](#фаза-4-advanced-rag-дни-76-120)
- [Параллельные треки](#параллельные-треки)
- [Критический путь](#критический-путь)
- [Что можно вырезать при нехватке времени](#что-можно-вырезать-при-нехватке-времени)

---

## Общая карта фаз

| Фаза | Дни | Цель | Milestone |
|---|---|---|---|
| **0. Подготовка** | −7 до 0 | Закрыть блокеры до первой строки кода | Готов к старту |
| **1. Foundation** | 1-21 | Работающая RAG на одном источнике | v0.1.0 baseline |
| **2. Quality Loop** | 22-45 | Contextual Retrieval + golden set + FT | v0.2.0 quality RAG |
| **3. Multi-source** | 46-75 | 4-5 источников, cross-lingual поиск | v0.3.0 production corpus |
| **4. Advanced RAG** | 76-120+ | Граф знаний + Dharmaseed + оптимизации | v0.4.0 multi-modal |

---

## Бюджет времени и реалистичность

Запланировано при среднем темпе 5-6 часов работы в день:

- 3 ч/день — поддерживающий режим (eval-прогон, docs, созвон с буддологом)
- 5-6 ч/день — основной режим (одна главная задача дня + тесты + ревью)
- 8 ч/день — focused day для больших фич (не больше 2 подряд)
- 12 ч/день — не планировать, только если «само пошло»

**Итого:** Phase 1-4 = 4-5 месяцев чистой работы. С буферами на выгорание,
отпуск, диагностику буксующих задач — ~6 месяцев.

**Недельный ритм:**
- Пн: focused (8ч), новая фича недели
- Вт-Чт: рабочие (5-6ч), интеграция, тесты, eval
- Пт: лёгкий (3ч), docs, рефакторинг, созвон с буддологом
- Сб-Вс: выходные (или лёгкие по желанию)

---

## Фаза 0: Подготовка (дни −7 до 0)

**Цель:** закрыть нетехнические блокеры до кода. Без этого любой Day 1
заканчивается тупиком.

| День | Задача | Результат |
|---|---|---|
| −7 | Отправить письма 3-5 кандидатам-буддологам с описанием проекта | 1-2 заинтересованных ответа |
| −6 | Созвон 1 час с первым кандидатом: цель, примеры golden-вопросов, рубрика | Принципиальное согласие |
| −5 | Обсудить условия: оплата, режим работы, NDA при необходимости | Договорённость зафиксирована письмом |
| −4 | Буддолог составляет **список 15-20 тем** для первых golden-вопросов | Topics list в Google Docs |
| −3 | Написать ADR-0001: зафиксировать BGE-M3, Qdrant named vectors, 384/2048 chunks, Phoenix, Contextual Retrieval | `docs/decisions/0001-*.md` |
| −2 | YAML-шаблон golden-вопроса + 5-балльная doctrinal rubric + инструкция буддологу | `docs/eval/rubric.md` |
| −1 | Python 3.12 venv, проверить Docker, создать скелет репо | Окружение готово |

**Gate перед Phase 1:**
- ADR-0001 подписан
- Буддолог на связи
- `docker compose up` поднимается без ошибок

---

## Фаза 1: Foundation (дни 1-21)

**Цель:** от нуля до работающей RAG на SuttaCentral с baseline-метриками.

### Неделя 1 — Инфраструктура и первая загрузка данных (дни 1-7)

| День | Что делаем | Зачем | Результат |
|---|---|---|---|
| **1** | `docker-compose.yml` с Qdrant + Postgres + Phoenix. Структура `src/`. Pinned `pyproject.toml`. FastAPI skeleton с `/health`. | Фундамент всей системы | `docker compose up` работает, `/health` → HTTP 200 |
| **2** | Postgres schema: таблицы `work`, `expression`, `instance`, `chunk`, справочники `tradition_t`, `language_t`, `author_t`. Alembic миграции. | FRBR-модель с первого дня, иначе потом переделывать | Пустая БД готова принимать данные |
| **3** | Скачать SuttaCentral Bilara (`git clone suttacentral/bilara-data`). Parser для JSON. Dry-run на 10 записях. | Понять формат до кода ingest | Parser выводит первые 10 записей |
| **4** | Полный ingest SuttaCentral: переводы Sujato (EN) для MN, DN, SN, AN. Metadata: work_id, segment_id, translator, tradition, license=CC0. | Первый реальный корпус в БД | ~12 000 записей в Postgres |
| **5** | **Контрольная точка: golden set v0.1 от буддолога — 30 вопросов в YAML.** Импорт в `tests/eval/golden_v0.yaml`. | Без этого метрики фиктивны | Golden v0.1 в репо |
| **6** | Cleaner: Unicode NFC, HTML strip, Pali диакритика (IAST + ASCII-fold в два поля). Unit-тесты. | Без этого поиск ломается на вариантах написания | 15+ тестов проходят |
| **7** | Структурный chunker: границы sutta/section с fallback 384 токена, 15% overlap. Parent-chunks 1024-2048 токенов. Запрет резать pericopes. | Структурное деление сохраняет смысл | ~15 000 child + ~4 000 parent-chunks в БД |

**Gate конца недели 1:** корпус структурирован, licensing metadata
проставлена, готов к embedding.

### Неделя 2 — Embedding и поиск (дни 8-14)

| День | Что делаем | Зачем | Результат |
|---|---|---|---|
| **8** | FlagEmbedding + BGE-M3. Загрузка модели на GPU. Batched inference на 100 тестовых чанках. | Проверить модель до полного ingest | BGE-M3 выдаёт dense + sparse векторы |
| **9** | **Phoenix observability.** OpenInference интеграция. Каждый шаг логируется. Dashboard на :6006. | Без логов первый баг отладится 5 дней | Трейсы тестовых запросов видны |
| **10** | Qdrant collection `dharma_v1` с **named vectors**: `bge_m3_dense` (1024 dim), `bge_m3_sparse`. Full ingest 15K чанков. FP16. | Named vectors — механизм обратимости | Индекс 15K готов за 10-30 мин |
| **11** | BM25 через Postgres FTS с custom Pali tokenizer (normalize диакритику). Pickle для rank-bm25. | Ловит термины где dense «размазывает» | 10 sanity-запросов осмысленные |
| **12** | Hybrid retrieval через RRF: параллельно dense + sparse + BM25, top-30 каждый, RRF fusion (k=60). Endpoint `/api/retrieve`. | Один метод поиска недостаточен для Pali | 20 кандидатов за <200 мс |
| **13** | BGE-reranker-v2-m3 на GPU. Из top-30 → top-8. Замер latency. | Второй этап отсева улучшает precision | Reranker работает |
| **14** | **Первый полный eval** через Ragas: faithfulness, ref_hit@5, citation_validity на golden v0.1. Результаты в Phoenix. `docs/EVAL_BASELINE.md`. | Baseline от которого меряем всё дальше | Отчёт baseline-метрик |

**Gate конца недели 2:** hybrid retrieval + reranking работают, baseline
известен. Ожидания: ref_hit@5 ≥ 40%, faithfulness ≥ 0.70.

### Неделя 3 — Contextual Retrieval и первый релиз (дни 15-21)

| День | Что делаем | Зачем | Результат |
|---|---|---|---|
| **15** | Prompt-template Claude Haiku под буддийский контекст. Prompt caching. Тест на 50 чанках вручную. | Универсальный prompt даст плохой контекст | Prompt validated |
| **16** | Full re-ingest 15K чанков с contextual-префиксом. Batch через Haiku API с cache. Стоимость ~$5-8. | −49% ошибок retrieval (данные Anthropic) | Collection `dharma_v2` |
| **17** | A/B прогон golden v0.1 на v1 vs v2. | Подтверждаем что улучшение реально | +15-30 pp на ref_hit@5 |
| **18** | Parent-child expansion: при retrieval child → LLM получает parent. | Точный поиск + богатый контекст | Parent expansion работает |
| **19** | Endpoint `POST /api/query`: принимает вопрос, делает retrieval+rerank+parent expansion, возвращает chunks БЕЗ LLM. | RAG-ядро независимо от LLM | Endpoint работает |
| **20** | `docs/ARCHITECTURE.md`, `docs/RAG_PIPELINE.md`. Diagram pipeline. | Solo-проекту без доков через 3 месяца непонятно | Docs обновлены |
| **21** | **v0.1.0 release.** Git tag, release notes. | Фиксируем рабочее состояние | v0.1.0 в git |

**Gate конца Phase 1:** ref_hit@5 ≥ 60%, faithfulness ≥ 0.80 на 30
golden-вопросах. Phoenix показывает трейсы каждого запроса.

---

## Фаза 2: Quality Loop (дни 22-45)

**Цель:** довести качество до production-уровня через расширение golden
set, fine-tuning и Pali glossary.

### Неделя 4 — Расширение golden set и ablation (дни 22-28)

| День | Задача | Результат |
|---|---|---|
| **22-23** | Буддолог пишет 70 новых вопросов (итого 100). Категории: factoid, definitional, citation, multi-hop, comparative, adversarial. Включая русские. | Golden v0.2 (100 QA) |
| **24** | Буддолог оценивает 30 ответов v0.1 по 5-балльной рубрике. Krippendorff α. | Первые doctrinal оценки, α известен |
| **25** | Ablation study: разные конфигурации (with/without Contextual, with/without rerank, разные RRF-веса). | Каждый компонент pipeline вносит вклад |
| **26** | Failure analysis: 10 худших запросов вручную. Категоризация. | `docs/FAILURE_PATTERNS.md` |
| **27-28** | Буфер + CI integration: `make eval` блокирует commit при падении ref_hit@5 >5pp. | Регрессии ловятся автоматически |

### Неделя 5 — Pali glossary и query expansion (дни 29-35)

| День | Задача | Результат |
|---|---|---|
| **29-30** | Импорт PTS Pali-English Dictionary (машиночитаемый). Парсер в YAML: term, variants, translations, category, sutta_refs. | ~1000 терминов в `data/glossary/pali.yaml` |
| **31** | Digital Pali Dictionary (Bodhirasa) для расширения. | Glossary до ~3000 записей |
| **32** | Query expansion pipeline: при запросе проверяем glossary, добавляем варианты написания (*satipaṭṭhāna* → *satipatthana*, *sati-patthana*). | Endpoint учитывает варианты |
| **33** | Regression eval на golden v0.2 с glossary. | +5-10 pp на лексических запросах |
| **34-35** | Буфер + обновление docs. | Документация актуальна |

### Неделя 6 — Fine-tuning BGE-M3 (дни 36-45)

| День | Задача | Результат |
|---|---|---|
| **36** | Training data: (query, positive_chunk) пары из SuttaCentral `parallels.json` — разные переводы одного sutta как positives между собой. | ~2000 triplets |
| **37** | Synthetic generation через Claude Haiku: для каждого чанка 3-5 вопросов. | ~10000 синтетических пар |
| **38** | NV-Retriever hard negatives mining. Margin=0.05 для отсечения false negatives. | Training dataset готов |
| **39-40** | FT BGE-M3 на локальной GPU через sentence-transformers с MultipleNegativesRankingLoss. 2-5 часов. | `bge-m3-dharma-v1` модель |
| **41** | Re-embed SuttaCentral в новый named vector `bge_m3_dense_ft` (не трогая оригинал). | v2 индекс параллельно с v1 |
| **42** | A/B eval: golden v0.2 через `bge_m3_dense` vs `bge_m3_dense_ft`. | Подтверждение или опровержение выигрыша |
| **43** | Если FT выигрывает >5pp — переключить default. Если нет — анализ. | Решение задокументировано |
| **44-45** | **v0.2.0 release.** Release notes, скринкаст метрик до/после. | v0.2.0 в git |

**Gate конца Phase 2:** ref_hit@5 ≥ 70%, faithfulness ≥ 0.85 на 100 QA.
Golden set с Krippendorff α ≥ 0.7. FT BGE-M3 работает или обоснованно
отклонён.

---

## Фаза 3: Multi-source (дни 46-75)

**Цель:** расширить корпус с ~15K до ~100K чанков через 4
дополнительных источника.

### Неделя 7 — Access to Insight (дни 46-52)

| Дни | Задачи |
|---|---|
| **46-47** | Скачать архив ATI. Parser HTML (BeautifulSoup). Извлечение переводов Таниссаро, Бодхи, Ньянапоники с metadata. |
| **48** | Licensing audit каждого переводчика. Consent Ledger entries. |
| **49-50** | Cleaner + structural chunking для ATI. Contextual Retrieval (~$3-5). |
| **51** | Ingest в `dharma_v2` (+25000 чанков). |
| **52** | Regression eval. Cross-source queries: «что Таниссаро говорит о...». |

### Неделя 8 — DhammaTalks.org (дни 53-59)

| Дни | Задачи |
|---|---|
| **53-54** | EPUB parser для книг Таниссаро («Wings to Awakening» и др). License: CC BY-NC. |
| **55** | Structural chunking (книги имеют чёткую структуру). |
| **56-57** | Contextual Retrieval + ingest (+15000-20000 чанков). |
| **58-59** | Cross-source eval. Буддолог добавляет 20 cross-source вопросов. Golden v0.3 (120 QA). |

### Неделя 9 — 84000 subset (дни 60-66)

| Дни | Задачи |
|---|---|
| **60-61** | 84000.co API. Скачать subset Kangyur (~50 переводов). |
| **62** | Лицензия CC BY-NC-ND — строгий review. Использовать с фокусом на non-commercial research. |
| **63** | Wylie transliteration handling для тибетских терминов. |
| **64-65** | Ingest + Contextual Retrieval (+10000-15000 чанков). |
| **66** | Regression eval. Корпус охватывает Theravada + Mahayana. |

### Неделя 10 — Русский канал (дни 67-75)

| Дни | Задачи |
|---|---|
| **67-68** | Скраппинг theravada.ru (переводы SV). Legal clearance. |
| **69** | dhamma.ru (Ajahn Chah, Thanissaro на русском). |
| **70** | Русская нормализация (ё/е, старые правила). |
| **71-72** | Ingest русского корпуса (~5-8K чанков). |
| **73** | Cross-lingual eval: 30 русских вопросов от буддолога. Сравнение: single-index vs translate-query pipeline. |
| **74** | Выбор стратегии по данным (вероятно translate-query выиграет для редких терминов). |
| **75** | **v0.3.0 release.** Корпус ~80-100K чанков. |

**Gate конца Phase 3:** 80-100K чанков. ref_hit@5 ≥ 75% на 150 QA
(включая cross-lingual).

---

## Фаза 4: Advanced RAG (дни 76-120+)

**Цель:** knowledge graph, интеграция Dharmaseed транскриптов,
продвинутые техники.

### Недели 11-12 — Knowledge graph (дни 76-89)

| Дни | Задачи |
|---|---|
| **76-77** | Apache AGE в существующий Postgres. Cypher queries testing. |
| **78-80** | Дизайн графа: 200-500 ключевых концепций (sati, samādhi, jhāna, nibbāna, dukkha...). Ручная курация с буддологом. |
| **81-82** | Типы связей (14 из документа: is_a, part_of, causes, synonym_of, translates_as, taught_by и др). |
| **83-84** | Автоматическое извлечение части связей из SuttaCentral `parallels.json` детерминированно, без LLM. |
| **85-86** | Ltree + closure table для lineages (линии передачи учителей). |
| **87-88** | Graph-enhanced retrieval для multi-hop queries. |
| **89** | A/B eval: граф on/off. Ожидание: выигрыш только на 20% сложных multi-hop queries. |

### Недели 13-15 — Dharmaseed интеграция (дни 90-110)

Зависит от отдельной транскрипционной работы. Если транскрипты готовы —
параллельно:

| Дни | Задачи |
|---|---|
| **90-92** | Licensing review CC BY-NC-ND. Письма учителям за explicit permission. Consent Ledger. |
| **93-95** | Ingest готовых транскриптов (Rob Burbea + Ajahn Sucitto + другие). Special chunking для устной речи (timestamps, длинные смысловые единицы). |
| **96-98** | Teacher metadata table: tradition, lineage, biography. Attribution в chunk metadata. |
| **99-101** | Pericope dedup для повторяющихся формул устных учений. |
| **102-105** | Buddhologist checkpoint: оценка качества для современных учителей. Rubric может расширяться (учитель ≠ канон). |
| **106-110** | Regression eval. Golden set → 300 QA. |

### Недели 16+ — Performance и v0.4.0 (дни 111-120)

| Дни | Задачи |
|---|---|
| **111-113** | Float8 quantization в Qdrant (4× экономия RAM, <0.3% потеря). |
| **114-115** | Scalar INT8 rescore для top-K. Latency профилирование. |
| **116-117** | HyPE (hypothetical questions per chunk) для важных чанков. A/B. |
| **118-119** | Late chunking эксперимент на BGE-M3 (8192 токена контекста). |
| **120** | **v0.4.0 release.** ~150-200K чанков, граф работает, Dharmaseed частично интегрирован. |

**Gate конца Phase 4:** ref_hit@5 ≥ 80%, faithfulness ≥ 0.88. Golden set
300 QA. Граф работает для multi-hop. Корпус ~150-200K.

---

## Параллельные треки

Идут всё время, не мешают основным фазам:

1. **Еженедельный eval в CI.** На каждом merge в main. Блокирует
   регрессии >5pp.
2. **Monthly Buddhologist review.** ~10 часов в месяц: +50 QA в golden
   set, оценка 30 системных ответов.
3. **STATUS.md обновление.** Каждую пятницу 15 минут: что сделано, что
   буксует, что переносится.
4. **Phoenix ежедневный взгляд.** 10 минут на dashboard для аномалий.

---

## Критический путь

Эти 5 точек блокируют всё остальное — при буксовании останавливаемся,
решаем, потом идём дальше:

1. **День 1-2:** Docker Compose + Postgres + Qdrant работают.
2. **День 5:** Golden v0.1 от буддолога — без этого все метрики фиктивны.
3. **День 9:** Phoenix observability — без логов первый баг отладится 5
   дней.
4. **День 14:** Первый baseline eval — от которого меряем всё.
5. **День 15-17:** Contextual Retrieval — обязательный quality-прирост
   (−49% ошибок по данным Anthropic).

---

## Что можно вырезать при нехватке времени

Если к 90-му дню чувствуется усталость:

- **Фаза 4 граф → отложить.** Полезен, но не критичен для Q&A.
- **84000 subset → отложить в Phase 5.** Theravada корпуса достаточно.
- **FT BGE-M3 (дни 36-45) → отложить.** Off-the-shelf уже хорош.
- **Русский канал → минимум.** Только theravada.ru, остальное в Phase 5.

**Минимальный успех:** Фазы 0, 1, половина 2, половина 3 за ~2.5
месяца. Это уже работающий Dharma-RAG на 2 источниках с
quality-метриками.

---

## Связь с Phase 1 текущего состояния

Репозиторий уже содержит коммит «Day 3: Add src/ foundation, config,
logging, CLI, and tests» из предыдущей сессии. Day 1-3 этого плана
соотносятся со сделанным:

- Day 1 (этого плана) — скелет `src/api/app.py`, FastAPI `/health`: **сделано** 2026-04-21.
- Day 2-3 — Postgres schema + Alembic + ingest parser: **в работе**.

Архитектурные решения зафиксированы в
[`docs/decisions/0001-phase1-architecture.md`](decisions/0001-phase1-architecture.md).
Расхождения с устаревшими параметрами в `CLAUDE.md` / `ROADMAP.md`
помечены там же; они подлежат «docs alignment pass» отдельной задачей.
