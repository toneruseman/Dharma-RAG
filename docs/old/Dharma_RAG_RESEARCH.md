# Dharma-RAG: архитектура RAG для буддийских текстов

**Репозиторий `toneruseman/Dharma-RAG` недоступен** для публичного анализа (приватный, удалён или опечатка в URL) — ни прямой `web_fetch`, ни поиск в GitHub/Google/Wayback не возвращают никакого следа. Это означает, что **оценка «текущего состояния» невозможна**, и отчёт построен как архитектурное руководство «с чистого листа», опирающееся на SOTA-практики 2025–2026 и на ближайшие публичные аналоги (особенно **`xr843/fojin`** — 9200+ буддийских текстов, BGE-M3, pgvector HNSW, KG 31K+ сущностей; **DharmaSutra** от gauraw.com; проект SuttaCentral/84000 как референс корпусной структуры). Всё дальнейшее — рекомендации, которые нужно будет сверить с фактическим кодом, как только доступ появится.

Ключевой вывод исследования: **для заявленного сценария (ru/en, цитатная корректность, multi-hop, локальный deploy на 2×48 ГБ + 256 ГБ RAM) доминирует один стек** — BGE-M3 (dense+sparse+ColBERT в одной модели) в Qdrant с named vectors, LightRAG или HippoRAG 2 как графовый слой, Cohere/Voyage rerank в Phase 1 → Qwen3-Reranker-4B / bge-reranker-v2-m3 локально, Claude Sonnet 4.5 → Qwen3-235B-A22B или DeepSeek V3.2 через KTransformers для генерации. Оценка — RAGAS + ALCE + Lynx + human-gate буддологами.

---

## 1. Критический взгляд на репозиторий и позиционирование

Отсутствие публичных артефактов Dharma-RAG делает невозможной оценку технологического стека, но позволяет зафиксировать **риски, с которыми почти неизбежно сталкивается любой новый проект** в этой нише:

- **Lock-in на OpenAI embeddings** — если в Phase 1 выбрано `text-embedding-3-large` без Qdrant named vectors, миграция на русскоязычные модели (FRIDA, GigaEmbeddings) или BGE-M3 потребует полной переиндексации.
- **Отсутствие sparse-ретривера для русской морфологии** — без BM25 c PyMorphy3 или SPLADE восстановление цитат по терминам «бодхичитта/бодхичитты/бодхичитте» проседает.
- **Ломка стихотворной структуры при fixed-size chunking** — гатхи и мантры теряют смысл, если разрезаны посередине.
- **Отсутствие citation verification** — буддийский корпус специфичен тем, что атрибуция цитаты неверной школе/автору хуже, чем отсутствие ответа.
- **Отсутствие eval-gate в CI** — без RAGAS/ALCE в pipeline регрессии выкатываются в продакшен незамеченными.

**Рекомендация:** запросить у владельца код/README; до получения — следовать blueprint ниже, который закрывает все вышеперечисленные риски by design.

---

## 2. Обработка корпуса: от сканов до чанков

### 2.1 OCR и парсинг PDF

Сравнение инструментов на смешанном мультиязычном буддийском корпусе (цифровые PDF академических изданий + сканы тибетских/деванагари):

| Инструмент | Сильные стороны | Слабости | Роль в pipeline |
|---|---|---|---|
| **Docling (IBM)** | Structure-aware, DocLayNet+TableFormer, ~28 с на документ, интеграция с LlamaIndex | Слабее на вложенных таблицах | **Primary** для цифровых PDF |
| **MinerU (OpenDataLab)** | LayoutLMv3+YOLOv8, **84 языка** (включая tibetan/devanagari), UniMERNet для формул | Тяжёлый, требует GPU | **Для сканов и кириллицы/тибетского** |
| **Gemini 2.5 Pro Vision** | Native PDF vision, 1M context, отличен на layout и мантрах | Cloud-only, стоимость | **Fallback** для сложных страниц |
| **Marker** | PDF→Markdown+Surya OCR, EPUB/DOCX | Медленный | Формульные академ. работы |
| **Nougat (Meta)** | Academic PDF→LaTeX, формулы | Зацикливается out-of-domain | Редкая ниша |
| **LlamaParse** | SOTA на таблицах | Cloud-only (проблема для restricted Ваджраяна-текстов) | Ограниченно |

**Транслитерация:** `pyewts` (Wylie↔Unicode тибетского), `indic_transliteration`/sanscript (IAST↔Devanagari). Хранить **параллельно оригинал + ASCII-нормализацию + перевод** — без этого recall на запросах типа «śūnyatā» vs «шуньята» vs «sunyata» проседает драматически.

### 2.2 Chunking: многослойная стратегия

Для буддийских текстов оптимален **трёхуровневый pipeline**, а не одна стратегия:

1. **Структурный слой (document-aware)** — разбиение по заголовкам сутры/главы/раздела канона, с **сохранением стихов (gāthā) как атомарных единиц**. Никогда не резать pāda посередине. Метаданные: `canonical_id` (DN22, Toh 44-45), `verse_range`, `folio` ([F.362.b]).
2. **Контекстный слой (Anthropic Contextual Retrieval, сент. 2024)** — LLM (Claude Haiku с prompt caching, ~$1.02 на 1M токенов) генерирует 50–100-токенный префикс к каждому чанку («Из Samyutta Nikaya, SN 22.59, Будда учит anatta…»). Замеры Anthropic: **−49% retrieval failures, −67% в связке с re-rank**.
3. **Иерархический слой (RAPTOR)** — рекурсивная кластеризация + LLM-суммаризация для обзорных запросов («основные взгляды Йогачары»). Дорого, но даёт +20% точности на high-level запросах.

