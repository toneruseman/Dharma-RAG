# Графовая модель (База знаний) vs Embedding (Чёрный ящик)

> Дополнение к `EMBEDDING_MODELS_RESEARCH_2026.md`
> Фундаментальное сравнение двух парадигм представления знаний для RAG

---

## Суть проблемы

Предыдущее исследование сравнивало **embedding модели между собой** — это как сравнивать марки чёрных ящиков. Но не был задан вопрос: **а нужен ли вообще чёрный ящик?**

Существуют две фундаментально разных парадигмы:

```
ПАРАДИГМА 1: EMBEDDING (Чёрный ящик)
═══════════════════════════════════════
Текст → [Модель 🔒] → Вектор [0.23, -0.15, 0.87, ...]
                           ↓
                     Cosine similarity
                           ↓
                    "Похожие документы"

❓ Почему эти документы похожи? → "Не знаю, модель так решила"
❓ Какие связи между концепциями? → "Не знаю, это вектор"
❓ Что модель считает важным? → "Не знаю, 1024 числа"


ПАРАДИГМА 2: ГРАФ ЗНАНИЙ (Прозрачная модель)
═══════════════════════════════════════════════
Текст → [Экстракция сущностей] → Граф:

    jhāna ──ЯВЛЯЕТСЯ──→ медитативное_поглощение
      │                          │
    ИМЕЕТ_ФАКТОРЫ              ЧАСТЬ
      │                          │
      ├── vitakka (направл.)    samatha_практика
      ├── vicāra (удержание)         │
      ├── pīti (восторг)          ВЕДЁТ_К
      ├── sukha (счастье)            │
      └── ekaggatā (одноточ.)    nibbāna
                                     │
    MN_39 ──ОПИСЫВАЕТ──→ jhāna    ЦИТИРУЕТСЯ_В
    Thanissaro ──ПЕРЕВОДИТ──→ MN_39    AN_9.36

❓ Почему этот документ релевантен? → "Потому что jhāna связана с pīti через ИМЕЕТ_ФАКТОРЫ"
❓ Какие связи между концепциями? → "jhāna → samatha → nibbāna (3 хопа)"
❓ Что модель считает важным? → "Каждая связь явно определена и объяснима"
```

---

## Полное сравнение: 12 критериев

### 1. ПРОЗРАЧНОСТЬ И ОБЪЯСНИМОСТЬ

| Критерий | Embedding (чёрный ящик) | Граф знаний (прозрачная) |
|----------|------------------------|--------------------------|
| Почему этот результат? | "Cosine similarity = 0.87" (бессмысленно для человека) | "jhāna → ОПИСЫВАЕТСЯ_В → MN 39" (понятная цепочка) |
| Можно отладить ошибку? | Практически нет — нельзя "открыть" вектор | Да — можно видеть каждый узел и связь |
| Аудит для доктринальной точности | Невозможен — нет понимания, что модель "знает" | Полный — каждая связь проверяема |
| Доверие пользователей | Низкое — "AI так сказал" | Высокое — "вот цепочка рассуждений" |

**Для Dharma RAG:** доктринальная точность критически важна. Если RAG говорит "jhāna имеет 5 факторов" — в графе видно, откуда это взялось. В embedding — невозможно понять, почему модель вернула конкретный чанк.

### 2. КАЧЕСТВО RETRIEVAL

| Тип запроса | Embedding | Граф | Кто лучше? |
|-------------|-----------|------|------------|
| "What is jhāna?" (семантический) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | **Embedding** — ловит семантику |
| "What does MN 39 say?" (точный) | ⭐⭐ | ⭐⭐⭐⭐⭐ | **Граф** — точный lookup |
| "Связь между jhāna и nibbāna?" (multi-hop) | ⭐⭐ | ⭐⭐⭐⭐⭐ | **Граф** — traversal по связям |
| "Как Thanissaro объясняет pīti?" (teacher+concept) | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | **Граф** — пересечение двух узлов |
| "Похожие учения о работе с гневом" (fuzzy) | ⭐⭐⭐⭐⭐ | ⭐⭐ | **Embedding** — нечёткий поиск |
| "Все практики samatha с описанием" (structured) | ⭐⭐ | ⭐⭐⭐⭐⭐ | **Граф** — структурированный обход |

**Ключевой вывод:** embedding силён на "найди похожее", граф — на "найди связанное". Для дхарма-контента нужно и то, и другое.

### 3. СТОИМОСТЬ ПОСТРОЕНИЯ

