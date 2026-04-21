# RAG Pipeline Architecture

> Детальное описание RAG pipeline в Dharma RAG. Обновляется по мере развития проекта.

---

## Общая схема

```
User Query
    │
    ▼
┌─────────────────────┐
│ 1. Language Detect  │  langdetect
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 2. Semantic Cache   │  Qdrant cache collection
│    Check            │  cosine > 0.92 → return cached
└──────────┬──────────┘
           │ (cache miss)
           ▼
┌─────────────────────┐
│ 3. Query Expansion  │  Pāli glossary lookup
│                     │  Optional HyDE for conceptual
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 4. LLM Routing      │  Haiku classifier
│                     │  simple/complex/philosophical
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────────┐
│ 5. Hybrid Retrieval (parallel)              │
│                                              │
│  ┌─────────────┐ ┌─────────┐ ┌───────────┐ │
│  │ BGE-M3      │ │ BGE-M3  │ │ BM25      │ │
│  │ dense       │ │ sparse  │ │ (Pāli     │ │
│  │ (Qdrant)    │ │ (Qdrant)│ │ tokenizer)│ │
│  └──────┬──────┘ └────┬────┘ └─────┬─────┘ │
│         │             │            │       │
│         └─────────────┴────────────┘       │
│              top-100 each                    │
│                    │                        │
│              RRF Fusion (k=60)               │
│                    │                        │
│                    ▼                        │
│             top-100 merged                   │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────┐
│ 6. Cross-encoder    │  BGE-reranker-v2-m3
│    Reranking        │  top-100 → top-10
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 7. Context Builder  │  Format parent chunks
│                     │  + metadata + citations
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 8. LLM Generation   │  Claude (Haiku/Sonnet)
│    + Streaming      │  SSE
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 9. Citation Verify  │  Parse [source: X]
│                     │  Verify against context
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 10. Save to Cache   │
└──────────┬──────────┘
           │
           ▼
     Final Response
  (text + citations + metadata)
```

---

## Компонент 1: Language Detection

**Модуль:** `src/language/detector.py`

Детектирует язык запроса для правильной обработки:
- Английский → использовать английский корпус primary
- Русский → искать в RU + EN (fallback), Pāli термины через transliteration

**Библиотека:** `langdetect` (port Google CLD3)

**Fallback:** если confidence < 0.9 → assume English

---

## Компонент 2: Semantic Cache

**Модуль:** `src/cache/semantic_cache.py`

**Зачем:** Дхарма-вопросы высоко повторяемы. "Что такое джхана?" ≈ "Расскажи про джханы" ≈ "What are the jhānas?"

**Хранение:** отдельная Qdrant collection `cache`:
```python
{
    "query_embedding": [...],
    "query_text": "What is jhāna?",
    "query_language": "en",
    "response": "Jhāna refers to...",
    "retrieved_chunk_ids": ["ch_001", "ch_002", ...],
    "citations": [...],
    "created_at": "2026-04-14T10:30:00Z",
    "hit_count": 5
}
```

**Lookup:** cosine similarity > 0.92 → return cached.

**TTL:** 30 дней (auto-cleanup через cron).

**Ожидаемый hit rate:** 40-60% в production.

---

## Компонент 3: Query Expansion

**Модуль:** `src/rag/query_expansion.py`

### Pāli Glossary Expansion

Если запрос содержит известный Pāli термин → добавить синонимы:

```
"What is satipaṭṭhāna?"
  → also search for: "satipatthana", "establishment of mindfulness",
                     "four foundations of mindfulness"
```

### HyDE (Hypothetical Document Embeddings)

Для концептуальных запросов генерировать гипотетический "ответ" через LLM, embed его:

```python
hypothetical = await llm.generate(
    f"Write a one-paragraph excerpt from a Buddhist teaching that would answer: {query}"
)
query_embedding = embed(f"{query}\n\n{hypothetical}")
```

**Применять к:** "explain", "what is", "how does X relate to Y" типам запросов.
**НЕ применять к:** лексическим ("Find MN 10", "Thanissaro Bhikkhu on jhāna").

---

## Компонент 4: LLM Routing

**Модуль:** `src/rag/router.py`

Маршрутизатор определяет сложность → выбирает LLM:

| Тип | LLM | Context size | Cost/1K tokens |
|-----|-----|---|---|
| Простая фактология | claude-haiku-4-5 | 10K | $1/$5 |
| Стандартные вопросы | claude-sonnet-4-6 | 25K | $3/$15 |
| Философские/синтез | claude-opus-4-6 | 50K | $15/$75 |