**Late chunking (Jina v3, 8192 ctx)** — альтернатива для длинных шастр с перекрёстными ссылками; **proposition-based** — только для философских трактатов, **никогда для гатх/мантр**.

### 2.3 Схема метаданных

Ориентир — BDRC Buddhist Digital Ontology + FRBR-разделение Work/Expression/Instance + практика SuttaCentral и 84000:

```json
{
  "id": "DN22",
  "canonical_id": "DN22",
  "parallels": ["MA98", "Toh 291"],
  "title": {"original": "Mahāsatipaṭṭhāna Sutta", "en": "...", "ru": "..."},
  "language": "pi", "script": "latn",
  "tradition": "Theravada",
  "school": "...",
  "text_type": "sutra",
  "canon_section": "Pali_Canon",
  "author": {"name_original": "...", "role": "attributed"},
  "period": {"century": "5th BCE (oral)"},
  "source": {"publisher": "SuttaCentral", "license": "CC-BY-NC-4.0", "restricted": false},
  "structure": {"chapter": 1, "verse_range": "1.1-1.15", "folio": "..."},
  "chunk_meta": {"chunk_type": "prose|gatha|mantra|commentary_note",
                 "parent_ref": "...", "cross_refs": [...],
                 "technical_terms": [{"term": "anatta", "lang": "pi"}]}
}
```

Флаг `restricted: true` критичен для **ваджраянских текстов** — они не должны уходить в cloud API и не должны попадать в публичный retrieval.

### 2.4 Мультиязычие ru/en

- **Language detection:** `fasttext lid.176` как основной (95%+ accuracy, 120k предл/сек), `lingua-py` для смешанных чанков.
- **Не переводить всё в один язык** — следовать образцу SuttaCentral: параллельные версии с общим `canonical_id`, технические термины (nirvāṇa, śūnyatā) всегда в оригинале.
- **Русская морфология:** PyMorphy3-лемматизация **обязательна** для BM25 (подтверждено RusBEIR 2025). Без этого recall на морфологически богатых запросах падает на 8+ pp.
- **Cross-lingual retrieval:** единый мультиязычный эмбеддер (BGE-M3) + hybrid с language-specific BM25 + RRF, опционально HyDE для кросс-языковых запросов (RU query → EN pseudo-answer → dense search в en-корпусе).

---

## 3. Embedding-модели: сравнение и выбор

### 3.1 Сводная таблица

| Модель | Params | Контекст | Dim | MMTEB/MTEB | RU-качество | Стоимость/VRAM | Лицензия |
|---|---|---|---|---|---|---|---|
| **OpenAI text-embedding-3-large** | — | 8191 | 3072 (MRL) | MTEB ~64.6 | средн. | $0.13/M | Proprietary |
| **Voyage-3-large** | — | 32K | 1024 (MRL, int8/bin) | +9.74% над OAI-v3 | сильн. | $0.06/M | Proprietary |
| **Cohere Embed v4 multilingual** | — | **128K** | 1536 (MRL) | MTEB 65.2 | сильн. | $0.12/M | Proprietary |
| **Jina v4** | 3.8B | 32K | 2048 (MRL) + multi-vec | MMTEB **66.49** | сильн. | API + OSS | Qwen Research |
| **Gemini Embedding 002** | — | 8K | 3072 (MRL) | MTEB **68.32** | EN лидер | $0.15/M | Proprietary |
| **Qwen3-Embedding-8B** | 8B | 32K | 4096 | MMTEB **70.58 #1** | SOTA | ~17 ГБ VRAM | Apache 2.0 |
| **Qwen3-Embedding-4B** | 4B | 32K | 2560 | MMTEB ~69 | очень сильн. | ~9 ГБ | Apache 2.0 |
| **BGE-M3** | 568M | 8192 | 1024 + sparse + ColBERT | MIRACL #1 | сильн. | ~2.3 ГБ | **MIT** |
| **BGE-Multilingual-Gemma2** | 9B | 8K | 3584 | MMTEB top-3 | сильн. | ~18 ГБ | Gemma (restric.) |
| **multilingual-e5-large-instruct** | 560M | 512 | 1024 | MMTEB ~64 | хорош. | ~1.1 ГБ | MIT |
| **Snowflake Arctic Embed L v2.0** | 568M | 8192 | 1024 (int4+MRL) | MIRACL/CLEF top | сильн. | ~1.2 ГБ | Apache 2.0 |
| **Nomic Embed v2 MoE** | 475M/305M акт. | 512 | 768 | BEIR на уровне 2× dense | средн. | ~1 ГБ | Apache 2.0 |
| **FRIDA (ai-forever)** | 823M | 512 | 1536 | **ruMTEB ~0.70** | RU-лидер open (до 2025) | ~1.7 ГБ | MIT |
| **GigaEmbeddings (Sber)** | 2.2B | 4K | — | **ruMTEB 69.1 SOTA** | RU #1 | ~4.5 ГБ | Open weights |
| **Jina-ColBERT-v2** | 560M | 8192 | 128/token (MRL) | 89 яз. late-int. | сильн. | ~1.2 ГБ | CC-BY-NC |

### 3.2 Ключевой выбор — BGE-M3

**BGE-M3 — единственная модель, выдающая за один forward-pass dense (1024-dim) + sparse (30K-dim, аналог BM25) + ColBERT-мультивектор (128-dim per token)**. Это идеально ложится на Qdrant named vectors и снимает необходимость держать три отдельные модели. Лицензия MIT, 100+ языков, 8192-токенов контекст — покрывает весь use case.

