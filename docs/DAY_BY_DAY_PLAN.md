# Dharma RAG — План реализации по дням (от А до Я)

> **Этот документ — пошаговая инструкция реализации проекта.** Каждый день имеет конкретные задачи, ожидаемые артефакты и критерии готовности. Соло-разработчик, ~4-6 часов работы в день.

**Условные обозначения:**
- 🎯 **Цель дня** — что должно быть готово к концу
- 📦 **Артефакты** — конкретные файлы/коммиты
- ✅ **Критерий готовности** — как понять, что день закрыт
- ⏱️ **Время** — оценка часов
- 🚧 **Блокеры** — что может помешать

---

## ОБЗОР ФАЗ

| Фаза | Длительность | Цель | Бюджет |
|------|--------------|------|--------|
| **0. Setup** | Дни 1-3 | Окружение + репозиторий | $0 |
| **1. Foundation** | Дни 4-14 | Eval framework + Qdrant + базовый retrieval | $30 |
| **2. Quality** | Дни 15-28 | Hybrid search + Contextual Retrieval + reranking | $80 |
| **3. Generation** | Дни 29-42 | Claude integration + RAG pipeline + CLI | $40 |
| **4. Web MVP** | Дни 43-56 | FastAPI + HTMX + первый деплой | $50 |
| **5. Telegram bot** | Дни 57-63 | aiogram bot + тесты | $20 |
| **6. Transcription** | Дни 64-90 | Транскрипция корпуса Dharmaseed | $1500 |
| **7. Mobile** | Месяцы 4-5 | SvelteKit + Capacitor | $200 |
| **8. Voice MVP** | Месяцы 5-6 | Pipecat + Deepgram + ElevenLabs | $300 |
| **9. Voice Production** | Месяцы 6-9 | LiveKit + on-device + meditation features | $500 |
| **10. Advanced** | Месяцы 9-12 | LightRAG + curriculum + scale | $1000 |

---

# ФАЗА 0: SETUP (Дни 1-3)

## День 1: GitHub репозиторий и базовая структура

🎯 **Цель:** Публичный (или приватный) репозиторий с базовой структурой и документацией.

⏱️ **Время:** 3-4 часа

### Задачи:

1. **Создать GitHub репозиторий** (30 мин)
   - Имя: `dharma-rag`
   - Описание: "Open-source multilingual RAG for Buddhist contemplative teachings"
   - Лицензия: MIT
   - Видимость: private (изменим на public позже)
   - Добавить .gitignore (Python)

2. **Клонировать локально и инициализировать** (30 мин)
   ```bash
   cd ~/projects
   git clone git@github.com:toneruseman/dharma-rag.git
   cd dharma-rag
   ```

3. **Скопировать сгенерированные документы** в репозиторий (1 час)
   - Все файлы из `/mnt/user-data/outputs/dharma-rag/`
   - Перенести существующие наработки из `Q:\dharmaseed\` (если есть)

4. **Создать ветку для разработки** (10 мин)
   ```bash
   git checkout -b dev
   git push -u origin dev
   ```

5. **Настроить branch protection** на GitHub (20 мин)
   - main: require PR review (для соло — required status checks)
   - Запретить force push на main

6. **Первый коммит и push** (30 мин)
   ```bash
   git add .
   git commit -m "Initial commit: project structure and documentation"
   git push origin dev
   ```

📦 **Артефакты:**
- Репозиторий с README, LICENSE, .gitignore, всей документацией
- Ветки main и dev

✅ **Критерий готовности:** README отображается на странице репозитория.

---

## День 2: Локальное окружение разработки

🎯 **Цель:** Работающее Python окружение, Docker, IDE настроен.

⏱️ **Время:** 4-5 часов

### Задачи:

1. **Установить Python 3.11+** (если ещё нет) (30 мин)
   - Windows: используйте miniconda3 или python.org
   - Проверить: `python --version` → 3.11+

2. **Создать виртуальное окружение** (15 мин)
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Mac/Linux
   pip install --upgrade pip
   ```

3. **Установить зависимости** (1 час)
   ```bash
   pip install -e ".[dev]"
   ```
   - Возможны проблемы с torch на Windows — используйте инструкции с pytorch.org

4. **Проверить Docker** (30 мин)
   - Установить Docker Desktop (Windows/Mac) или docker-compose (Linux)
   - Запустить: `docker compose up -d qdrant`
   - Проверить: `curl http://localhost:6333/healthz` → ok

5. **Скопировать .env.example → .env** (10 мин)
   - Получить ANTHROPIC_API_KEY на console.anthropic.com (если ещё нет)
   - Заполнить минимум: ANTHROPIC_API_KEY, QDRANT_URL

6. **Настроить VS Code (или другой IDE)** (1 час)
   - Установить расширения:
     - Python (Microsoft)
     - Pylance
     - Ruff
     - Docker
     - GitLens
     - Markdown All in One
   - Настроить интерпретатор: указать .venv
   - Включить format-on-save с Ruff

7. **Тест: запустить Python и подключиться к Qdrant** (30 мин)
   ```python
   # test_setup.py
   from qdrant_client import QdrantClient
   client = QdrantClient(url="http://localhost:6333")
   print(client.get_collections())
   ```

📦 **Артефакты:**
- Работающий .venv с установленными пакетами
- Запущенный Qdrant в Docker
- Файл .env (НЕ коммитим)

✅ **Критерий готовности:** `python test_setup.py` выводит коллекции (пустой список — это нормально).