| Элемент | Embedding | Граф знаний |
|---------|-----------|-------------|
| Начальные вложения (время) | **2-4 часа** на embedding 56K чанков | **50-200 часов** на построение онтологии + extraction |
| LLM стоимость extraction | $0 (просто embed) | **$50-500** на LLM-экстракцию сущностей из 56K чанков |
| Стоимость 900K чанков | $0-1 (self-hosted BGE-M3) | **$500-5000** на GraphRAG extraction |
| Вручную (человеко-часы) | 0 | **100-500 часов** на курирование онтологии |
| Инфраструктура | Qdrant (уже есть) | + Neo4j/ArangoDB/FalkorDB |
| Поддержка | Автоматическая (re-embed) | Ручная курация + автоматическая extraction |

**Microsoft GraphRAG стоимость:**

```
GraphRAG на 56K чанков:
  Entity extraction: ~$200-500 (Claude/GPT через API)
  Community detection: ~$50-100
  Summarization: ~$100-200
  ИТОГО: $350-800

GraphRAG на 900K чанков:
  ИТОГО: $5,000-15,000 (!!)
```

**LightRAG (альтернатива):**
- В 6000× дешевле GraphRAG
- ~$0.01-0.10 на 56K чанков
- Но качество ниже, особенно на multi-hop

### 4. СКОРОСТЬ RETRIEVAL

| Операция | Embedding (Qdrant) | Граф (Neo4j) |
|----------|-------------------|--------------|
| Простой поиск | **2-10 мс** | 5-50 мс |
| С фильтрацией | **5-20 мс** | 10-100 мс |
| Multi-hop (3 хопа) | Невозможно напрямую | **20-200 мс** |
| Batch 1000 queries | ~500 мс | ~5-50 сек |
| Масштаб 1M docs | Отлично | Зависит от графа |

### 5. МУЛЬТИЯЗЫЧНОСТЬ

| Аспект | Embedding | Граф |
|--------|-----------|------|
| Кросс-языковой retrieval | ✅ Нативно (BGE-M3 ловит "jhāna" ≈ "джхана") | ⚠️ Требует мультиязычную онтологию |
| Новый язык | ✅ Просто re-embed | ❌ Нужно расширять граф |
| Pāli/Sanskrit | ⚠️ Модели знают слабо | ✅ Можно построить точную онтологию |

### 6. ДОМЕННАЯ АДАПТАЦИЯ

| Подход | Embedding | Граф |
|--------|-----------|------|
| Fine-tuning | LoRA на 1000 пар ($50, +10-30%) | N/A (нет модели для тюна) |
| Domain knowledge | Implicit (в весах модели) | **Explicit** (каждый факт видим) |
| Обновление знаний | Re-embed документ | Добавить узел/связь |
| Противоречия | Не обнаруживаются | **Обнаруживаются** (конфликт связей) |

### 7. HALLUCINATION CONTROL

| Аспект | Embedding | Граф |
|--------|-----------|------|
| Могут ли вернуть нерелевантное? | Да — "семантически похоже, но не то" | Редко — связи explicit |
| Проверка фактов | Сложно | Легко — проверить связь в графе |
| Traceability | Есть чанк-источник | Есть полный путь рассуждения |
| False positives | Частые (20-30%) | Редкие (<5%) |

**Для Dharma RAG:** граф мог бы предотвратить смешивание Тхеравады и Махаяны — связь "anattā → Тхеравада" vs "buddha-nature → Махаяна" explicit.

### 8. МАСШТАБИРУЕМОСТЬ

| Масштаб | Embedding | Граф |
|---------|-----------|------|
| 10K docs | Мгновенно | Мгновенно |
| 100K docs | Быстро | Быстро |
| 1M docs | Хорошо (Qdrant оптимизирован) | Зависит от количества связей |
| 10M docs | Отлично | ⚠️ Графы становятся сложными |
| Добавление новых docs | Просто embed и upsert | Нужна extraction → merge в граф |

### 9. СЛОЖНОСТЬ РЕАЛИЗАЦИИ (для соло-разработчика)

| Аспект | Embedding RAG | Graph RAG |
|--------|-------------|-----------|
| Время до MVP | **1-2 недели** | 1-3 месяца |
| Необходимые навыки | Python, векторная БД | + Ontology design, Graph DB, NER |
| Объём кода | ~500-1000 LOC | ~3000-5000 LOC |
| Debugging | Средний | Сложный |
| Documentation/tutorials | Обширная | Ограниченная |
| Библиотеки | sentence-transformers, qdrant-client | neo4j, LightRAG, Microsoft GraphRAG |