**Стратегия по фазам:**

- **Phase 1 (cloud):** `Voyage-3-large` (best quality/cost) ИЛИ `Cohere Embed v4` (128K контекст — длинные сутры без чанкинга). Jina v3 как drop-in для миграции с OpenAI. Для RU-only запросов — экспериментальный слой **GigaEmbeddings API** если доступен.
- **Phase 2 (self-hosted 2×48 ГБ):** **BGE-M3** как primary hybrid-ретривер + **Qwen3-Embedding-4B** как дополнительный dense второго мнения + **FRIDA** как RU-ускоритель (~2 ГБ, можно держать в hot-path постоянно). Все три параллельно в TEI или Infinity.

### 3.3 Стратегия миграции в Qdrant (named vectors)

Критично заложить в collection schema изначально:

```python
client.create_collection(
    "dharma",
    vectors_config={
        "dense_v1": VectorParams(size=1024, distance=COSINE,
                                 on_disk=True,
                                 quantization_config=ScalarQuantization(INT8, always_ram=True)),
        # dense_v2 добавляется позже без пересоздания коллекции
        "colbert": VectorParams(size=128, distance=COSINE,
                                multivector_config=MultiVectorConfig(MAX_SIM)),
    },
    sparse_vectors_config={
        "bm25":   SparseVectorParams(modifier=Modifier.IDF),
        "splade": SparseVectorParams(),
    })
```

5-фазный zero-downtime blue/green: **Add slot → Backfill** (conditional update по `embed_version` с 1.16+) **→ Dual-write → Canary A/B → Deprecate v1**. Для смены размерности — отдельные коллекции + atomic alias swap. Shared ID между Qdrant и графом — **UUIDv5(namespace, canonical_uri)**.

---

## 4. Vector store и Knowledge Graph

### 4.1 Vector-only: Qdrant — явный победитель

| БД | Hybrid | Quantization | Named vectors | Multi-vector | Память 10M×1024 fp32 | Оценка |
|---|---|---|---|---|---|---|
| **Qdrant** | Native sparse+BM25+RRF | Scalar int8 (4×), Binary (32×), BQ 1.5-bit | ✅ **Первоклассная** | ✅ Native | ~40 ГБ raw, ~5 ГБ с BQ+inline (1.16) | ⭐⭐⭐⭐⭐ |
| **Milvus** | Native hybrid | Scalar/PQ/SQ8/Binary/RaBitQ | ✅ | ✅ | ~40 ГБ | ⭐⭐⭐⭐ |
| **Weaviate** | BM25+RRF | PQ/SQ/BQ | ⚠ Named с v1.24 | ⚠ | ~40–60 ГБ | ⭐⭐⭐⭐ |
| **pgvector 0.8** | Manual (tsvector + RRF) | halfvec, bit, sparsevec | ❌ | ❌ (2000-dim limit) | ~60–120 ГБ | ⭐⭐⭐ |
| **LanceDB** | FTS+vector | IVF_PQ | Multiple | ⚠ | Columnar, disk-first | ⭐⭐⭐⭐ embedded |
| **Chroma** | Basic | — | ❌ | ❌ | ~40 ГБ | ⭐⭐ prototype-only |

**pgvectorscale (Timescale) заявляет 11.4× лидерство над Qdrant на 50M векторов** (май 2025), но Qdrant 1.16 с ACORN + inline storage сократил разрыв; на 10M корпусе Qdrant выигрывает однозначно.

### 4.2 Knowledge Graph: выбор зависит от стадии

- **Phase 1:** **Neo4j AuraDB** — самый зрелый managed graph, Cypher 25 с vector index, Bloom-визуализация, готовые GraphRAG-интеграции.
- **Phase 2 (embedded):** **Kuzu/RyuGraph** — в процесс, columnar, HNSW+FTS extensions, Cypher; отлично для single-machine. ⚠ Kuzu архивирован в октябре 2025, активно развивается fork **RyuGraph** (Predictable Labs).
- **Unified альтернатива:** `PostgreSQL + pgvector + Apache AGE` — один стек, SQL+Cypher в одной транзакции. OK до 5M векторов; проседает дальше.

**RDF vs LPG.** RDF (Oxigraph) оправдан только если нужна интероперабельность с BDRC bdo.ttl/CBETA/84000. В остальных случаях LPG (Neo4j/Kuzu) даёт лучший DX, Text2Cypher через LLM, быстрее multi-hop. **Компромисс:** LPG как основное хранилище + импортёр из BDRC RDF + хранение BDRC URI как `external_id`.

### 4.3 Схема графа для буддийских текстов (выдержка)

Сущности: `Work` (абстрактная композиция — «Алмазная сутра»), `Expression` (санскритская recension / кит. перевод Кумарадживы), `Instance` (конкретное издание CBETA), `Chunk`, `Person`, `School`, `Place`, `Concept` (SKOS-style с prefLabel/altLabel), `Practice`, `Event`, `Period`.

Ключевые рёбра: `AUTHORED`, `TRANSLATED{from_lang,to_lang,year}`, `COMMENTED_ON`, `TEACHER_OF`, `DISCIPLE_OF`, `BELONGS_TO_SCHOOL`, `CITES{count,sections}`, `PARALLEL_TO{correspondence_type}` (Pali↔Skt↔Zh parallels), `DISCUSSES{prominence}→Concept`, `EMPHASIZES` (школа→концепция), `ROOTED_IN_CONCEPT` (практика→концепция).

Пример запроса «все практики Гелуг, связанные с шуньятой»:

```cypher
MATCH (s:School {name:"Gelug"})-[:PRACTICES]->(p:Practice)
      -[:ROOTED_IN_CONCEPT]->(c:Concept)-[:RELATED_TO*0..2]->(t:Concept)
WHERE t.label_skt = "śūnyatā" OR t.preferred_label_en =~ "(?i).*emptiness.*"
RETURN DISTINCT p.name, collect(DISTINCT t.preferred_label_en)
```

Результат → из Qdrant подтянуть chunks, где `:DISCUSSES` указывает на найденные Concept-узлы (через shared UUIDv5).

---

## 5. RAG-архитектура: какой паттерн выбрать

### 5.1 Сравнение подходов

| Архитектура | Indexing cost | Query cost | Multi-hop | Incremental | Best for | Зрелость 2026 |
|---|---|---|---|---|---|---|
| Vanilla RAG | Минимум | Низкий | Слабо | ✅ | Factoid | Production |
| **Microsoft GraphRAG** | **Очень высокий** (LLM community summaries, ~$1/МБ) | Средн.-высок. | ✅ (global) | ❌ rebuild | Глобальные обзоры | Stable v2 |
| **LightRAG** (HKUDS) | Средний | Низкий-средн. | ✅ dual-level | ✅ Хорошо | Relational queries, budget | Production |
| **LazyGraphRAG** (MS) | **0.1% от GraphRAG** | Средний | ✅ | ✅ Streaming | Exploratory | Beta |
| **HippoRAG 2** (OSU) | Низкий-средн. (9M tok vs 115M у GraphRAG для MuSiQue) | Низкий (PPR O(E)) | ✅✅ **SOTA** | ✅✅ | Multi-hop + long-term memory | Зрелый |
| **Fast-GraphRAG** (Circlemind) | Низкий-средн. | Низкий | ✅✅ (27× быстрее GraphRAG) | ✅ | Promptable domain | v0.0.x |
| **Agentic RAG** (CRAG, Self-RAG) | — | Высокий | ✅ (iterative) | — | Complex/underspecified | Production |

**Бенчмарки multi-hop (HippoRAG 2 paper, Feb 2025):** MuSiQue F1 44.8 → **51.9**, 2Wiki R@5 76.5% → **90.4%**. На 2WikiMHQA (Circlemind): VectorDB 0.23, LightRAG 0.28, GraphRAG 0.64, **Fast-GraphRAG 0.94**. LazyGraphRAG: 100% win rate против vector/RAPTOR/LightRAG/GraphRAG на 5590 AP news articles.

**Критично:** arxiv 2506.05690 (GraphRAG-Bench) показывает, что **GraphRAG часто проигрывает vanilla RAG на real-world задачах** (−13.4% на NQ). Вывод: **обязателен ablation на собственном корпусе**.

### 5.2 Рекомендация — Hybrid HippoRAG 2 + Contextual Retrieval + Agentic wrapper

Для буддийского корпуса критичны: точность цитат, multi-hop по «учитель→ученик→текст→термин», cross-lingual retrieval, приемлемый cost индексации (корпус редко обновляется, но может расти).

**HippoRAG 2 оптимален** как графовый слой: SOTA multi-hop, дешёвая индексация (в 10× дешевле GraphRAG), incremental updates, PPR-ретривал естественно отражает ассоциативную структуру буддийского знания. **LightRAG** — разумная альтернатива с dual-level entity+concept, нативная интеграция с BGE-M3 и Kuzu. **Полный Microsoft GraphRAG** — только для offline-генерации reference summaries по школам.

### 5.3 Query understanding — таксономия для буддизма

| Тип запроса | Пример | Стратегия |
|---|---|---|
| Factoid/citation | «Где Будда учит anatta в SN?» | Single retrieval + metadata filter |
| Cross-canonical comparative | «Как Падмасамбхава vs. Нагарджуна о pratityasamutpāda?» | Decompose → parallel retrievals → synthesize |
| Multi-hop lineage | «Кто ученики Цонкапы писали о śūnyatā в традиции X?» | HippoRAG PPR traversal |
| Practice instruction | «Инструкции shamatha по Лам-риму» | Query expansion + HyDE + parent-chunk |
| Doctrinal abstract | «Что такое Madhyamaka prasangika?» | Step-Back + community summary |
| Cross-lingual | RU query, источники EN/Pali | HyDE на EN + cross-lingual embedding + оригинал+перевод в ответе |
| Polemic | «Сватантрика vs. Прасангика» | Decompose в [позиция A][позиция B][critique][authors] |

**Обязательны:** term normalization dictionary (IAST ↔ Devanagari ↔ Wylie ↔ кириллическая транслитерация ↔ английский перевод), author alias graph («Nāgārjuna = Нагарджуна = 龍樹 = Klu-sgrub»), citation-aware chunking с сохранением `MN.10.5` как metadata.

---

## 6. Re-ranking: двухуровневый подход