**Классификатор:** Haiku с system prompt:
```
Classify query complexity: simple | standard | complex
- simple: single fact lookup
- standard: explanation requiring synthesis of 3-5 sources
- complex: philosophical, cross-traditional, requires deep reasoning
Respond with one word only.
```

**Стоимость маршрутизации:** ~$0.0001/запрос (Haiku, ~100 токенов).

---

## Компонент 5: Hybrid Retrieval

**Модуль:** `src/rag/retriever.py`

### Dense (BGE-M3)

Обычные semantic embeddings. 1024 dim, normalized, cosine similarity.

```python
query_dense = bge_m3.encode_dense(query)  # shape: (1024,)
dense_results = qdrant.search(
    collection="dharma_v3",
    query_vector=("dense", query_dense),
    limit=100,
    with_payload=True
)
```

### Sparse (BGE-M3 learned sparse)

Learned sparse vectors — как BM25 но с весами, выученными моделью. Ловит лексические совпадения.

```python
query_sparse = bge_m3.encode_sparse(query)  # dict: {token_id: weight}
sparse_results = qdrant.search(
    collection="dharma_v3",
    query_vector=("sparse", sparse_vector_to_qdrant(query_sparse)),
    limit=100
)
```

### BM25 (Pāli-aware)

**Модуль:** `src/rag/bm25.py`

Используется только для текстов с Pāli терминологией. Кастомный токенайзер:

```python
def pali_tokenize(text: str) -> list[str]:
    # Нормализация диакритики: satipaṭṭhāna ↔ satipatthana
    text = normalize_pali(text)
    # Стандартный word-level tokenize
    tokens = re.findall(r'\w+', text.lower())
    return tokens
```

### RRF Fusion

Reciprocal Rank Fusion объединяет три ранжирования:

```python
def rrf_fusion(rankings: list[list[str]], k: int = 60) -> list[str]:
    scores = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    return sorted(scores, key=scores.get, reverse=True)
```

**k=60** — стандартное значение из литературы.

---

## Компонент 6: Cross-encoder Reranking

**Модуль:** `src/rag/reranker.py`

**Модель:** BGE-reranker-v2-m3 (570M params, Apache 2.0)

**Отличие от bi-encoder:** принимает query и document вместе, выдаёт score релевантности. Точнее, но медленнее — потому используется только на top-100.

```python
pairs = [[query, chunk.text] for chunk in top_100_chunks]
scores = reranker.predict(pairs)  # shape: (100,)
top_10 = sorted(zip(top_100_chunks, scores), key=lambda x: -x[1])[:10]
```

**Latency:** ~300ms на 100 кандидатов (CPU) / ~50ms (GPU).

**Альтернатива:** Cohere Rerank 4 Pro ($2/1K searches, +30-50ms latency но выше качество).

---

## Компонент 7: Context Builder

**Модуль:** `src/rag/context_builder.py`

Задача: превратить top-10 chunks в формат для LLM.

### Parent-Child expansion

Retrieved chunks — children (150 слов). Для LLM отдаём parent (600 слов):

```python
child_chunks = reranker.top_10
parent_ids = set(chunk.parent_id for chunk in child_chunks)
parents = db.fetch_parents(parent_ids)
```

### Форматирование

```markdown
# Context for answering

## Source 1
**Citation:** [source: MN 39, Mahā-Assapura Sutta]
**Translator:** Bhikkhu Sujato
**License:** CC0

<parent chunk text>

---

## Source 2
**Citation:** [source: AN 9.36, Jhāna Sutta]
...
```

**Токены:** обычно ~3000-5000 токенов context для 10 chunks.

---

## Компонент 8: Generation

**Модуль:** `src/rag/generator.py`

### System Prompt

```
You are a knowledgeable assistant specializing in Buddhist teachings,
particularly the Theravada tradition and practical meditation.

CRITICAL INSTRUCTIONS:
1. Answer ONLY from the provided context. Do not add outside knowledge.
2. Every factual claim MUST cite a source using [source: X] format.
3. If context doesn't contain the answer, say "I don't have enough
   information in my sources to answer this confidently" — do not fabricate.
4. Preserve Pāli/Sanskrit terms with proper diacritics (satipaṭṭhāna,
   not satipatthana) when context provides them.
5. When traditions differ (Theravada vs Mahayana), attribute clearly.
6. Respond in the language the user asked in.

User question: {query}

Context from Buddhist sources:
{context}

Provide a clear, accurate answer with citations.
```