### 10. ПРИВАТНОСТЬ

| Аспект | Embedding (self-hosted) | Граф (self-hosted) |
|--------|------------------------|-------------------|
| Данные покидают сервер? | Нет | Нет |
| Что хранится | Вектора (нечитаемы) | Явные факты (читаемы) |
| GDPR compliance | Проще (вектора обезличены) | Сложнее (факты = PII?) |

### 11. ПОДДЕРЖКА И ЭВОЛЮЦИЯ

| Аспект | Embedding | Граф |
|--------|-----------|------|
| Смена модели | Re-embed всё (стоимость) | Граф не меняется |
| Новая версия модели | Нужно перестраивать индекс | Граф стабилен |
| A/B тестирование | Легко (два индекса) | Сложно (один граф) |
| Откат | Вернуть старый индекс | Сложнее |

### 12. СПЕЦИФИЧНОСТЬ ДЛЯ БУДДИЙСКОГО КОНТЕНТА

| Сценарий | Embedding | Граф | Идеал |
|----------|-----------|------|-------|
| "Что такое jhāna?" | ✅ Найдёт релевантные чанки | ✅ Найдёт узел и связи | Оба ок |
| "Чем jhāna в Тхераваде отличается от дзен?" | ⚠️ Может смешать традиции | ✅ Явные связи tradition→concept | **Граф** |
| "Все сутты где упоминается pīti" | ⚠️ Может пропустить | ✅ Точный запрос по связи | **Граф** |
| "Как практика mettā связана с jhāna?" | ⚠️ Семантически далеко | ✅ Traversal mettā→brahmaviharā→samatha→jhāna | **Граф** |
| "Посоветуй практику для беспокойства" | ✅ Семантический матч "anxiety → meditation" | ⚠️ Нужен маппинг "беспокойство → uddhacca-kukkucca" | **Embedding** |
| "Что говорит Аджан Чах о терпении?" | ✅ Если есть чанки Аджана Чаха | ✅ Teacher→works→concepts→khanti | Оба ок |

---

## Три архитектурных подхода

### Подход A: Только Embedding (Vector RAG)

```
Query → Embed → Qdrant → top-K chunks → LLM → Response
```

**Плюсы:** просто, быстро, дёшево, работает из коробки
**Минусы:** чёрный ящик, нет multi-hop, нет структурированных связей
**Стоимость:** $0 (self-hosted)
**Время до MVP:** 1-2 недели
**Подходит:** MVP, Phase 1

### Подход B: Только Граф знаний (Graph RAG)

```
Query → Extract entities → Neo4j traversal → Subgraph → LLM → Response
```

**Плюсы:** прозрачно, точно, multi-hop, объяснимо
**Минусы:** дорого строить, медленно обновлять, сложно масштабировать, плохо с нечёткими запросами
**Стоимость:** $500-5000 (extraction) + инфраструктура
**Время до MVP:** 2-3 месяца
**Подходит:** зрелый продукт с курируемым контентом

### Подход C: Гибрид (Vector + Graph) ⭐ РЕКОМЕНДАЦИЯ

```
Query → [Параллельно]:
  ├── Embed → Qdrant → semantic candidates (top-100)
  └── Extract entities → Graph lookup → structured candidates
       ↓
  Merge + Rerank → top-10 → LLM → Response (с graph-context)
```

**Плюсы:** лучшее из обоих миров — семантика + структура
**Минусы:** сложнее в реализации
**Стоимость:** $0 (Phase 1) + $100-500 (Phase 2 граф)
**Время до MVP:** 2 недели (embedding first) + 2-4 недели (add graph)

---

## Конкретный план для Dharma RAG

### Phase 1 (Дни 1-56): Только Embedding

Используем BGE-M3 hybrid (dense + sparse). Быстрый старт, работающий MVP.

Это НЕ чёрный ящик целиком — у нас есть:
- **Sparse vectors** — видимые лексические веса (какие слова важны)
- **BM25** — детерминированный keyword matching
- **Metadata filtering** — структурированные фильтры (teacher, sutta, tradition)
- **Citation verification** — проверка каждой цитаты

### Phase 2 (Месяц 3-4): Лёгкий граф буддийских концепций

Ручная курация (НЕ автоматическая extraction):

**200-500 ключевых концепций как JSON/YAML:**