| Модель | Size | Multilingual (RU) | License | BEIR/MTEB-R | Позиция |
|---|---|---|---|---|---|
| **Cohere Rerank 3.5/4.0** | Proprietary | ✅ **SOTA RU** | Commercial | BEIR multiling. лидер | Phase 1 default |
| **Voyage rerank-2.5** | Proprietary, 32K ctx | ✅ 31 langs | Commercial | +12.7% vs Cohere на MAIR | Phase 1 альтернатива |
| **Qwen3-Reranker-4B** | 4B | ✅ 100+ langs, instruction-aware | Apache 2.0 | **MTEB-R 69.76 best open** | Phase 2 primary |
| **mxbai-rerank-large-v2** | 1.5B | ✅ 100+ langs | Apache 2.0 | **BEIR 57.49 лидер open** | Phase 2 альтернатива |
| **Qwen3-Reranker-8B** | 8B | ✅ | Apache 2.0 | CMTEB-R 77.45 | Phase 2 max quality |
| **BGE-reranker-v2-m3** | 568M | ✅ | Apache 2.0 | Strong baseline | Phase 2 fast path |
| **BGE-reranker-v2-gemma** | 2B | ✅ | Gemma | Выше v2-m3 | Phase 2 balanced |
| **Jina-reranker-v2-multi** | 278M | ✅ 100+ langs | **CC-BY-NC** | SOTA MKQA | Только API |
| **Jina-ColBERT-v2** | 560M | ✅ 89 langs | CC-BY-NC | Late-interaction | Опциональный доп. слой |

**Двухуровневая схема:** hybrid retrieval → top-50 → **cross-encoder rerank** (Cohere в Phase 1 / Qwen3-4B в Phase 2) → top-8 → опциональный **LLM re-rank** (Claude Sonnet для критических citation-запросов).

**RRF (k=60)** — fusion-алгоритм, не re-ranker, но обязательный слой hybrid-поиска (BM25 + dense + PPR-graph).

---

## 7. LLM: cloud и локальная инфраструктура

### 7.1 Cloud LLM (апрель 2026)

| Модель | Цена $/M (in/out) | Контекст | RU + Buddhist | Примечания |
|---|---|---|---|---|
| **Claude Opus 4.6/4.7** | $5/$25 | 1M | Отлично | Лучшее citation, agentic coding |
| **Claude Sonnet 4.6** | $3/$15 | 1M | Отлично | Best default для генерации |
| **Claude Haiku 4.5** | $1/$5 | 200K | Хорошо | Indexing (Contextual Retrieval с caching) |
| **GPT-5.4** | $2.50/$20 | 1M+ | Отлично | 5-level reasoning, Computer Use |
| **GPT-5.2** | $0.88/$7 | 400K | Очень хорошо | Сильный baseline |
| **Gemini 3.1 Pro** | ~$2/$12 | 1M (10M claim) | Очень хорошо | Native PDF vision |
| **Gemini 2.5 Flash-Lite** | $0.10/$0.40 | 1M | Хорошо | Декомпозиция, routing |
| **Mistral Large 3** | $2/$6 | 131K | Хорошо | EU data residency |
| **DeepSeek R1** | $0.55/$2.19 | — | Хорошо | Reasoning, open-weights |

**Prompt caching** у Claude (90% экономии на повторах) критичен для Contextual Retrieval этапа индексации. **Long-context cliff:** даже Gemini 3 Pro даёт 77% на 8-needle MRCR при 128K и падает до 26.3% при 1M — **не полагайтесь на рекламные цифры**, валидируйте на RULER/LongBench v2.

### 7.2 Open-source frontier (апрель 2026)

| Модель | Params / активные | Контекст | Лицензия | Заметки |
|---|---|---|---|---|
| **DeepSeek V3.2 Speciale** | 685B / 37B MoE | 128K+ | MIT | DSA — near-linear attention; LMArena Elo ~1421 |
| **Qwen3.5-397B-A17B** | 397B / 17B MoE | 128K–1M | Apache 2.0 | GPQA Diamond 88.4 (заявлено) |
| **Qwen3-235B-A22B** | 235B / 22B MoE | 128K | Apache 2.0 | Main recommendation для локала |
| **Qwen3-72B / Qwen2.5-72B** | 72B dense | 128K | Apache 2.0 | Dense flagship |
| **Kimi K2.5** | 1T / 32B MoE | — | Open weights | 384 экспертов, powers Cursor Composer 2 |
| **GLM-5.1** | 744B / 40B MoE | — | MIT | 77.8% SWE-Bench Verified |
| **Llama 4 Scout/Maverick** | 17B active | 10M (Scout) | Llama 4 Community | Cap 700M MAU |
| **Gemma 4** | 26B MoE | 256K | Gemma | 85 tok/s на consumer |
| **T-pro 2.0 (T-tech)** | — | — | Open | **RU SOTA:** ruAIME-2025 0.646 vs GPT-4o 0.069 |
| **Vikhr-Nemo-12B** | 12B | — | Open | Лучший RU open среди small |

### 7.3 Локальный inference на 2×48 ГБ VRAM + 256 ГБ RAM

| Движок | Сильное место | Для чего на нашем hardware |
|---|---|---|
| **vLLM** | PagedAttention, broadest hw, ~12.5k tok/s Llama-8B BF16 на H100 | **Default** для dense моделей 7–72B |
| **SGLang** | RadixAttention, +29% throughput на prefix-shared (RAG!) | **Предпочтительно для RAG** с повторяющимися prefix/шаблонами |
| **KTransformers** (Tsinghua) | **Expert offloading для MoE** (DeepSeek V3 Q4 в 14 ГБ VRAM + 382 ГБ RAM); 3–28× vs llama.cpp | **Критично** для DeepSeek V3.2 и Qwen3-235B на нашем железе |
| **TensorRT-LLM** | +15–30% после компиляции, NVIDIA lock-in | Для пикового throughput в проде |
| **llama.cpp/GGUF** | CPU+GPU fallback | Dev/edge |
| **ExLlamaV2 (EXL2)** | Дробная квантизация | Experiments |

**Что умещается на 2×48 ГБ (96 ГБ VRAM) + 256 ГБ RAM:**

