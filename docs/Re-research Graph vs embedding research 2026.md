Ты затронул три очень практичных проблемы, которые часто упускают в теоретических сравнениях. Разберу каждую.

---

## Проблема 1: Один Qdrant — одна модель

Ты абсолютно прав. Вот конкретная ситуация:

```
Qdrant collection "dharma_v1":
  - 900,000 чанков
  - Embedded с BGE-M3 (1024 dim)
  - Хранит dense + sparse vectors

Хочешь попробовать Qwen3-Embedding-4B (1024 dim)?
  → Нужно re-embed ВСЕ 900K чанков
  → Даже если dim совпадает — пространства НЕСОВМЕСТИМЫ
  → BGE-M3 вектор [0.23, -0.15, ...] ≠ Qwen3 вектор [0.23, -0.15, ...]
  → Это РАЗНЫЕ координатные системы
```

Это как если бы два картографа нарисовали карту одного города, но один использовал проекцию Меркатора, а другой — азимутальную. Координаты (0.5, 0.3) указывают на разные точки.

### Варианты решения

**Вариант A: Несколько коллекций в Qdrant (сейчас так)**

```
Qdrant:
  ├── dharma_bge_m3        (900K × 1024 dim, ~3.5 GB)
  ├── dharma_qwen3_4b      (900K × 1024 dim, ~3.5 GB)
  └── dharma_mitra_e       (900K × 768 dim, ~2.7 GB)
                            ИТОГО: ~10 GB RAM
```

Работает, но жрёт память. На VPS 8GB — не влезет. На 32GB — ок.

**Вариант B: Matryoshka — одна модель, разные размерности**

```
Qwen3-Embedding-4B с Matryoshka:
  ├── dim=1024 → production (полное качество)
  ├── dim=512  → быстрый поиск (95% качества)
  └── dim=256  → mobile/edge (90% качества)
```

Экономит память, но это **одна и та же модель**, не решает проблему выбора.

**Вариант C: Собственная база знаний в Postgres** ← то, что ты предлагаешь

```
Postgres:
  ├── concepts (id, name, pali, english, tradition)
  ├── relations (from_id, to_id, type, source_sutta)
  ├── chunks (id, text, source, teacher, metadata)
  └── chunk_concepts (chunk_id, concept_id, relevance)

Запрос: "jhāna AND teacher=Thanissaro AND tradition=theravada"
  → SQL JOIN, детерминированный, мгновенный
  → Не зависит от embedding модели
  → Можно менять embedding сколько угодно — граф стабилен
```

---

## Проблема 2: Зоопарк квантизаций

Ты правильно заметил — возьмём только Qwen3-Embedding-0.6B:

```
На HuggingFace / Ollama доступны:
  ├── FP32  (2.4 GB, максимальное качество)
  ├── FP16  (1.2 GB, ~99.9% качества)
  ├── BF16  (1.2 GB, ~99.9% качества)
  ├── INT8  (0.6 GB, ~99% качества)
  ├── GGUF Q8_0  (0.65 GB, ~98% качества)
  ├── GGUF Q6_K  (0.5 GB, ~97% качества)
  ├── GGUF Q5_K_M (0.45 GB, ~96% качества)
  ├── GGUF Q4_K_M (0.4 GB, ~94% качества)
  ├── GGUF Q4_0  (0.35 GB, ~92% качества)
  ├── GGUF Q3_K_M (0.3 GB, ~88% качества)
  ├── GGUF Q2_K  (0.25 GB, ~80% качества)
  └── GGUF IQ2_XS (0.2 GB, ~75% качества)
```

Умножь на 3 размера (0.6B, 4B, 8B) — получаешь **36 вариантов** только одной модели.

И **каждый вариант генерирует СВОЁ пространство** — нельзя embed чанки через Q4 а query через Q8.

### Что это значит практически

**Выбрал Q4_K_M → все 900K чанков привязаны к этой квантизации навсегда.**

Хочешь перейти на FP16 "для качества"? → Re-embed всё. Хочешь попробовать другую модель? → Re-embed всё. Вышла новая версия модели? → Re-embed всё.

**Каждое re-embedding = время + деньги + downtime.**

---

## Проблема 3: Postgres как собственная база знаний

Вот где твоя мысль становится по-настоящему сильной. Сравним:

### Qdrant (embedding-зависимый)