```yaml
# data/knowledge_graph/concepts.yaml

concepts:
  - id: jhana
    label: "Jhāna"
    pali: "jhāna"
    sanskrit: "dhyāna"
    english: "meditative absorption"
    tradition: theravada
    category: samatha_practice
    factors:
      - vitakka
      - vicara
      - piti
      - sukha
      - ekaggata
    related:
      - {concept: samadhi, relation: "is_type_of"}
      - {concept: nibbana, relation: "leads_to"}
      - {concept: nivarana, relation: "overcomes"}
    sources:
      - {sutta: "MN 39", relevance: "primary"}
      - {sutta: "AN 9.36", relevance: "primary"}
      - {sutta: "DN 2", relevance: "supporting"}
    teachers:
      - {name: "Thanissaro Bhikkhu", perspective: "hard jhana"}
      - {name: "Leigh Brasington", perspective: "lite jhana"}
      - {name: "Pa Auk Sayadaw", perspective: "traditional"}

  - id: piti
    label: "Pīti"
    pali: "pīti"
    english: "rapture, joy"
    tradition: theravada
    category: jhana_factor
    jhana_level: [1, 2]  # присутствует в 1-й и 2-й джхане
    related:
      - {concept: sukha, relation: "accompanies"}
      - {concept: jhana, relation: "factor_of"}
      - {concept: bojjhanga, relation: "one_of_seven"}
    five_types:
      - khuddaka_piti    # мелкий восторг
      - khanika_piti     # мгновенный
      - okkantika_piti   # волновой
      - ubbega_piti      # поднимающий
      - pharana_piti     # всепроникающий
```

**Стоимость:** $0 (ручная работа, ~40-80 часов)
**Преимущество:** абсолютная доктринальная точность, полный контроль

### Phase 2.5 (Месяц 4-5): LightRAG автоматический граф

Для остального корпуса — автоматическая extraction через LightRAG:

```python
from lightrag import LightRAG

rag = LightRAG(
    working_dir="./lightrag_data",
    llm_model_func=claude_haiku,
    embedding_func=bge_m3_embed,
)

# Инкрементальное добавление документов
for chunk in all_chunks:
    rag.insert(chunk.text)

# Multi-mode retrieval
result = rag.query(
    "How does jhāna relate to nibbāna?",
    param=QueryParam(mode="hybrid")  # naive / local / global / hybrid
)
```

**Стоимость LightRAG vs GraphRAG:**

| Метрика | Microsoft GraphRAG | LightRAG | Разница |
|---------|-------------------|----------|---------|
| Стоимость extraction (56K чанков) | $350-800 | **$0.05-0.10** | 6000× дешевле |
| Стоимость extraction (900K чанков) | $5,000-15,000 | **$0.80-1.50** | 10000× дешевле |
| Качество multi-hop | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | GraphRAG лучше |
| Инкрементальное обновление | ❌ Полный rebuild | ✅ Добавление | LightRAG лучше |
| RAM/GPU requirement | Высокий | Низкий | LightRAG легче |

### Phase 3 (Месяц 6+): Полный гибрид

```
User Query: "Как jhāna связана с просветлением в Тхераваде?"
      │
      ├──→ BGE-M3 Embedding → Qdrant Hybrid Search
      │         → top-100 semantically similar chunks
      │
      ├──→ Entity extraction: [jhāna, просветление, Тхеравада]
      │         → YAML graph lookup:
      │           jhāna → leads_to → nibbāna
      │           jhāna → tradition: theravada
      │           nibbāna ≈ просветление
      │         → Related sutta IDs: [MN 39, AN 9.36, DN 2]
      │
      ├──→ LightRAG graph:
      │         → Local search: jhāna neighborhood
      │         → Global search: "path to enlightenment" theme
      │
      └──→ Merge all candidates
           → Reranker (BGE-reranker-v2-m3)
           → top-10 with graph context
           → Claude generates response with:
               - Semantic match chunks
               - Explicit jhāna→nibbāna relationship
               - Tradition-specific framing (Theravāda only)
               - Correct sutta citations from graph
```

---

## Количественное сравнение для Dharma RAG

### Стоимость по фазам

| Фаза | Embedding-only | Graph-only | Hybrid (рекомендация) |
|------|---------------|------------|----------------------|
| Phase 1 MVP | **$0** | $500-800 | **$0** |
| Phase 1.5 (900K) | **$0.07** | $5,000-15,000 | **$1-5** (LightRAG) |
| Phase 2 (качество) | $50 (fine-tune) | $200 (курация) | **$50-200** |
| Phase 3 (production) | $0/мес | $50-100/мес (Neo4j) | **$0-20/мес** |
| **ИТОГО год 1** | **~$50** | **$6,000-16,000** | **$50-225** |