- **Qwen2.5-72B / Qwen3-72B dense Q6/Q8** — влезает целиком в VRAM через TP=2 (2×48). Рекомендованная основная модель Phase 2 для dense.
- **Mistral Large 2 (123B) Q4/Q5** — ~70–85 ГБ, TP=2 впритык, нужен offload KV-cache.
- **Qwen3-235B-A22B MoE** — через **KTransformers** (22B активных на GPU, эксперты в 256 ГБ RAM) реально работает с приемлемой латентностью.
- **DeepSeek V3.2 (685B / 37B MoE) Q4_K_M** — через KTransformers: ~27 ГБ VRAM + ~350 ГБ RAM. **Наш 256 ГБ RAM тут впритык** — возможно понадобится SSD-offload для части экспертов либо Q3.
- **Llama 4 Scout** — 17B active, спокойно.
- **Embedding+Reranker stack:** BGE-M3 (2.3 ГБ) + Qwen3-Reranker-4B (~9 ГБ) + FRIDA (~2 ГБ) = ~15 ГБ, можно держать постоянно на GPU0, а GPU1 полностью под LLM.

**NVLink vs PCIe:** для 2× custom RTX 4090/5090 48GB с PCIe 5.0 x16 — tensor parallelism работает, но с заметным overhead на all-reduce. Рекомендованная стратегия: **pipeline parallelism** для моделей, которые делятся чисто, **tensor parallelism** для MoE через vLLM/SGLang + NCCL.

### 7.4 Fine-tuning — когда нужен и когда нет

**Frameworks 2026:**
- **Unsloth** — доминирует single-GPU: 2–5× быстрее, 70–80% меньше VRAM. Llama-3 70B QLoRA в 48K контексте на 1×A100 80GB. Feb 2026: 12× быстрее MoE training, 50K+ GitHub stars. Multi-GPU — в paid Pro.
- **Axolotl v0.8+** — production pipelines, YAML, Ring FlashAttention, QAT, GRPO.
- **LLaMA-Factory v0.9.4** (Dec 2025) — web UI, Megatron-LM + KTransformers integration.
- **TRL** — стандарт для DPO/GRPO; сочетать с Unsloth.

**Что fine-tune'ить на 2×48 ГБ:**
1. **Embeddings (обязательно):** BGE-M3 или Qwen3-Embedding-0.6B c LoRA (r=32, α=64), batch 128, seq 512, **3–5 эпох ~10–20 часов**. Ожидаемый gain: +5–15 pp nDCG на domain-specific retrieval.
2. **Reranker (желательно):** Qwen3-Reranker-4B или bge-reranker-v2-m3 с LoRA на synthetic Buddhist QA.
3. **LLM QLoRA:** Qwen2.5-72B QLoRA — возможно (базовая 35–40 ГБ + градиенты ~5 ГБ); Qwen3-30B dense QLoRA — комфортно.
4. **Full FT 70B** — не влезает (560–640 ГБ), нужен кластер.

**Метод RAFT (Berkeley):** обучение на `(Q, oracle_doc, distractors, CoT_answer)` с **оптимальным P=80% oracle / 20% без** (чистые 100% ухудшают). +35% на HotpotQA, +76% на Torch Hub. **Рекомендуется для финального домен-специфичного этапа**.

**Hard negatives mining** для embedding FT — через NV-Retriever подход: teacher-модель (Qwen3-8B) отбирает 7 негативов на query с порогом false-positive 95%. Добавить **cross-school negatives** (тхеравадинский термин vs. махаянский с тем же корнем).

**Вывод:** fine-tuning embedding + reranker на корпусе — **обязательно**, даёт крупнейший lift. FT генеративной LLM — опционально, при наличии ~300+ буддийских QA высокого качества.

---

## 8. Оценка качества: формальные критерии

### 8.1 Стек метрик

| Слой | Метрики | Порог приёмки |
|---|---|---|
| **Retrieval** | NDCG@10, Recall@10, MRR@10 | ≥ 0.70, ≥ 0.85, ≥ 0.75 |
| **Generation (RAGAS)** | faithfulness, answer_relevancy, context_precision, context_recall | ≥ **0.90**, 0.85, 0.80, 0.85 |
| **Citation (ALCE)** | Citation Recall, Precision, F1 | ≥ 0.90, 0.85, 0.87 |
| **Hallucination** | Lynx-rate, SelfCheckGPT consistency | ≤ 3%, ≥ 0.80 |
| **Multi-hop** | Answer F1, Reasoning-path correctness | ≥ 0.65, ≥ 0.70 |
| **Operational** | Latency p95, Cost/query | ≤ 4 с, бюджет |
| **"IDK"-rate** на adversarial unanswerable | | ≥ 0.85 |
| **Human gate** (буддологи, n=50) | Доктринальная корректность | ≥ 0.92 accepted |

### 8.2 Фреймворки

**Основной стек:** RAGAS (faithfulness + context_*) + DeepEval (G-Eval с custom rubric «доктринальная точность») + ALCE (citation Recall/Precision через NLI) + Lynx-8B как cheap guardrail на 100% трафика + SelfCheckGPT на critical queries. **TruLens RAG Triad** promts — проверенно дают F1 +8% на LLMAggreFact.

**LLM-as-judge — обязательные mitigation'ы:**
- Position bias → swap evaluation (A vs B + B vs A).
- Verbosity bias → явная инструкция, проверка на длинные тавтологии.
- Self-enhancement bias → кросс-модельное жюри (Claude + GPT + Qwen), majority vote.
- Калибровка с людьми: **κ ≥ 0.6 с буддологами** (иначе меняем prompt/модель).