🚧 **Возможные блокеры:** torch на Windows может потребовать особой версии CUDA. См. [pytorch.org](https://pytorch.org/get-started/locally/).

---

## День 3: Настройка observability и базовая структура src/

🎯 **Цель:** Langfuse работает, базовый src/ создан.

⏱️ **Время:** 3-4 часа

### Задачи:

1. **Запустить Langfuse локально** (1 час)
   ```bash
   docker compose up -d langfuse-db langfuse
   ```
   - Открыть http://localhost:3000
   - Создать аккаунт (локальный)
   - Создать проект "dharma-rag"
   - Скопировать ключи в .env

2. **Создать структуру src/** (1 час)
   ```
   src/
   ├── __init__.py
   ├── config.py           # настройки через pydantic-settings
   ├── logging.py          # structlog setup
   ├── ingest/
   │   └── __init__.py
   ├── processing/
   │   └── __init__.py
   ├── embeddings/
   │   └── __init__.py
   ├── rag/
   │   └── __init__.py
   ├── api/
   │   └── __init__.py
   └── cli.py
   ```

3. **Реализовать src/config.py** (1 час)
   ```python
   from pydantic_settings import BaseSettings, SettingsConfigDict

   class Settings(BaseSettings):
       model_config = SettingsConfigDict(env_file=".env")
       anthropic_api_key: str
       qdrant_url: str = "http://localhost:6333"
       langfuse_public_key: str | None = None
       # ... все из .env
   ```

4. **Реализовать src/logging.py** (30 мин)
   - structlog с JSON-выводом для prod, цветным для dev

5. **Тестовый Hello World через Claude API** (30 мин)
   ```python
   # scripts/test_claude.py
   from anthropic import Anthropic
   from src.config import Settings

   client = Anthropic(api_key=Settings().anthropic_api_key)
   resp = client.messages.create(
       model="claude-haiku-4-5-20251001",
       max_tokens=100,
       messages=[{"role": "user", "content": "Say hi in Pāli"}]
   )
   print(resp.content[0].text)
   ```

📦 **Артефакты:**
- src/ с базовой структурой
- Работающий Langfuse на localhost:3000
- Тестовый запрос к Claude работает

✅ **Критерий готовности:** Тестовый скрипт выводит ответ Claude на палийском.

---

# ФАЗА 1: FOUNDATION (Дни 4-14)

## День 4: Перенос существующих данных и аудит

🎯 **Цель:** Все 56,684 чанка из старого проекта перенесены в новую структуру.

⏱️ **Время:** 4 часа

### Задачи:

1. **Скопировать data/processed/ из старого проекта** (1 час)
   - Из `Q:\dharmaseed\` или старого dharma-rag репозитория
   - В `~/projects/dharma-rag/data/processed/`
   - Структура: `data/processed/{source}/{lang}.jsonl`

2. **Создать data/raw/ каталог и скопировать сырые данные** (1 час)
   - SuttaCentral, DhammaTalks, Access to Insight и др.
   - Это большие файлы (1.1 GB) — не коммитить в git!

3. **Аудит каждого источника** (1.5 часа)
   - Запустить скрипт scripts/audit_sources.py
   - Подсчитать чанки на источник
   - Проверить корректность метаданных
   - Записать результаты в docs/DATA_AUDIT.md

4. **Создать data/README.md** с инструкциями загрузки (30 мин)
   - Где скачать SuttaCentral bilara-data
   - Где DhammaTalks epubs
   - Где Access to Insight ZIP

📦 **Артефакты:**
- data/ каталог с переданными данными (gitignored)
- docs/DATA_AUDIT.md с аудитом

✅ **Критерий готовности:** Все 56,684 чанка доступны в data/processed/.

---

## День 5: Создание golden eval test set (часть 1)

🎯 **Цель:** 50 первых тестовых вопросов с ответами и канонической атрибуцией.

⏱️ **Время:** 5 часов

### Задачи:

1. **Создать структуру eval** (30 мин)
   ```
   tests/eval/
   ├── test_queries.yaml          # вопросы и ожидаемые источники
   ├── golden_answers.yaml        # эталонные ответы
   └── README.md                  # как пополнять
   ```

2. **Написать первые 50 вопросов** (4 часа)
   - 20 семантических: "What is the nature of suffering?", "Как развить mettā?"
   - 15 лексических: "What does MN 10 say?", "Define satipaṭṭhāna"
   - 10 гибридных: "What does Thanissaro Bhikkhu say about jhāna factors?"
   - 5 кросс-языковых: вопрос на русском про английский корпус

3. **Формат вопроса:**
   ```yaml
   - id: q001
     query: "What is jhāna?"
     language: en
     type: semantic
     expected_sources:
       - sutta: AN 9.36
       - sutta: MN 39
     topics: [jhana, samatha, samadhi]
     difficulty: basic
     golden_answer: |
       Jhāna refers to states of deep meditative absorption...
   ```

📦 **Артефакты:**
- tests/eval/test_queries.yaml — 50 вопросов
- tests/eval/golden_answers.yaml — эталонные ответы

✅ **Критерий готовности:** 50 вопросов структурированы и закоммичены.

---

## День 6: Golden eval test set (часть 2) и Ragas setup

🎯 **Цель:** 100 вопросов всего + работающий Ragas evaluator.

⏱️ **Время:** 4 часа

### Задачи:

1. **Добавить ещё 50 вопросов** (2.5 часа)
   - 15 про конкретных учителей (Ajahn Chah, Thanissaro, etc.)
   - 15 про конкретные практики (mettā, breath, body scan)
   - 10 про работу с препятствиями (5 nīvaraṇa)
   - 10 кросс-традиционных (Тхеравада vs Махаяна терминология)

2. **Установить ragas** (15 мин)
   ```bash
   pip install -e ".[eval]"
   ```

3. **Создать src/eval/runner.py** (1 час)
   - Базовый раннер: загрузить test_queries.yaml, прогнать через retrieval + LLM, вычислить метрики
   - Метрики: ref_hit@5, topic_hit@5, faithfulness, context_precision

4. **Запустить baseline на старом dense-only retrieval** (15 мин)
   - Сохранить результаты в tests/eval/results/baseline_dense_only.json

📦 **Артефакты:**
- 100 вопросов в test_queries.yaml
- src/eval/runner.py
- baseline результаты

✅ **Критерий готовности:** Запуск `python -m src.eval.runner --baseline` выводит метрики.

---

## День 7: Установка Qdrant collection и базовый ingester

🎯 **Цель:** Все 56,684 чанка с dense-векторами BGE-M3 в Qdrant.

⏱️ **Время:** 5 часов

### Задачи:

1. **Создать src/embeddings/model.py** (1.5 часа)
   - Класс EmbeddingModel: загрузка BGE-M3, методы encode_dense, encode_sparse, encode_colbert
   - Использовать FlagEmbedding (BGEM3FlagModel) или sentence-transformers

2. **Создать src/embeddings/store.py** (1.5 часа)
   - Класс QdrantStore: create_collection, upsert_chunks, search
   - Конфиг коллекции: dense vectors (1024 dim, cosine) + sparse vectors + payload schema

3. **Реализовать scripts/build_index.py** (1 час)
   - Читать JSONL → батчами эмбедить → upsert в Qdrant
   - Прогресс-бар через tqdm
   - Чекпойнты для возобновления

4. **Запустить полную индексацию** (1 час, фоновая задача)
   ```bash
   python scripts/build_index.py --collection dharma_v1
   ```
   - 56,684 чанков × 0.05 сек/чанк ≈ 50 минут на CPU
   - Если есть GPU: ~10 минут

📦 **Артефакты:**
- src/embeddings/{model,store}.py
- scripts/build_index.py
- Qdrant коллекция dharma_v1 с 56,684 точками

✅ **Критерий готовности:** `client.count("dharma_v1")` возвращает 56684.

---

## День 8: Базовый retrieval + первая оценка

🎯 **Цель:** Работающий dense retrieval, baseline метрики получены.

⏱️ **Время:** 4 часа

### Задачи:

1. **Создать src/rag/retriever.py** (1.5 часа)
   - Класс DenseRetriever: search(query, top_k) → list of chunks
   - Подключить Langfuse трейсинг

2. **Запустить eval на dense retrieval** (1 час)
   ```bash
   python -m src.eval.runner --retriever dense --output tests/eval/results/dense_v1.json
   ```
   - Записать: ref_hit@5, topic_hit@5 по типам запросов

3. **Анализ результатов** (1 час)
   - Какие запросы провалились?
   - Палийские термины — насколько плохо?
   - Сравнить с baseline (2% ref_hit, 55% topic_hit из старого проекта)

4. **Документировать в docs/EVAL_RESULTS.md** (30 мин)

📦 **Артефакты:**
- src/rag/retriever.py
- tests/eval/results/dense_v1.json
- docs/EVAL_RESULTS.md (первая запись)

✅ **Критерий готовности:** Метрики совпадают с предыдущими ~2% ref_hit@5 (подтверждение проблемы).

---

## День 9-10: Sparse vectors через BGE-M3

🎯 **Цель:** Sparse vectors добавлены в Qdrant, hybrid search работает.

⏱️ **Время:** 8 часов (2 дня)

### День 9 — генерация sparse:

1. **Расширить EmbeddingModel** (2 часа)
   - Метод encode_with_sparse возвращает (dense, sparse_dict)
   - Sparse format: dict {token_id: weight}

2. **Обновить QdrantStore** (1.5 часа)
   - Создать новую коллекцию dharma_v2 с named vectors:
     - "dense": dense vectors
     - "sparse": sparse vectors (Qdrant native format)

3. **Реализовать scripts/build_index_hybrid.py** (1 час)
   - Сгенерировать оба типа векторов одновременно
   - Upsert обоих в новую коллекцию

### День 10 — hybrid retrieval:

4. **Реализовать HybridRetriever** (2 часа)
   - Параллельный поиск по dense и sparse
   - RRF fusion (k=60)
   - Объединить результаты, дедуп по chunk_id

5. **Запустить eval на hybrid** (30 мин)
6. **Сравнить с dense-only** (1 час)
   - Ожидание: hybrid даёт +20-40пп ref_hit@5
   - Если нет — отлаживать sparse vectors

📦 **Артефакты:**
- Коллекция dharma_v2 с hybrid vectors
- src/rag/retriever.py с HybridRetriever
- Новые eval-результаты

✅ **Критерий готовности:** ref_hit@5 на лексических запросах вырос с 0% до >30%.

---

## День 11: BM25 как третий retriever + RRF комбинация

🎯 **Цель:** BM25 работает с палийским токенайзером, hybrid стал триадой.

⏱️ **Время:** 4 часа

### Задачи:

1. **Создать src/rag/bm25.py** (2 часа)
   - rank-bm25 + кастомный токенайзер
   - Палийская нормализация: satipaṭṭhāna ↔ satipatthana

2. **Построить BM25 индекс** (1 час)
   - Индексировать все 56,684 чанка
   - Сохранить как pickle для быстрой загрузки

3. **Обновить HybridRetriever** для трёх sources (1 час)
   - Dense + Sparse + BM25 → RRF
   - Запустить eval

📦 **Артефакты:**
- src/rag/bm25.py
- data/bm25_index.pkl
- Новые eval-результаты с triple hybrid

✅ **Критерий готовности:** ref_hit@5 на лексических запросах >50%.

---

## День 12-13: Reranker (BGE-reranker-v2-m3)

🎯 **Цель:** Reranker внедрён, top-100 → top-10, качество выросло.

⏱️ **Время:** 6 часов

### День 12:

1. **Создать src/rag/reranker.py** (2 часа)
   - Класс CrossEncoderReranker
   - Загрузка BGE-reranker-v2-m3
   - Метод rerank(query, candidates) → reranked top-N

2. **Интеграция в pipeline** (1.5 часа)
   - HybridRetriever возвращает top-100
   - Reranker сужает до top-10
   - Опциональный bypass для быстрых запросов

### День 13:

3. **Eval с reranker** (1 час)
4. **Тюнинг параметров** (1.5 часа)
   - top_k_retrieve: 50/100/200
   - top_k_rerank: 5/10/20
   - Оптимизация по ratio качества/скорости

📦 **Артефакты:**
- src/rag/reranker.py
- Eval-результаты с reranker

✅ **Критерий готовности:** topic_hit@5 вырос на +15пп vs hybrid-only.

---

## День 14: Документация retrieval pipeline

🎯 **Цель:** docs/RAG_PIPELINE.md содержит полное описание текущего стека.

⏱️ **Время:** 3 часа

### Задачи:

1. **Написать docs/RAG_PIPELINE.md** (2 часа)
   - Архитектурная диаграмма
   - Описание каждого компонента
   - Метрики на текущий момент
   - Bash-команды для воспроизведения

2. **Обновить README.md** (30 мин) — отметить прогресс
3. **Создать первый PR в main** (30 мин) — слить изменения из dev

📦 **Артефакты:**
- docs/RAG_PIPELINE.md
- PR dev → main

✅ **Критерий готовности:** Можно с нуля воспроизвести текущий pipeline по документации.

---

# ФАЗА 2: QUALITY (Дни 15-28)

## День 15-16: MITRA-E evaluation

🎯 **Цель:** MITRA-E (Buddhist NLP embedding model) оценена на eval set.

⏱️ **Время:** 6 часов

### День 15:

1. **Скачать MITRA-E** с HuggingFace (1 час)
   - `huggingface-cli download mitra-foundation/mitra-e`
   - Изучить inference API

2. **Создать src/embeddings/mitra.py** (2 часа)
   - Wrapper вокруг MITRA-E с тем же интерфейсом, что EmbeddingModel

### День 16:

3. **Построить параллельный индекс с MITRA-E** (2 часа)
   - Только для палийских/санскритских чанков (subset)

4. **Eval: MITRA vs BGE-M3** (1 час)
   - Особое внимание к запросам с Pāli терминами

📦 **Артефакты:**
- src/embeddings/mitra.py
- docs/EVAL_RESULTS.md обновлён

✅ **Критерий готовности:** Решение принято: MITRA-E как primary для Pāli или нет.

---

## День 17-19: Contextual Retrieval (Anthropic method)

🎯 **Цель:** Все 56,684 чанка имеют LLM-сгенерированный контекст-префикс.

⏱️ **Время:** 12 часов (3 дня)

### День 17 — реализация:

1. **Создать src/processing/contextual.py** (3 часа)
   - Промпт: "Дай 2-3 предложения контекста для этого чанка из <document>"
   - Использует Claude Haiku
   - Prompt caching (cache документа целиком)

2. **Тест на 100 чанках** (1 час)
   - Проверить качество контекстов
   - Замерить стоимость: ожидание ~$0.003/чанк → $170 на весь корпус

### День 18 — массовая обработка:

3. **Batch обработка 56,684 чанков** (4 часа фоновой задачи)
   - Скрипт scripts/add_context.py
   - Async с rate limiting (Anthropic Tier 1: 50 RPM)
   - Чекпойнты, возобновление

### День 19 — переиндексация и eval:

4. **Переиндексировать с контекстами** (2 часа)
   - Новая коллекция dharma_v3
   - Embed: context + chunk text

5. **Eval: с контекстом vs без** (2 часа)
   - Ожидание: -49% до -67% ошибок retrieval

📦 **Артефакты:**
- src/processing/contextual.py
- data/processed/contextualized/
- Коллекция dharma_v3

✅ **Критерий готовности:** ref_hit@5 вырос ещё на +20пп.

---

## День 20-21: Pāli глоссарий и query expansion

🎯 **Цель:** 200+ Pāli терминов с переводами и синонимами, query expansion работает.

⏱️ **Время:** 8 часов

### День 20:

1. **Составить глоссарий** (4 часа)
   - 200 ключевых Pāli терминов
   - Для каждого: основное написание, варианты романизации, английский перевод, синонимы
   - Источник: PED (Pali-English Dictionary), личные знания
   - Формат: data/glossary/pali.yaml

### День 21:

2. **Создать src/rag/query_expansion.py** (2 часа)
   - Если запрос содержит Pāli термин — добавить синонимы и перевод
   - Если на русском — нормализовать терминологию

3. **Eval с expansion** (1 час)
4. **Документировать в docs/PALI_HANDLING.md** (1 час)

📦 **Артефакты:**
- data/glossary/pali.yaml (200+ терминов)
- src/rag/query_expansion.py

✅ **Критерий готовности:** Запросы про Pāli термины показывают +10пп точности.

---

## День 22-24: Семантический кеш

🎯 **Цель:** 40-60% cache hit rate на типичных запросах.

⏱️ **Время:** 10 часов

### День 22:

1. **Создать src/cache/semantic_cache.py** (3 часа)
   - Отдельная Qdrant коллекция `cache`
   - Хранит: query_embedding, query_text, response, retrieved_chunk_ids, timestamp
   - Lookup: cosine similarity > 0.92

### День 23:

2. **Интеграция в RAG pipeline** (2 часа)
   - Pre-retrieve check: есть ли в кеше?
   - Post-generate: сохранить в кеш

3. **TTL и инвалидация** (2 часа)
   - 30 дней по умолчанию
   - Команда `dharma-rag cache clear`

### День 24:

4. **Тест и тюнинг** (3 часа)
   - Прогнать 200 синтетических вариаций 50 базовых запросов
   - Замерить hit rate
   - Настроить порог similarity

📦 **Артефакты:**
- src/cache/semantic_cache.py
- Коллекция cache

✅ **Критерий готовности:** Hit rate >40% на синтетических вариациях.

---

## День 25-26: Parent-child chunking refinement

🎯 **Цель:** Чанкинг переработан с учётом дискурсивности дхарма-текстов.

⏱️ **Время:** 8 часов

### День 25:

1. **Анализ текущего чанкинга** (2 часа)
   - Где обрезаются концепции?
   - Какой средний размер контекста нужен?

2. **Реализация parent-child** (2 часа)
   - Children: 150 слов для embedding
   - Parents: 600 слов возвращаются как контекст

### День 26:

3. **Переиндексация с parent-child** (2 часа)
4. **Eval** (2 часа)
   - Ожидание: faithfulness ↑, context_precision ↓ (нормально)

📦 **Артефакты:**
- src/processing/chunker.py обновлён
- Новая коллекция dharma_v4

✅ **Критерий готовности:** faithfulness >0.85.

---

## День 27-28: Финальный eval Phase 2

🎯 **Цель:** Полный отчёт о retrieval quality после Phase 2.

⏱️ **Время:** 6 часов

1. **Прогнать все 100 запросов через финальный pipeline** (1 час)
2. **Сравнить с baseline** (1 час)
3. **Написать docs/PHASE2_RESULTS.md** (3 часа)
4. **PR в main** (1 час)

📦 **Артефакты:**
- docs/PHASE2_RESULTS.md
- Релиз tag v0.2.0

✅ **Критерий готовности:** ref_hit@5 >70%, topic_hit@5 >85%.

---

# ФАЗА 3: GENERATION (Дни 29-42)

## День 29-30: System prompts и prompt engineering

🎯 **Цель:** Базовый system prompt для Claude генерирует ответы с цитатами.

⏱️ **Время:** 8 часов

### День 29:

1. **Создать src/rag/prompts.py** (3 часа)
   - System prompt: роль, инструкции по цитированию, поведение при незнании
   - Few-shot examples: 3-5 примеров хороших ответов

2. **Тест на 10 запросах** (1 час) — итерация промпта

### День 30:

3. **Кросс-языковые промпты** (2 часа)
   - Запрос на русском → ответ на русском
   - Сохранение Pāli терминов в оригинале

4. **Версионирование промптов в Langfuse** (1 час)
5. **Документация в docs/PROMPTS.md** (1 час)

📦 **Артефакты:**
- src/rag/prompts.py
- docs/PROMPTS.md

---

## День 31-32: Generator + streaming

🎯 **Цель:** Claude генерирует ответы со streaming, цитаты автоматически проверяются.

⏱️ **Время:** 8 часов

### День 31:

1. **src/rag/generator.py** (3 часа)
   - Класс ResponseGenerator
   - generate_streaming(query, contexts) → AsyncIterator[str]
   - Langfuse трейсинг

2. **Тест streaming в CLI** (1 час)

### День 32:

3. **src/rag/citations.py** (3 часа)
   - Парсинг цитат из ответа Claude (формат [source: SN 56.11])
   - Верификация: цитата существует в context?
   - Деграждейшн при ошибке цитирования

4. **Тест на eval set** (1 час)

📦 **Артефакты:**
- src/rag/{generator,citations}.py

---

## День 33-34: LLM Routing (Haiku/Sonnet/Opus)

🎯 **Цель:** Простые запросы идут на Haiku, сложные на Sonnet/Opus.

⏱️ **Время:** 6 часов

### День 33:

1. **src/rag/router.py** (3 часа)
   - Классификатор сложности через Claude Haiku
   - Routing rules: простая фактология → Haiku, требует синтеза → Sonnet, философские/мульти-аспектные → Opus

### День 34:

2. **Eval costs vs quality** (2 часа)
   - Прогнать 100 запросов через router
   - Замерить cost/req и quality
   - Цель: avg ~$0.014/req

3. **Документация** (1 час)

📦 **Артефакты:**
- src/rag/router.py
- docs/COST_MODEL.md

---

## День 35-36: Pipeline integration + CLI

🎯 **Цель:** `dharma-rag query "What is jhāna?"` работает end-to-end.

⏱️ **Время:** 8 часов

### День 35:

1. **src/rag/pipeline.py** (3 часа) — оркестратор
   - Полный flow: query → cache → router → retriever → reranker → generator → cite
   - Async, streaming

2. **src/cli.py** (2 часа)
   - Команды: query, ingest, eval, cache, version

### День 36:

3. **End-to-end тесты** (2 часа)
4. **Полировка UX** (1 час)

📦 **Артефакты:**
- src/rag/pipeline.py
- src/cli.py
- `pip install -e .` → команда `dharma-rag` доступна глобально

✅ **Критерий готовности:** `dharma-rag query "What is jhāna?"` выводит обоснованный ответ с цитатами.

---

## День 37-39: Тестирование и edge cases

🎯 **Цель:** Покрытие тестами >70%, edge cases обработаны.

⏱️ **Время:** 12 часов

### День 37 — unit tests:

1. **tests/unit/** (4 часа)
   - test_chunker.py
   - test_retriever.py
   - test_reranker.py
   - test_cache.py

### День 38 — integration tests:

2. **tests/integration/** (3 часа)
   - test_pipeline_e2e.py с моками внешних API

### День 39 — edge cases:

3. **Обработка ошибок** (3 часа)
   - Empty query, нерелевантный запрос, multilingual混合
   - Rate limiting, API failures
   - LiteLLM fallback chain

4. **CI на GitHub Actions** (2 часа)
   - .github/workflows/test.yml — pytest, ruff, mypy

📦 **Артефакты:**
- Полный тестовый набор
- CI pipeline

---

## День 40-42: Документация и v0.3.0 релиз

🎯 **Цель:** v0.3.0 опубликован, документация полная.

⏱️ **Время:** 9 часов

### День 40:

1. **docs/ARCHITECTURE.md финал** (3 часа)
   - Обновлённые диаграммы
   - Финальный стек

### День 41:

2. **docs/COOKBOOK.md** (3 часа)
   - Примеры использования через CLI
   - Примеры программных вызовов

### День 42:

3. **CHANGELOG.md, RELEASE_NOTES** (1 час)
4. **Релиз v0.3.0** (1 час)
5. **Обзор фазы и планирование Phase 4** (1 час)

📦 **Артефакты:**
- v0.3.0 tag
- Полная документация

---

# ФАЗА 4: WEB MVP (Дни 43-56)

## День 43-44: FastAPI app skeleton

🎯 **Цель:** FastAPI работает с базовыми endpoints.

⏱️ **Время:** 8 часов

### День 43:

1. **src/api/app.py** (2 часа)
   - FastAPI app с middleware (CORS, logging, langfuse)

2. **src/api/routes.py** (2 часа)
   - POST /api/query → JSON ответ
   - GET /api/health → health check
   - GET /api/sources → список источников

### День 44:

3. **POST /api/query/stream → SSE** (2 часа)
4. **Pydantic schemas** (1 час)
5. **OpenAPI документация** (1 час) — авто из FastAPI

📦 **Артефакты:**
- src/api/{app,routes,schemas}.py
- http://localhost:8000/docs работает

---

## День 45-47: HTMX frontend

🎯 **Цель:** Веб-чат с streaming работает в браузере.

⏱️ **Время:** 12 часов

### День 45:

1. **frontend/templates/index.html** (3 часа)
   - HTMX + Tailwind (CDN)
   - Чат-интерфейс: текст-поле, история сообщений
   - SSE streaming через `hx-ext="sse"`

### День 46:

2. **frontend/static/css/style.css** (2 часа) — кастомные стили
3. **frontend/templates/components/** (2 часа)
   - chat_message.html
   - source_citation.html

### День 47:

4. **Jinja2 интеграция в FastAPI** (2 часа)
5. **Тест в браузере** (1 час)
6. **Мобильная адаптивность** (2 часа)

📦 **Артефакты:**
- frontend/ полностью
- Веб-чат работает на http://localhost:8000

---

## День 48-49: Полировка UX

🎯 **Цель:** Чат красивый, удобный, с источниками.

⏱️ **Время:** 8 часов

1. **Подсветка цитат** (2 часа)
2. **Раскрываемые блоки источников** (2 часа)
3. **История сессии (без БД, в localStorage)** (2 часа)
4. **Темная/светлая тема** (1 час)
5. **Loading states, error handling** (1 час)

📦 **Артефакты:**
- Полировка UI

---

## День 50-52: Деплой на VPS (Hetzner)

🎯 **Цель:** Публичный URL, HTTPS, мониторинг.

⏱️ **Время:** 12 часов

### День 50:

1. **Заказать Hetzner CX32** (1 час)
   - €9/мес, 4 vCPU, 8GB RAM, Ubuntu 24.04

2. **Базовая настройка сервера** (3 часа)
   - SSH ключи
   - UFW firewall
   - fail2ban
   - Docker + docker-compose

### День 51:

3. **Dockerfile для приложения** (2 часа)
4. **docker-compose.prod.yml** (1 час) — отличия от dev
5. **Каталин/CD pipeline** (3 часа)
   - GitHub Actions: build → push image → deploy via SSH

### День 52:

6. **Домен + Cloudflare** (2 часа)
   - Купить домен (например, dharma-rag.org)
   - Настроить DNS на Cloudflare
   - SSL через Caddy reverse proxy

📦 **Артефакты:**
- Публичный URL https://dharma-rag.org
- Auto-deploy при push в main

---

## День 53-55: Production observability

🎯 **Цель:** Метрики, логи, алерты работают.

⏱️ **Время:** 10 часов

### День 53:

1. **Prometheus + Grafana** на VPS (3 часа)
   - Метрики FastAPI: latency, RPS, errors
   - Метрики Qdrant: query latency, collection size

### День 54:

2. **Langfuse production** (2 часа)
   - Перенастроить на cloud Langfuse или self-hosted на этом же VPS

3. **Loki для логов** (2 часа) — опционально

### День 55:

4. **Алерты в Telegram** (2 часа)
   - Через alertmanager или простой скрипт
   - Триггеры: error rate >1%, latency p95 >5s

5. **Документация: docs/DEPLOYMENT.md** (1 час)

📦 **Артефакты:**
- Grafana дашборд
- Алерты работают

---

## День 56: v0.4.0 релиз

🎯 **Цель:** Публичный MVP запущен.

⏱️ **Время:** 4 часа

1. Финальные тесты на production
2. v0.4.0 tag
3. Анонс в README
4. Обновить статус в badges (Pre-Alpha → Alpha)

📦 **Артефакты:**
- v0.4.0 + публичный MVP

---

# ФАЗА 5: TELEGRAM BOT (Дни 57-63)

## День 57-58: aiogram setup

🎯 **Цель:** Бот отвечает на команду /start.

⏱️ **Время:** 8 часов

### День 57:

1. **Создать бота через @BotFather** (30 мин)
2. **src/bot/main.py** (2 часа) — entry point
3. **src/bot/handlers/start.py** (1 час) — /start, /help

### День 58:

4. **Базовый /query handler** (2 часа)
5. **Streaming через edit_message_text** (2 часа)
6. **Запуск в polling режиме** (30 мин)

📦 **Артефакты:**
- src/bot/
- Бот отвечает в Telegram

---

## День 59-60: FSM и медитативные сценарии

🎯 **Цель:** Гайд-флоу для guided practices через FSM.

⏱️ **Время:** 8 часов

### День 59:

1. **FSM для guided meditation** (3 часа)
   - Состояния: choosing_practice → setting_duration → practicing → reflecting
   - Команды: /meditate, /retreat, /lesson

### День 60:

2. **/meditate флоу** (2 часа)
3. **/lesson генератор** (2 часа) — простая версия
4. **Тестирование** (1 час)

📦 **Артефакты:**
- Полноценный бот с командами

---

## День 61-63: Деплой бота + полировка

🎯 **Цель:** Бот работает 24/7 на production.

⏱️ **Время:** 10 часов

1. **Webhook setup** (2 часа) — вместо polling
2. **Деплой как systemd service на VPS** (2 часа)
3. **Rate limiting per user** (2 часа)
4. **Аналитика usage в Langfuse** (1 час)
5. **Документация docs/TELEGRAM_BOT.md** (1 час)
6. **v0.5.0 релиз** (2 часа)

📦 **Артефакты:**
- Production-бот @DharmaRagBot
- v0.5.0

---

# ФАЗА 6: TRANSCRIPTION (Дни 64-90)

## День 64-66: Подготовка к транскрипции

🎯 **Цель:** Готов pipeline для Groq Batch API.

⏱️ **Время:** 12 часов

### День 64:

1. **Получить Groq API key** (30 мин)
2. **Изучить Groq Batch API docs** (2 часа)
3. **Создать src/transcription/groq_batch.py** (2 часа)

### День 65:

4. **Скачать аудио Dharmaseed (если ещё нет)** (фоновая задача)
5. **scripts/prepare_audio.py** (2 часа)
   - Silero VAD pre-processing
   - Нормализация, конверсия

### День 66:

6. **Pāli initial_prompt** (1 час) — финальный список 200 терминов
7. **Тест на 10 файлах** (3 часа)

📦 **Артефакты:**
- src/transcription/
- Тестовые транскрипты

---

## День 67-70: Pilot транскрипция (1000 файлов)

🎯 **Цель:** 1000 транскриптов готовы и оценены.

⏱️ **Время:** 16 часов (фоновые задачи)

### День 67-68:

1. **Запустить batch на 1000 файлов** (фоновая задача)
2. **Параллельно:** разработка post-processing pipeline

### День 69-70:

3. **LLM коррекция Pāli** (3 часа)
4. **Качественная оценка** (2 часа)
   - Сравнить 20 случайных с человеческими транскриптами Hermes Amāra (для Burbea)
5. **Тюнинг параметров** (2 часа)

📦 **Артефакты:**
- 1000 транскриптов
- Метрики качества

---

## День 71-80: Полная транскрипция корпуса

🎯 **Цель:** 35,000 часов транскрибированы.

⏱️ **Время:** 10 дней (в основном фоновое)

1. **Фоновая обработка через Groq Batch** (~7 дней)
2. **Параллельно:** scripts/post_process.py runs
3. **LLM коррекция** (2 дня компьюта, $200-500)
4. **Diarization Q&A talks** (2 дня)
5. **Финальная сегментация** (1 день)

📦 **Артефакты:**
- 47,202 транскриптов
- ~$700-2000 потрачено

---

## День 81-90: Re-ingestion и Phase 1.5 релиз

🎯 **Цель:** Все транскрипты в Qdrant, retrieval работает на расширенном корпусе.

⏱️ **Время:** ~40 часов

### День 81-83: Чанкинг транскриптов

1. **Адаптировать chunker для аудио** (4 часа)
   - Учёт timestamps
   - Сохранение speaker info

2. **Прогнать всё через chunker** (2 дня фоновое)

### День 84-86: Re-embedding

3. **Massive re-embedding** (3 дня фоновое или $50 на cloud GPU)

### День 87-89: Re-ingest в Qdrant

4. **Создать dharma_v5 collection** с расширенными метаданными
5. **Eval на расширенном корпусе** — обновить test_queries новыми

### День 90: v0.6.0 релиз

📦 **Артефакты:**
- Корпус ~900K чанков
- v0.6.0

---

# ФАЗА 7: MOBILE (Месяцы 4-5)

## Недели 1-2 (Месяц 4): SvelteKit миграция

- Установка SvelteKit 2 + Svelte 5
- Перенос HTMX UI на компоненты Svelte
- API client с TypeScript типами
- PWA manifest, service worker

## Недели 3-4 (Месяц 4): Capacitor wrapping

- `npx cap add android`, `npx cap add ios`
- Базовый build → APK / IPA
- @capacitor/microphone, push notifications
- Тестирование на устройствах

## Недели 5-6 (Месяц 5): Mobile-specific features

- Background audio для медитаций
- Offline-кеш частых запросов
- Голосовой ввод (нативный)
- Sherpa-ONNX для on-device STT

## Недели 7-8 (Месяц 5): Релиз в Google Play (alpha)

- Google Play Console аккаунт ($25 разово)
- Internal testing track
- Closed beta с 20 тестировщиками

📦 **Артефакты:** Android APK, iOS требует Apple Developer ($99/год — отложить)

---

# ФАЗА 8: VOICE MVP (Месяцы 5-6)

## Недели 1-2 (Месяц 5-6): Pipecat прототип

- Установка pipecat-ai
- Базовый pipeline: Deepgram Nova-3 → Claude Haiku → ElevenLabs Flash
- WebSocket в FastAPI
- Тест latency end-to-end (цель <1s)

## Недели 3-4 (Месяц 6): RAG injection

- Function calling Claude с retrieve()
- SSML для пауз
- Pāli pronunciation dictionary → IPA
- Цитаты в UI параллельно с голосом

## Недели 5-6 (Месяц 6): Voice UI

- WebRTC браузерный клиент
- Push-to-talk + VAD
- Транскрипция в реальном времени на экране
- Интеграция в SvelteKit

📦 **Артефакты:** Voice MVP, $300 потрачено

---

# ФАЗА 9: VOICE PRODUCTION (Месяцы 6-9)

## Месяц 7: LiveKit Agents migration

- Перенос с Pipecat на LiveKit
- WebRTC infrastructure
- Turn detection model
- Interruption handling

## Месяц 8: Meditation features

- Guided meditation flows
- Ambient audio mixing (Web Audio API)
- Session state tracking
- Adaptive guidance

## Месяц 9: On-device + scale

- Sherpa-ONNX в Capacitor
- Self-hosted Kokoro-82M TTS на VPS с GPU (Hetzner GEX44 €184/мес или Modal on-demand)
- Load testing (1000 concurrent voice users)

📦 **Артефакты:** Production voice chat

---

# ФАЗА 10: ADVANCED (Месяцы 9-12)

## Месяц 10: LightRAG

- Knowledge graph extraction (~$100-500)
- Graph-augmented retrieval
- Visualization (Cytoscape.js)

## Месяц 11: Curriculum & retreat composer

- User profiles + progress tracking
- Spaced repetition algorithm (SM-2)
- Retreat composer agent (Pydantic AI)
- Lesson generator

## Месяц 12: Polish & community

- Public launch
- Documentation site (Astro Starlight)
- Community Discord
- Translation to Spanish, German

📦 **Артефакты:** v1.0.0, public launch

---

# ЕЖЕДНЕВНЫЕ ПРАКТИКИ

## Утренний ритуал (15 мин)
- Проверить алерты с production
- Прочитать issues на GitHub
- План на день — Todoist/Notion

## Вечерний ритуал (15 мин)
- Commit + push (даже WIP в dev branch)
- Заметка в CHANGELOG.md / dev diary
- Отметить прогресс в этом ROADMAP

## Еженедельно (1 час, воскресенье)
- Обзор недели: что сделано, что застряло
- Обновление ROADMAP: пересмотр оценок
- Обзор costs/usage в Anthropic console, Hetzner, Groq
- Backup: проверить, что данные сбэкаплены

## Ежемесячно (2 часа, последняя пятница)
- Обзор фазы: что закрыто, что переносится
- Финансовый отчёт
- Обновление FUTURE_WORK.md
- Реклутинг: ищем ли контрибьюторов?

---

# ВОЗМОЖНЫЕ БЛОКЕРЫ И ИХ РЕШЕНИЯ

| Блокер | Решение |
|--------|---------|
| Anthropic API rate limit | Запросить Tier 2 на console.anthropic.com (требует $40 spend) |
| Qdrant OOM на 8GB VPS | Включить scalar quantization + mmap, или апгрейд на 16GB (+€4/мес) |
| Groq batch API queue | Тайно использовать паралельно несколько ключей |
| Dharmaseed permission | Параллельно запрос → ждать ответ → fallback на CC BY-NC corpus |
| Соло-разработчик уперся | Рекрутинг в r/Buddhism, r/streamentry, Lions Roar community |
| Production downtime | Status page (UptimeRobot бесплатно), резервный VPS у другого провайдера |

---

# КРИТЕРИИ УСПЕХА ПО ФАЗАМ

**Phase 1 MVP (День 56):** публичный URL, бот в Telegram, работает на 90% запросов
**Phase 1.5 (День 90):** полный корпус Dharmaseed transcribed, retrieval >70% ref_hit@5
**Phase 2 (Месяц 5):** мобильное приложение в Google Play (alpha)
**Phase 3 voice (Месяц 9):** voice chat <800ms latency, $0.05/min cost
**v1.0 (Месяц 12):** 1000 active users, 50 contributors, 10K monthly queries

---

# ССЫЛКИ НА СВЯЗАННЫЕ ДОКУМЕНТЫ

- [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) — полный обзор архитектуры с критикой
- [SOURCES_CATALOG.md](SOURCES_CATALOG.md) — каталог источников данных
- [TRANSCRIPTION_PIPELINE.md](TRANSCRIPTION_PIPELINE.md) — детали пайплайна транскрипции
- [RAG_PIPELINE.md](RAG_PIPELINE.md) — детали RAG
- [VOICE_PIPELINE.md](VOICE_PIPELINE.md) — детали voice
- [EVALUATION.md](EVALUATION.md) — методология оценки
- [DEPLOYMENT.md](DEPLOYMENT.md) — деплой
- [PRIVACY.md](PRIVACY.md) — приватность
- [CONTRIBUTING.md](CONTRIBUTING.md) — для контрибьюторов