```
Данные: 900K векторов
Зависимость: BGE-M3 конкретной версии и квантизации
Смена модели: re-embed всё (~$0.07-5, ~10-60 мин)
Обновление знаний: re-embed изменённые чанки
Структурированный поиск: через payload filters (ограниченно)
Multi-hop: невозможно
Объяснимость: нулевая (cosine similarity)
Резервная копия: snapshot Qdrant (~5-10 GB)
```

### Postgres (собственная база знаний)

```
Данные: таблицы с явными связями
Зависимость: нет (SQL стандарт)
Смена "модели": данные не меняются (!)
Обновление знаний: INSERT/UPDATE конкретной записи
Структурированный поиск: полная мощь SQL
Multi-hop: JOIN через таблицы связей
Объяснимость: полная (каждая связь видима)
Резервная копия: pg_dump (~500 MB)
```

### Гибрид: Postgres + pgvector

Postgres с расширением **pgvector** может хранить и вектора, и граф в одной базе:

sql

```sql
-- Таблица чанков с текстом И вектором
CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    source_id VARCHAR(100),
    teacher VARCHAR(200),
    sutta_ref VARCHAR(50),
    tradition VARCHAR(50),
    language VARCHAR(10),
    embedding vector(1024),  -- pgvector
    created_at TIMESTAMP DEFAULT NOW()
);

-- Таблица концепций (граф)
CREATE TABLE concepts (
    id VARCHAR(100) PRIMARY KEY,
    label VARCHAR(200),
    pali VARCHAR(200),
    english VARCHAR(500),
    tradition VARCHAR(50),
    category VARCHAR(100)
);

-- Связи между концепциями
CREATE TABLE concept_relations (
    from_concept VARCHAR(100) REFERENCES concepts(id),
    to_concept VARCHAR(100) REFERENCES concepts(id),
    relation_type VARCHAR(100),  -- "is_type_of", "leads_to", "factor_of"
    source_sutta VARCHAR(50),
    confidence FLOAT DEFAULT 1.0,
    PRIMARY KEY (from_concept, to_concept, relation_type)
);

-- Связь чанков с концепциями
CREATE TABLE chunk_concepts (
    chunk_id INTEGER REFERENCES chunks(id),
    concept_id VARCHAR(100) REFERENCES concepts(id),
    relevance FLOAT,
    PRIMARY KEY (chunk_id, concept_id)
);

-- Гибридный запрос: semantic + structured
SELECT c.text, c.source_id, c.teacher,
       1 - (c.embedding <=> query_vec) AS similarity
FROM chunks c
JOIN chunk_concepts cc ON c.id = cc.chunk_id
JOIN concepts con ON cc.concept_id = con.id
WHERE con.id = 'jhana'
  AND c.tradition = 'theravada'
  AND c.teacher = 'Thanissaro Bhikkhu'
ORDER BY similarity DESC
LIMIT 10;
```

**Что ты получаешь:**

- Semantic search через pgvector (как Qdrant)
- Structured search через SQL (невозможно в Qdrant)
- Graph traversal через JOINs (невозможно в Qdrant)
- **Одна база данных** вместо Qdrant + Neo4j
- Полный контроль, полная прозрачность

---

## Postgres + pgvector vs Qdrant: честное сравнение

|Критерий|Qdrant|Postgres + pgvector|
|---|---|---|
|**Semantic search скорость**|⭐⭐⭐⭐⭐ (HNSW, оптимизирован)|⭐⭐⭐⭐ (HNSW, чуть медленнее)|
|**На 1M векторов**|2-5 мс|5-15 мс|
|**Structured queries**|⭐⭐ (payload filters)|⭐⭐⭐⭐⭐ (SQL)|
|**Graph/JOIN**|❌|⭐⭐⭐⭐⭐|
|**Sparse vectors**|⭐⭐⭐⭐⭐ (нативно)|❌ (нужен отдельный FTS)|
|**Full-text search**|❌|⭐⭐⭐⭐ (tsvector, нативно)|
|**RAM на 1M × 1024 dim**|~1.5-2 GB (scalar quant)|~4-6 GB (без оптимизации)|
|**Резервное копирование**|Snapshot (сложнее)|pg_dump (стандарт)|
|**Ecosystem**|Специализированный|Огромный (любой ORM, любой язык)|
|**Уже в docker-compose**|✅|✅ (langfuse-db уже Postgres!)|
|**Независимость от модели**|❌ привязан к embedding dim|❌ тоже привязан, НО граф не привязан|
|**Сложность setup**|Проще (один сервис)|Чуть сложнее (схема + миграции)|

### Ключевое отличие

**Qdrant** — чисто векторная БД. Отличная для одной задачи (similarity search), но ВСЁ остальное нужно делать снаружи.