**Human evaluation** неизбежен для доктрины. Инструменты: **Argilla** (HF-экосистема, основной) + **Label Studio** (для span-разметки цитат). IAA: **Krippendorff α ≥ 0.7** обязательно. 2–3 буддолога, 20% двойной разметки. Таксономия ошибок: фактическая / доктринальная / атрибуционная / переводческая / контекстуальная.

### 8.3 Gold-standard датасет

- **Объём:** 500–800 QA (70/30 dev/test split).
- **Таксономия:** 25% factual / 20% definitional / 15% citation-based / 15% multi-hop / 10% comparative / 10% practice / 5% doctrinal-interpretive.
- **Pipeline:** corpus stratified sampling → synthetic generation (Claude Sonnet 4.5) → cross-family LLM validation (GPT-5) → 100% human validation буддологами → adversarial augmentation (hard negatives + counterfactuals для "IDK"-теста) → ru↔en back-translation с ручной выверкой терминов.
- **Каждая QA:** `{question, gold_answer, gold_citations[passage_ids], reasoning_path, difficulty, query_type, language, school, annotator_ids, IAA}`.

### 8.4 Observability

**Phase 1 cloud:** Langfuse (self-hosted, privacy) + Helicone gateway для кеширования + Braintrust для CI/eval. **Phoenix** для dev/debug.

**Что логировать:** `query, language, retrieved_chunks + scores, reranker_scores, final_prompt, model, response, citations_in_response, token_counts, latency_breakdown, user_feedback`.

---

## 9. План A/B-тестирования и ablation

**Baseline v0:** fixed-512 chunking, multilingual-e5-large, hybrid BM25+dense (α=0.5), top-5, no rerank, GPT-4o, system prompt v0.

**15 ablation-осей** (тестировать по одной, Fisher-style, затем фактор-план на топ-3):

| # | Ось | Варианты |
|---|---|---|
| A1 | Embeddings | Voyage-3 / BGE-M3 / Cohere v4 / Qwen3-Emb-4B / Jina v3 |
| A2 | BM25 добавление | Hybrid vs только dense |
| A3 | Contextual chunks | С Anthropic preamble vs raw |
| A4 | Re-ranker | Cohere 3.5 / Qwen3-4B / BGE-v2-m3 / mxbai-v2 / без |
| A5 | Top-K to LLM | 5 / 10 / 20 / 40 |
| A6 | Graph retrieval | HippoRAG 2 vs LightRAG vs Fast-GraphRAG vs без |
| A7 | Query decomposition | Sub-question vs single |
| A8 | HyDE | Вкл./выкл. для cross-lingual |
| A9 | Step-Back | Для abstract-запросов |
| A10 | Self-RAG/CRAG | 0/1/2 итерации |
| A11 | Parent-chunk | Child vs parent |
| A12 | Prompt caching | On/off |
| A13 | LLM | Claude Sonnet 4.5 / GPT-5 / Gemini 2.5 / Qwen3-72B local |
| A14 | RAG arch | Vanilla vs LightRAG vs HippoRAG vs LazyGraphRAG |
| A15 | Late-interaction | Без vs + Jina-ColBERT-v2 stage |

**Primary metric:** `faithfulness × citation_F1` (гармоническое среднее) — не даём улучшать одно ценой другого.

**Статистика:** paired bootstrap n=10000 + Wilcoxon + Bonferroni. MDE 3 pp по faithfulness при n=300, power 0.8. **PPI** для расширения CI где часть оценок — LLM-judge.

**Pareto-frontier** по (quality, latency p95, cost/1k queries) — выбираем конфиги на фронте.

**Decision tree:**
- Если baseline + BM25 + contextual + Cohere rerank даёт R@5 > 0.85 на multi-hop → **граф не нужен**, LightRAG опционально.
- Разрыв на multi-hop > 15 pp → **HippoRAG 2 оправдан**.
- Cross-lingual R@20 < 0.6 без HyDE → **HyDE обязателен**.

---

## 10. Итоговые рекомендации

### Phase 1 — Cloud (быстрый старт, 4–6 недель до MVP)

| Слой | Выбор | Обоснование |
|---|---|---|
| Ingestion/PDF | Docling + MinerU + Gemini 2.5 Vision (fallback) | Покрывает цифру, сканы, сложные layouts |
| Chunking | Document-aware + Contextual Retrieval (Claude Haiku w/ caching) + опционально RAPTOR | −49–67% retrieval failures, сохраняет структуру |
| Embeddings | **Voyage-3-large** primary, Cohere v4 для длинных сутр (128K) | Best RU+EN, MRL, int8 |
| Sparse | BGE-M3 sparse через Infinity API или Qdrant BM25 + PyMorphy3 | Необходим для RU морфологии |
| Vector store | **Qdrant Cloud** с named vectors | Миграционная гибкость |
| Graph | **Neo4j AuraDB** + LightRAG, shared UUIDv5 с Qdrant | Managed, mature GraphRAG |
| Re-rank | **Cohere Rerank 3.5** (SOTA RU) или Voyage rerank-2.5 | Лучшее для RU |
| LLM gen | **Claude Sonnet 4.5** с strict citation prompting | Citations + RU + long-context |
| Framework | LlamaIndex (ingestion + sub-question) + LangGraph (agentic loops) | Data-heavy + orchestration |
| Eval | RAGAS + DeepEval + ALCE + Lynx-8B + human gate буддологов | Многослойная оценка |
| Observability | Langfuse self-hosted + Helicone gateway + Braintrust CI | Privacy + cost + regression blocking |

### Phase 2 — Локально (2×48 ГБ VRAM + 256 ГБ RAM, 3–6 месяцев)