### Время реализации

| Подход | До MVP | До production |
|--------|--------|---------------|
| Embedding-only | **2 недели** | 2 месяца |
| Graph-only | 2-3 месяца | 6 месяцев |
| Hybrid (embedding first) | **2 недели** | 3-4 месяца |

### Качество retrieval (ожидаемое)

| Метрика | Embedding-only | Graph-only | Hybrid |
|---------|---------------|------------|--------|
| ref_hit@5 (general) | 70-80% | 60-70% | **85-90%** |
| ref_hit@5 (multi-hop) | 20-30% | **80-90%** | **80-90%** |
| ref_hit@5 (Pāli lexical) | 50-60% | **90-95%** | **90-95%** |
| Faithfulness | 0.85-0.90 | **0.92-0.97** | **0.92-0.97** |
| Doctrinal accuracy | 3.8-4.2/5 | **4.5-4.8/5** | **4.5-4.8/5** |

---

## Почему "чёрный ящик" не так страшен, как кажется

### Митигации непрозрачности embedding

1. **Sparse vectors (BGE-M3)** — видимые лексические веса. Можно понять, какие слова сработали.

2. **BM25** — полностью детерминированный. "jhāna" найдёт точно документы с "jhāna".

3. **Reranker объясним** — cross-encoder даёт score, можно понять порог.

4. **Citation verification** — каждая цитата проверяется постфактум.

5. **Metadata filtering** — tradition=theravada, teacher=Thanissaro — это не чёрный ящик.

6. **Eval framework** — golden test set показывает, где модель ошибается.

7. **Langfuse tracing** — полный лог каждого вызова, входы/выходы.

### Когда "чёрный ящик" действительно проблема

- **Multi-hop reasoning:** "Как A связано с C через B?" — embedding не может
- **Structural queries:** "Все факторы первой jhāna" — нужен граф
- **Tradition disambiguation:** "anattā в Тхераваде vs buddha-nature в Махаяне" — embedding может смешать
- **Curriculum planning:** "Что изучать после satipaṭṭhāna?" — нужен граф прогрессии

**Решение:** YAML-граф ключевых концепций (200-500 узлов) решает 80% этих проблем без стоимости полного GraphRAG.

---

## Рекомендация: Прагматический гибрид

### Фаза 1: Embedding-first (сейчас)

```
BGE-M3 (dense + sparse) + BM25 + metadata filters
```

- Быстрый старт, $0
- 70-80% качества на общих запросах
- Достаточно для MVP и первых пользователей

### Фаза 2: Добавить лёгкий граф (через 2 месяца)

```
+ concepts.yaml (200-500 концепций, ручная курация)
+ LightRAG (автоматический граф для остального)
```

- +10-15% качества на structured/multi-hop запросах
- Стоимость: $1-5 (LightRAG) + ~50 часов ручной работы
- Доктринальная точность значительно вырастет

### Фаза 3: Полная интеграция (через 6 месяцев)

```
Embedding + Graph + Reranker → Unified RAG pipeline
```

- Лучшее из обоих миров
- Retrieval 85-90% на всех типах запросов
- Объяснимые результаты с graph-context

### Что НЕ делать

1. ❌ **Не начинать с графа** — слишком дорого и долго для MVP
2. ❌ **Не использовать Microsoft GraphRAG** — $5000-15000 для нашего масштаба
3. ❌ **Не ставить Neo4j** — overkill для 200-500 концепций, YAML/JSON достаточно
4. ❌ **Не полагаться ТОЛЬКО на embedding** — потеряем multi-hop и structural queries
5. ❌ **Не автоматизировать 100% графа** — для доктринальной точности нужна ручная курация ключевых концепций

---

## Источники

- Microsoft GraphRAG: https://github.com/microsoft/graphrag
- LightRAG: https://github.com/HKUDS/LightRAG
- LazyGraphRAG (Microsoft, 2025): https://github.com/microsoft/graphrag/blob/main/docs/lazy_graphrag.md
- Neo4j Knowledge Graph vs Vector RAG: https://neo4j.com/blog/developer/knowledge-graph-vs-vector-rag/
- "Vector Databases vs Knowledge Graphs for RAG": meilisearch.com, instaclustr.com, redpanda.com (2025-2026)

---

*Документ для проекта Dharma RAG. Дополнение к EMBEDDING_MODELS_RESEARCH_2026.md*