**Postgres + pgvector** — универсальная БД, которая **ещё и** умеет в вектора. Плюс графы, полнотекстовый поиск, ACID транзакции, стандартный SQL.

---

## Архитектурный вопрос: а нужен ли вообще Qdrant?

У тебя **уже есть Postgres** в docker-compose (для Langfuse). Можно использовать тот же Postgres для всего:

### Вариант "Всё в Postgres"

```
docker-compose.yml:
  postgres:        # ОДНА база для всего
    ├── langfuse schema    (observability)
    ├── dharma schema      (chunks + embeddings через pgvector)
    └── knowledge schema   (concepts + relations)
```

**Плюсы:**

- Один сервис вместо двух (Qdrant + Postgres)
- Меньше RAM (~4 GB vs 2+4 GB)
- Одна технология для backup, monitoring, scaling
- Полный контроль через SQL
- Граф и вектора в одном месте → JOIN между ними

**Минусы:**

- pgvector чуть медленнее Qdrant на чистом vector search (5-15 мс vs 2-5 мс)
- Нет нативных sparse vectors (нужен tsvector + ts_rank для BM25-like)
- Нет ColBERT late interaction (Qdrant поддерживает)
- Меньше специализированных фич (scalar quantization, ACORN filtering)

### Вариант "Qdrant для скорости + Postgres для графа"

```
docker-compose.yml:
  qdrant:          # быстрый vector search
  postgres:        # граф знаний + Langfuse + structured data
```

**Плюсы:**

- Лучшая скорость vector search
- Нативные sparse vectors и ColBERT
- Граф в Postgres — полный контроль

**Минусы:**

- Два сервиса вместо одного
- Больше RAM
- Нужно синхронизировать данные между ними

---

## Моя обновлённая рекомендация

### Для Phase 1 (сейчас): оставить Qdrant как есть

Почему: Qdrant уже настроен, документация под него, BGE-M3 hybrid (dense+sparse) работает нативно. Переход на Postgres + pgvector потребует ~неделю работы и не даст преимуществ на 56K чанках.

### Для Phase 2 (месяц 3): добавить граф в Postgres

```
Qdrant:   vectors (embedding search)
Postgres: concepts + relations + chunk_concepts (граф знаний)
```

Это тот самый "прагматический гибрид" — embedding для fuzzy semantic search, граф для structured/multi-hop.

### Для Phase 3 (месяц 6+): оценить миграцию на "всё в Postgres"

К этому моменту будет понятно:

- Насколько критична скорость Qdrant (5 мс vs 15 мс)
- Насколько ценен ColBERT (возможно, reranker достаточно)
- Насколько sparse vectors лучше tsvector в Postgres

Если Qdrant не даёт значительных преимуществ — мигрировать на Postgres:

- Один сервис
- Полный контроль
- SQL для всего
- **Embedding модель можно менять** — граф остаётся стабильным

### Главный принцип

**Граф знаний — это КОНСТАНТА проекта. Embedding модель — это ПЕРЕМЕННАЯ.**

```
Граф:     jhāna → leads_to → nibbāna     (это ФАКТ, не меняется)
Embedding: [0.23, -0.15, 0.87, ...]       (это зависит от модели/квантизации)
```

Поэтому **инвестировать время в граф** (200-500 концепций × ручная курация) — это долгосрочная ценность. А embedding модель можно менять хоть каждый месяц — пересчитать вектора стоит копейки.

---

## Практический вывод для тебя

Ты прав в трёх вещах:

1. **Зоопарк квантизаций** — реальная проблема. Решение: выбрать одну квантизацию, зафиксировать, менять только при значительном улучшении. Для BGE-M3 на CPU — FP16 или INT8 оптимально.
2. **Qdrant привязывает к модели** — тоже верно. Решение: граф в Postgres не привязан ни к какой модели, это чистые факты.
3. **Собственный граф в Postgres** — правильная стратегия на перспективу. Полный контроль, полная прозрачность, никакого чёрного ящика.

**Начинаем с embedding (быстро, дёшево), но с самого начала проектируем с мыслью о графе.** Phase 2 — YAML-граф концепций. Phase 3 — возможно полная миграция на Postgres + pgvector.

Оба документа (`EMBEDDING_MODELS_RESEARCH` и `GRAPH_VS_EMBEDDING_RESEARCH`) положи в `docs/` репозитория — это обоснование архитектурных решений на год вперёд.

Хочешь, чтобы я проработал конкретную SQL-схему для буддийского графа знаний в Postgres?