| Слой | Выбор |
|---|---|
| Embeddings primary | **BGE-M3** (dense + sparse + ColBERT в одной модели) |
| Embeddings secondary | Qwen3-Embedding-4B (dense) + FRIDA (RU booster) |
| Vector store | Qdrant self-hosted (той же схемы — zero code change) |
| Graph | **Kuzu/RyuGraph** embedded (или Neo4j Community) |
| Re-rank | **Qwen3-Reranker-4B** primary, bge-reranker-v2-m3 fast path |
| LLM gen primary | **Qwen3-235B-A22B MoE через KTransformers** (22B active на GPU, experts в RAM) |
| LLM gen альтернативы | Qwen2.5-72B Q8 через vLLM TP=2 / Mistral Large 2 Q5 / DeepSeek V3.2 Q4 (впритык) |
| LLM indexer/router | Qwen3-30B-A3B (быстрый, для Contextual Retrieval и query routing) |
| Inference engine | SGLang для RAG generation (prefix-sharing) + KTransformers для MoE |
| FT stack | Unsloth для embedding/reranker LoRA, Axolotl для генеративных моделей |

### Критерии приёмки Phase 1 → релиз v1.0

1. **Blockers** (любой из них проваливает релиз):
   - faithfulness ≥ 0.90
   - citation-F1 ≥ 0.85
   - hallucination-rate (Lynx) ≤ 5%
   - "IDK"-rate на adversarial unanswerable ≥ 0.85
   - human gate буддологов (n=50) ≥ 0.92 accepted
2. **Warnings:** NDCG@10 ≥ 0.70, answer_relevancy ≥ 0.85, latency p95 ≤ 4 с.
3. **CI блокирует PR**, если Blocker регрессирует > 2 pp, Warning > 5 pp.

### 6-спринтовая дорожная карта

- **Sprint 1:** Baseline Phase 1 (Docling → Qdrant → Voyage → Claude) + 100 human-curated QA + Langfuse.
- **Sprint 2:** Contextual Retrieval + RAGAS/DeepEval/ALCE + датасет 300 QA + IAA раунд.
- **Sprint 3:** Lynx guardrail + ARES-PPI калибровка + LightRAG/HippoRAG 2 слой графа.
- **Sprint 4:** Ablation A1–A5 (chunking, embeddings, rerankers, top-K).
- **Sprint 5:** Ablation A6–A15 (graph, query decomposition, CRAG, LLM) + Pareto-frontier.
- **Sprint 6:** Phase 2 migration prep (self-hosted BGE-M3, local LLM через KTransformers), fine-tuning embedding на Buddhist hard negatives, финальный human-gate, v1.0 релиз.

---

## 11. Ключевые риски и mitigation

- **Lock-in на одну embedding-модель** → Qdrant named vectors с первого дня, предусмотреть `dense_v1` + slot под `dense_v2`.
- **Галлюцинированные цитаты** → strict format в prompt, NLI-verification pass на каждой цитате через RoBERTa-large-mnli.
- **Санскрит/тибетский OCR noise** → pre-normalize pyewts/sanscript, alias KG, хранить оригинал + ASCII-fallback.
- **RU морфология** → PyMorphy3 в BM25 pipeline обязателен.
- **Переводческие расхождения** → glossary в system prompt + constrained generation для терминов (śūnyatā остаётся śūnyatā, не «пустота»).
- **Разбиение гатх** → respect-boundary chunking, тест на integrity стихов в CI.
- **Vajrayāna-restricted тексты** → флаг `restricted: true`, исключение из cloud API, локальный-only retrieval.
- **Overreliance на GraphRAG** → ablation обязателен; на real-world задачах часто vanilla+rerank достаточно.
- **Vendor benchmark overstatement** → все заявленные цифры (27× FastGraphRAG, 11.4× pgvectorscale, 67% Anthropic) воспроизводить на собственном корпусе.
- **Human eval cost** → начать с 2 буддологов на 20% пересечения, активное обучение для приоритизации кейсов.

---

## Заключение

Без доступа к текущему коду `Dharma-RAG` прямая оценка невозможна, но **конвергентный blueprint SOTA 2025–2026 для многоязычного буддийского корпуса вырисовывается чётко**: Docling/MinerU → Contextual Retrieval → BGE-M3 (unified hybrid) в Qdrant с named vectors → Neo4j/Kuzu граф с LightRAG или HippoRAG 2 → Cohere/Qwen3 rerank → Claude Sonnet 4.5 (Phase 1) или Qwen3-235B через KTransformers (Phase 2). Оценка — RAGAS + ALCE + Lynx + human gate буддологов с Krippendorff α ≥ 0.7. Критически важно: **никакие рекламные цифры не подменяют ablation на собственном корпусе** — GraphRAG проигрывает vanilla на time-sensitive NQ, Gemini 3 теряет 50 pp качества между 128K и 1M контекста, «лучшая embedding-модель по MTEB» может уступать domain-tuned BGE-M3 на +5–15 pp после LoRA на Buddhist hard negatives.

Новизна этого отчёта относительно публичных аналогов (fojin, DharmaSutra) — это **явная связка: (а) миграционная стратегия через Qdrant named vectors, делающая выбор embedding обратимым; (б) двухуровневая eval-架ка с формальными gates и Krippendorff-валидированным human-loop; (в) KTransformers-based deployment пути для 235B–685B MoE моделей на 96 ГБ VRAM + 256 ГБ RAM, который делает локальный Phase 2 реалистичным уже сегодня**. Если владелец проекта предоставит код, 80% этого blueprint будет применимо напрямую, оставшиеся 20% адаптируются к существующим решениям за 2–4 недели рефакторинга.