### Streaming

```python
async def generate_streaming(query: str, context: str):
    async with anthropic.messages.stream(
        model=routed_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    ) as stream:
        async for text in stream.text_stream:
            yield text
```

### Langfuse трейсинг

Каждый вызов трейсится:
- Input query + retrieved chunks
- Model used, tokens in/out
- Cost
- Latency
- User feedback (если есть)

---

## Компонент 9: Citation Verification

**Модуль:** `src/rag/citations.py`

### Парсинг

Regex ищет `[source: X]` паттерны в ответе:
```python
CITATION_RE = re.compile(r'\[source:\s*([^\]]+)\]')
citations = CITATION_RE.findall(response)
```

### Проверка

Для каждой цитаты:
1. Существует ли source в context?
2. Содержит ли source действительно заявленную информацию? (LLM check, опционально)

```python
for citation in citations:
    if not any(citation in chunk.source_id for chunk in context_chunks):
        # Галлюцинация цитаты!
        log_warning(f"Hallucinated citation: {citation}")
        # Пометить ответ с deprecated цитатой
```

### Метрика

`citation_validity = valid_citations / total_citations`

Цель: >95%

---

## Компонент 10: Cache Save

Если запрос не из кеша и сгенерирован ответ:

```python
await semantic_cache.save(
    query_text=query,
    query_embedding=query_embedding,
    response=response,
    retrieved_chunks=top_10,
    citations=verified_citations,
)
```

---

## Метрики pipeline

### Latency budget (цель)

| Шаг | Target | Actual (v0.3) |
|-----|--------|---------------|
| Language detect | <5ms | 2ms |
| Cache lookup | <50ms | 30ms |
| Query expansion | <100ms | 80ms |
| LLM routing | <200ms | 150ms |
| Hybrid retrieval | <300ms | 250ms |
| Reranking | <400ms | 350ms |
| Context builder | <50ms | 20ms |
| LLM first token | <500ms | 400ms |
| **TOTAL (cache miss)** | **<1600ms** | **~1300ms** |
| TOTAL (cache hit) | <100ms | 60ms |

### Cost per query

| Модель | Avg tokens in/out | Cost/query |
|--------|-------------------|------------|
| Haiku (40%) | 3000/200 | $0.004 |
| Sonnet (50%) | 4000/300 | $0.017 |
| Opus (10%) | 5000/400 | $0.105 |
| **Средневзвешенно** | | **~$0.022** |

С кешем (40% hit): **~$0.013/запрос**

---

## Версионирование коллекций

| Версия | Что нового |
|--------|-----------|
| dharma_v1 | Dense-only BGE-M3 |
| dharma_v2 | + Sparse vectors |
| dharma_v3 | + Contextual Retrieval |
| dharma_v4 | + Parent-child refined |
| dharma_v5 | + Dharmaseed transcripts (Phase 1.5) |

Старые версии хранятся минимум 2 недели после миграции для rollback.

---

## Debugging

### Включить детальное логирование

```bash
export LOG_LEVEL=DEBUG
python -c "from src.rag.pipeline import RAGPipeline; ..."
```

### Langfuse traces

Каждый запрос виден на http://localhost:3000:
- Полный chain вызовов
- Input/output на каждом шаге
- Latency breakdown
- Cost attribution

### Manual testing

```bash
# CLI для быстрой итерации
dharma-rag query "Test question" --debug

# Вывод:
# [Retriever] Got 100 candidates (dense: 100, sparse: 100, BM25: 87)
# [RRF Fusion] Merged to 100 unique
# [Reranker] Top 10 selected
# [Router] Classified as "standard" → claude-sonnet-4-6
# [Generator] 420ms first token, 1.2s complete
# [Citations] 5 citations, all verified ✓
```

---

## Будущие улучшения (Phase 2-3)

1. **HyDE для всех conceptual запросов** (сейчас только selective)
2. **LightRAG** — graph-based retrieval для cross-reference
3. **Multi-vector search** — разные embeddings для разных типов контента
4. **Adaptive top-k** — динамически выбирать top_k на основе query complexity
5. **Fallback chain** через LiteLLM — Claude → OpenAI → local Llama

---

## Ссылки

- [BGE-M3 paper](https://arxiv.org/abs/2402.03216)
- [Anthropic Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
- [RRF original paper](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)
- [HyDE paper](https://arxiv.org/abs/2212.10496)
