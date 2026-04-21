# Dharma-RAG: технический аудит и 14-дневный план запуска

**Важное предуведомление об источниках.** Репозиторий `toneruseman/Dharma-RAG` (согласно указанной дате начала разработки 14 апреля 2026) на момент исследования не отдаётся ни через `web_fetch` (URL не в whitelist инструмента), ни через поисковые индексы (слишком свеж / приватен / не проиндексирован). Поэтому разбор построен на **архитектурном описании из задачи** (README-выжимка от пользователя) и **независимом исследовании альтернатив 2025–2026** через субагентов. Везде, где я опираюсь на «как описано в README», имеется в виду именно эта выжимка; где делаю рекомендацию — она следует из research, не из кода. Если позже откроется доступ к репо, отдельные пункты (особенно про реальное состояние Phase 0 Setup и `pyproject.toml`) нужно будет уточнить.

---

## Часть 0. Общая рамка и главные выводы

Dharma-RAG — это **классический «advanced RAG 2024-vintage» стек**, собранный из компонентов с солидной репутацией: BGE-M3 + BM25 + BGE-reranker-v2-m3 на Qdrant, FastAPI + Langfuse, Claude с Haiku/Sonnet routing. Архитектура разумная, но **консервативная и в ряде мест уже отстаёт от state-of-the-art 2026**. Для MIT-проекта, обещающего «100% free-to-user», самое проблемное место — **Claude в центре генерации** (closed, платно, противоречит OSS-этосу) и **отсутствие в описании contextual retrieval / hierarchical chunking** — самых дешёвых и мощных улучшений для корпусов с высокой ценой галлюцинации (каковой и является Pali Canon).

**Три главные рекомендации, если делать только три:**

1. **Добавить Contextual Retrieval (Anthropic, сентябрь 2024)** уже в Phase 1 — одноразовая препроцессинг-стоимость ~$30 для 56k чанков, выигрыш до **−49% retrieval failures**. Для буддийского корпуса, где чанк теряет контекст суттры/слушателей/нидана-структуры, это не «nice-to-have», а обязательная вещь.
2. **Перейти на BYOK-паттерн (Bring Your Own Key) с OpenRouter/LiteLLM** и добавить open-source default (Qwen3-32B или Llama 3.3 70B через DeepInfra/Groq). Claude оставить как opt-in premium. Иначе «free-to-user» — фикция, потому что кто-то всегда платит.
3. **Golden evaluation set должен появиться в первые 5 дней**, не в финале. Без него все решения по chunking/rerankers/промптам — гадание на кофейной гуще. Реализовать через Ragas `TestsetGenerator` + 30% человеческой верификации ≈ $5 и пара вечеров.

Остальные рекомендации — в деталях ниже.

---

## Часть 1. Критический разбор стека

### A. Retrieval layer

#### A.1. BGE-M3 как выбор embedding-модели

**Что выбрано.** `BAAI/bge-m3`, 568M параметров (XLM-RoBERTa large), 1024-dim dense + sparse lexical + ColBERT multi-vector из одного forward pass, 8192 токена контекста, MIT-лицензия, 100+ языков, MMTEB ≈ 59, MIRACL ≈ 69.

**Сильные стороны.** (1) Единственная открытая модель, дающая **три представления одним inference-проходом** — критично для экономии на больших корпусах. (2) MIT-лицензия, идеально совместима с MIT-лицензией проекта. (3) 8192-токенный контекст позволяет применять **late chunking** (Jina, 2024), где pooling делается после full-document forward pass — значимое улучшение для сутт с длинным наративом и анафорой («he said… the Blessed One answered…»). (4) Нативная поддержка в Qdrant через single-collection named vectors.

**Слабые стороны и риски.**
- **По MMTEB уже уступает 2025-поколению на 5–11 п.п.** Top-1 на MMTEB в июне 2025 — **Qwen3-Embedding-8B** с 70.58, Qwen3-4B — около 69.5, при MMTEB ≈ 59 у BGE-M3. То есть вы закладываетесь в архитектуру 2024 года.
- **Pali-терминология — OOV-случай.** XLM-RoBERTa токенайзер бьёт `saṃsāra` / `paṭicca-samuppāda` на суб-токены хаотично; dense-вектор «размазывается», sparse ловит только те токены, что были в обучении. Это как раз оправдывает третий канал BM25 (см. A.2), но также означает, что **даже идеальный BGE-M3 даст потолок качества ниже, чем на нормальном английском**.
- **Лицензионная справка.** MIT — это лицензия BAAI; сам vocabulary и Deep Tuning Data — proprietary. Для коммерческого использования проблем нет, но форка модели с дообучением на собственных буддийских данных сделать нетривиально без доступа к их тренировочному пайплайну.

**Сравнение с альтернативами (апрель 2026).**

| Модель | Params | Dim | Ctx | Лицензия | MMTEB | Комментарий для Dharma-RAG |
|---|---|---|---|---|---|---|
| **BAAI/bge-m3** | 568M | 1024 | 8192 | MIT | ~59 | текущий выбор; dense+sparse+colbert; стабильный 2024-baseline |
| `intfloat/multilingual-e5-large-instruct` | 560M | 1024 | 512 | MIT | ~63 | выше качество, но 512 ctx убивает long-doc stories |
| `jinaai/jina-embeddings-v3` | 570M | 32–1024 (Matryoshka) | 8192 | **CC-BY-NC** | ~54 multi | лицензия несовместима с free-to-user commercial |
| Cohere embed-multilingual-v3 | proprietary | 1024 | 512 | API-only | n/a | closed, платно |
| OpenAI text-embedding-3-large | proprietary | 3072 | 8191 | API-only | ~64.6 | closed, слабый long-ctx |
| **Qwen/Qwen3-Embedding-8B** | 8B | до 4096 | 32k | Apache 2.0 | **70.58 (#1)** | лучшее качество, но 10× медленнее на inference |
| **Qwen/Qwen3-Embedding-4B** | 4B | 2560 | 32k | Apache 2.0 | ~69.5 | **sweet spot** — +10 п.п. MMTEB за цену re-embedding |
| `Qwen/Qwen3-Embedding-0.6B` | 0.6B | 1024 | 32k | Apache 2.0 | ~64.3 | дешёвая замена BGE-M3 dense, но нет sparse |
| `nomic-embed-text-v1.5` | 137M | 768 | 8192 | Apache 2.0 | EN only | слабый на multilingual |
| `Alibaba-NLP/gte-multilingual-base` | 305M | 768 | 8192 | Apache 2.0 | ~58 | дешёвый, есть dense+sparse |
| Snowflake `arctic-embed-l-v2.0` | 568M | 1024 MRL | 8192 | Apache 2.0 | ~55 | MRL index компактнее |

**Рекомендация.** **Оставить BGE-M3 для Phase 1 MVP** — он даёт максимум функциональности на единицу сложности и MIT-чистый. **В Phase 2 провести A/B на Qwen3-Embedding-4B** — это **realistic upgrade path** (+5–7 п.п. NDCG@10), но он требует отдельного BM25-движка (Qwen sparse не генерирует) и re-embedding корпуса. Переезд на 8B — overkill и экономически не оправдан при 56k чанков. Jina v3 отклонить из-за CC-BY-NC.

#### A.2. Hybrid retrieval (dense + sparse + BM25)

**Тройной гибрид действительно оправдан, но с оговоркой.** Классический аргумент «BGE-M3 sparse уже перекрывает BM25» справедлив для латиницы без диакритики. Для Pali-терминов (`ṃ, ñ, ṭ, ḍ, ā, ī, ū`) это не так: XLM-R токенайзер лотерейно бьёт эти формы, а реальные запросы пользователей приходят с **непредсказуемой нормализацией** (`Saṃyutta` vs `Samyutta` vs `Samyutta Nikaya` vs `SN`). Нужен **BM25 с ICU unicode normalization + diacritic folding** (NFKD + strip combining marks) — именно это даёт +1–2 NDCG сверх dense+sparse для Pali-запросов.

**Fusion-стратегии.** Reciprocal Rank Fusion (RRF, k=60) — безопасный дефолт и стандарт в Qdrant, Elasticsearch, OpenSearch. Weighted RRF даёт управляемость, но требует калибровки per-corpus. DBSF (Distribution-Based Score Fusion, Qdrant-специфичный) устойчивее на heavy tails. **Рекомендация для Dharma-RAG:** RRF с весами `[dense 1.0, sparse 0.8, bm25 0.6]` — компромисс между простотой и контролем. Переключать на weighted linear только если eval-set покажет plateau на RRF.

**Альтернативы, которые я бы отклонил:**
- **SPLADE++** — формально SOTA на some-benchmarks, но storage overhead 5–10× и sparse-vocab привязан к BERT-tokenizer → нет преимущества перед sparse-каналом BGE-M3.
- **ColPali** (Vision-LLM over PDF patches) — только для визуально-насыщенных PDF с таблицами/диаграммами. Плейн-текст сутт этого не требует.
- **Pure ColBERT** как единственный ретривер — отличное качество OOD, но 10–50× storage overhead. Реалистично использовать только ColBERT-режим BGE-M3 как опциональный rescore между sparse и reranker.

#### A.3. BGE-reranker-v2-m3 vs альтернативы

| Reranker | Params | Ctx | Лицензия | Качество (Hit@1 proxy) | Latency на паре |
|---|---|---|---|---|---|
| **BAAI/bge-reranker-v2-m3** | 568M | 8192 | MIT | **baseline** BEIR ~56.5 NDCG | GPU 50–80 ms, CPU 300–600 ms |
| Cohere rerank-3.5 | closed | 4096 | API | +3–5 п.п. над baseline | ~600 ms managed |
| `jinaai/jina-reranker-v2-multilingual` | 278M | 1024 | **CC-BY-NC** | SOTA AirBench | 15× быстрее bge-v2-m3 |
| jina-reranker-m0 | 2.4B | 10k | CC-BY-NC | BEIR 58.95, MIRACL 66.75 | ~300 ms GPU |
| **Qwen/Qwen3-Reranker-4B** | 4B | 32k | Apache 2.0 | лучший open-multi | высокая |
| Qwen3-Reranker-0.6B | 0.6B | 32k | Apache 2.0 | +2 п.п. над BGE-reranker-v2-m3 | средняя |
| mxbai-rerank-v2-xsmall | 70M | 512 | Apache 2.0 | слабый Hit@1 ~65% | очень быстрый |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | 22M | 512 | Apache 2.0 | устарел, EN-only | <10 ms |

**Рекомендация.** **BGE-reranker-v2-m3 оставить как default в Phase 1**; после того как golden eval set наберётся, провести **A/B с Qwen3-Reranker-0.6B** (MIT-совместимая Apache 2.0, +2–3 NDCG, сопоставимая по размеру) и **Qwen3-Reranker-4B** (если есть GPU). Jina-v2 отклонить по лицензии, Cohere — по «closed+платно». Re-rank top-30…50 кандидатов (не 20), потому что для Pali-OOV retrieval-failures выше и истинный ответ чаще лежит на 20–50 позиции.

#### A.4. Chunking — самое слабое место текущего плана

Из описания стека не видно, чтобы chunking был адаптирован под **структуру суттр**. Это критичный gap. Основные проблемы дефолтного `RecursiveCharacterTextSplitter` на Pali Canon:

1. **Boilerplate / stock formulas** (`Evaṃ me sutaṃ. Ekaṃ samayaṃ Bhagavā...`) повторяется в тысячах сутт дословно. Без dedup dense-retriever ранжирует случайные сутты вверх просто по наличию вступительной формулы.
2. **Pericopes** (satipaṭṭhāna-формула, jhāna-формула, bojjhaṅga-формула) встречаются сотнями раз — без pericope-aware boundaries формула рвётся посреди и теряет семантику.
3. **Анафорическая плотность.** Значительная часть сутт — диалог, где субъект введён в вводной и дальше — `he said, he replied, they answered`. Fixed-size chunker отрывает реплики от говорящего.

**Рекомендуемая стратегия (в порядке приоритета):**

1. **Structural chunking по sutta-boundaries** (SuttaCentral JSON даёт `<section>`/`<paragraph>` разметку). Chunk = параграф, с метаданными `{sutta_uid, nikaya, speaker, audience, pericope_id}`. Это базовый bottom.
2. **Hierarchical / parent-document retrieval.** Индексируем маленькие child-чанки (≈384 токенов) для точного matching, при ответе в LLM-контекст подставляем parent (полная сутта или смысловая секция ≈1024–2048 токенов). Крупное улучшение качества ответа при почти нулевой стоимости.
3. **Contextual Retrieval** (Anthropic, Sep 2024). Для каждого чанка LLM генерирует 50–100-токенный саммари («This passage is from MN 10 Satipaṭṭhāna Sutta, where the Buddha instructs monks on the four foundations of mindfulness...») и добавляет его к чанку **до** embedding и BM25-индексации. Опубликованный выигрыш на codebases/fiction/ArXiv — **−35% failure при контекстных эмбеддингах, −49% при + contextual BM25, −67% с reranker**. Для Pali Canon эффект ожидаю особенно сильным. Стоимость: ~$30 одноразово (Haiku 4.5 + prompt caching).
4. **Late chunking** (Jina, 2024). Full-sutta forward pass через BGE-M3 (до 8192 ctx), затем mean-pool по span-ам чанков. Сохраняет long-range dependencies. Нулевая дополнительная стоимость (просто pooling другой).
5. **Pericope-aware dedup / MMR diversification** в post-retrieval. Поле `pericope_id` в metadata, в MMR штраф за одинаковые pericope_id в top-k. Иначе десять сутт откроются одним и тем же jhāna-пассажем.
6. **HyPE (Hypothetical Prompt Embeddings, 2025).** Офлайн генерация 3–5 «вопросов, на которые этот пассаж отвечает», эмбеддинг вопросов вместе с чанком. Превращает asymmetry `query↔doc` в symmetry `query↔query`. В бенчмарках precision@k +42 п.п. Стоимость: ~$30–50 одноразово.

**Chunk size:** для MVP — **384–512 токенов + 15% overlap**. Выше 1024 растворяет уникальные пассажи в boilerplate; ниже 256 рвёт pericope.

#### A.5. Query processing

HyDE — **не дефолт**, а условный fallback когда top-1 dense score ниже порога (~0.55). Дефолт — **Multi-query с Pali-expansion** (LLM генерирует 3 перефразировки, одна обязательно включает Pali/Sanskrit synonyms). Стоит ~$0.001 на запрос Haiku, стабильный выигрыш +3–8% recall. Query routing (Vinaya/Sutta/Abhidhamma) — overkill для MVP, лучше реализовать как metadata-filter extraction через structured output.

---

### B. Vector database (Qdrant vs альтернативы)

**Вердикт: Qdrant — правильный выбор, мигрировать не нужно.** Но обоснование важнее вердикта.

**Сравнительная таблица (апрель 2026, для корпуса 56k–500k × 1024dim):**

| Engine | Hybrid native | Sparse BGE-M3 | Ops overhead | Licence | Для Dharma-RAG |
|---|---|---|---|---|---|
| **Qdrant 1.16+** | ✅ Universal Query API + RRF/DBSF | ✅ IDF modifier с 1.10, first-class | Low (single Rust binary) | Apache 2.0 | **best fit** по фичам для BGE-M3 |
| Weaviate 1.27+ | ✅ BM25 + vector | ⚠ слабее | Medium | BSD-3 | schema-heavy, overkill |
| Milvus 2.5 | ✅ | ✅ Sparse Float Vector | **High** (etcd, Pulsar, MinIO) | Apache 2.0 | overkill до 10M+ |
| pgvector 0.8 + ParadeDB | ✅ через SQL RRF | через pg_search | Low если уже есть PG | PostgreSQL / **AGPL v3** | AGPL для pg_search — юр. оговорка для MIT-проекта |
| pgvectorscale | ❌ только dense | ❌ | Low | PostgreSQL | 471 QPS @99% recall на 50M (Tiger bench May 2025), но только dense |
| Vespa | ✅ индустриальный | ✅ | **Very high** (JVM, YQL) | Apache 2.0 | operational overhead непропорционален |
| LanceDB 0.15+ | ✅ FTS + vector | ✅ | **Zero** (embedded) | Apache 2.0 | идеален для 56k, но не для multi-instance |
| Chroma | ⚠ | ❌ | Zero | Apache 2.0 | только прототип |

**Особо про Qdrant vs pgvector (+ParadeDB).** На вашем масштабе (56k → 200k) разница в latency **незаметна** — все dense-only решения дают <50 ms p99. Реальный bottleneck — embedding inference BGE-M3 на CPU (50–300 ms). Выбор определяется не скоростью, а:

- **Нативность BGE-M3 sparse.** Qdrant — один из немногих DB, где BGE-M3 работает «из коробки»: `SparseVectorParams(modifier=Modifier.IDF)` в Qdrant 1.10+, `FusionQuery(RRF)` в 1.10+, `prefetch` с dense+sparse+colbert в одном запросе. В pgvector sparse через отдельный `sparsevec` тип появился в 0.7, но без IDF automation; нужен собственный BM25 через ParadeDB.
- **Лицензия.** Qdrant Apache 2.0 — чисто MIT-совместим. **pg_search (ParadeDB) под AGPL v3** — для self-hosted проекта без модификации pg_search это ОК, но если кто-то захочет форкнуть pg_search — AGPL обязывает открыть. Для чистого MIT-этоса это cognitive dissonance.
- **Размер данных.** 56,684 × 1024 × float32 ≈ **232 МБ** dense, <500 МБ с sparse. Это помещается в RAM любого решения. Даже после Dharmaseed (~46k лекций × N чанков) — 200k–500k чанков, всё ещё <2 ГБ.

**Когда мигрировать:**
- **>5M чанков + GPU index** → Milvus/Zilliz (CAGRA).
- Уже есть Postgres с user-данными и нужна транзакционность «документ↔вектор» → pgvector 0.8 + pg_search.
- Хочется zero-ops single-process → LanceDB embedded.

Для Dharma-RAG на текущем горизонте — **оставайтесь на Qdrant**. Upgrade до 1.16+ для ACORN на фильтрованных запросах, включите IDF modifier, используйте `prefetch + FusionQuery` вместо клиентской склейки.

---

### C. Generation layer

Самое спорное место в архитектуре. **Claude-в-центре-генерации противоречит обещанию «100% free to user» и MIT-этосу.** Анализ должен начинаться с этого.

**Актуальные цены Claude (апрель 2026, после весеннего relaunch):**

| Модель | Input $/1M | Output $/1M | Ctx | Cache hit input |
|---|---|---|---|---|
| Haiku 4.5 | $1.00 | $5.00 | 200K | $0.10 |
| Sonnet 4.6 | $3.00 | $15.00 | 1M flat | $0.30 |
| Opus 4.6 | $5.00 | $25.00 | 1M flat | $0.50 |

**Economics для типичной нагрузки (1000 RAG-запросов/день, 4K контекст, 500 токенов ответа):**

| Сценарий | $/день | $/месяц |
|---|---|---|
| All Sonnet 4.6 без кэша | $19.5 | ~$585 |
| All Sonnet 4.6 + prompt cache (80% hit) | $10.86 | ~$326 |
| All Haiku 4.5 без кэша | $6.5 | ~$195 |
| **Routing 70/20/10 Haiku/Sonnet/Opus + cache** | ~$5.20 | ~$156 |
| **Llama 3.3 70B через DeepInfra ($0.35/M)** | $1.58 | **~$47** |
| **Qwen3-32B self-host на Hetzner GEX44** | ~€6/день амортизация | ~€184 фикс + energy |

Цифры показывают: даже при наилучшем routing Claude дороже открытого стека в 3–4×. Для OSS-проекта это существенно.

**Паттерны Haiku/Sonnet routing.** Три подхода:
1. **Cheap-first classifier** (Haiku классифицирует запрос на factoid/synthesis/interpretive за ~100 токенов, далее выбирает модель). Ровно дёшево, но добавляет +100–200 ms latency.
2. **Confidence-based escalation.** Haiku отвечает первым, если self-eval confidence <0.7 или groundedness-check <70% покрытия — повтор на Sonnet. Экономит ~50% vs all-Sonnet, теряет <2% качества.
3. **Question-type routing** (прямое правило: цитаты → Haiku, сравнения → Sonnet, философия/медитация → Opus).

Для Dharma-RAG рекомендую **подход 2 + groundedness-check через cosine между ответом и top-k retrieved chunks** (bge-m3 cosine <0.55 → escalate).

**Открытые альтернативы:**

| Модель | Лицензия | Active params | Ctx | RAG faithfulness | Hardware (FP8) |
|---|---|---|---|---|---|
| **Qwen3-32B** | **Apache 2.0 ✓** | 32B dense | 131K | хороший, дефолт 2026 | 1× H100 |
| Qwen 2.5 72B Instruct | Qwen (commercial OK) | 72B dense | 128K | топ среди open, лучше multilingual | 1× H100 |
| Llama 3.3 70B Instruct | Llama 3.3 (permissive) | 70B dense | 128K | baseline FaithJudge | 1× H100 |
| Llama 4 Scout | Llama 4 | 17B/109B MoE | 10M | средне, хорош для long-ctx | 1× H100 |
| DeepSeek V3.2 | DeepSeek permissive | 37B/671B MoE | 128K | чуть ниже Llama 3.3 на faithfulness | 8× H100 |
| DeepSeek R1 | MIT ✓ | 37B/671B | 128K | self-catches halu в `<think>`, overkill | 8× H100 |

**Cheap API для пользователей без GPU** (Llama 3.3 70B):

| Provider | In/M | Out/M | TPS | TTFT | Заметки |
|---|---|---|---|---|---|
| **Groq** | $0.59 | $0.79 | 293–315 | 0.8s | LPU, лучший для voice |
| **DeepInfra Turbo** | $0.15–0.35 | $0.35 | 27–40 | 1.2s | дешевле всех |
| Together AI | $0.88 | $0.88 | 45 | 1.0s | fine-tune |
| Fireworks | $0.70 | $0.70 | 50 | 0.6s | low TTFT |
| **Cerebras** | $0.60 | $0.60 | 450+ | 0.35s | макс throughput |

**Anthropic Citations API** (GA с января 2025) — отдельное преимущество Claude: `"citations": {"enabled": true}`, char-level спаны, `cited_text` не тарифицируется как output (экономия 15–25%). Для Dharma-RAG, где атрибуция доктринально критична, это реальная ценность.

**Конкретная рекомендация:**
1. **Абстрагировать LLM через LiteLLM или OpenRouter с первого дня.** Не жёстко `anthropic.messages.create`.
2. **Default free-to-user backend:** Llama 3.3 70B через DeepInfra ($0.35/M, ~$47/мес на 1000 req/day). Или Groq для voice-mode (300+ TPS).
3. **Premium opt-in:** Claude Sonnet 4.6 + Citations API, пользователь вводит свой API-ключ (BYOK).
4. **Routing:** Haiku 4.5/Qwen3-8B classifier → Llama 3.3 70B/Sonnet 4.6 default → Opus 4.6/DeepSeek R1 для интерпретативных.
5. **Citation-prompt:** XML-теги `<cite source="MN10" loc="12.3-5"/>` для открытых моделей; нативные Citations API при Claude.

---

### D. Backend & API

**FastAPI + Uvicorn — адекватный выбор.** Python-ecosystem standard для async RAG. Критика минимальная:

- **SSE через EventSourceResponse** (встроен в FastAPI 0.115+) корректно для streaming. Gotchas: `X-Accel-Buffering: no` для Nginx, heartbeats каждые 15–30 с, `request.is_disconnected()` для cancel.
- **Не делать inference внутри FastAPI-процесса.** BGE-M3/reranker — это блокирующий torch, а не asyncio. Вынести в отдельный сервис (TEI или Infinity). Иначе streaming SSE ломается.
- **Uvicorn vs Granian.** Apr 2026 бенчмарки: Uvicorn (httptools) и Granian ≈ равны по RPS (~51k для ASGI), различие в p99 (Granian немного лучше). Granian — drop-in replacement; можно протестировать при проблемах с tail latency.

**Очереди для транскрипции Dharmaseed.** У вас ~46k лекций, которые надо прогнать через Whisper — classic use-case для очереди:

| Библиотека | Async-native | Для Dharma-RAG |
|---|---|---|
| Celery | ❌ sync-first | tried-and-true, но overhead и сложно в async |
| ARQ | ✅ asyncio | простой, Redis backend |
| **Taskiq** | ✅ asyncio, FastAPI-like DI | **лучший выбор для async FastAPI 2026** |
| Dramatiq | ❌ sync | быстрый, стабильный |
| Procrastinate | ✅ asyncio, Postgres-based | если нет Redis |

**Caching.** **Redis Semantic Cache (RedisVL)** — правильный выбор, если Redis уже есть (а он нужен для Langfuse и очереди). Для многоязычного Q&A (один вопрос на EN и RU — один embedding) даёт большой boost. GPTCache — больше фич, но сложнее.

**Observability — Langfuse vs Phoenix.**

| Критерий | Langfuse v3 | Phoenix (Arize) |
|---|---|---|
| Лицензия | MIT ✓ | ELv2 |
| Self-host complexity | **Medium** (Postgres + ClickHouse + Redis + S3 + 2 контейнера) | **Low** (single Docker + Postgres) |
| Min RAM для prod | ~16 GB | ~2 GB |
| Tracing | OTel-compatible | OpenInference native |
| Prompt versioning | ✅ + playground | ❌ |
| Pre-built RAG evals | через LLM-as-judge | **✅ (hallucination, groundedness, context relevance)** |

**Честная критика.** Langfuse v3 — это **4 сервиса + ClickHouse**. Для маленького self-hosted проекта это тяжёлый overhead. Если prompt versioning критичен — оставьте Langfuse. Если нет — Phoenix (single container + Postgres) экономит ресурсы и даёт из коробки pre-built RAG evals, что для буддийского корпуса с высокой ценой галлюцинаций прямо релевантно.

**Рекомендация:** начать с Phoenix (Day 1–5 MVP), мигрировать на Langfuse если потребуется prompt versioning. Это перевернёт порядок в текущем плане, но даст быструю observability без ops overhead.

**Model serving.** **TEI (Text Embeddings Inference от Hugging Face)** — production-grade, token-based dynamic batching, поддерживает BGE-M3 dense+sparse и BGE-reranker-v2-m3. Single Docker:

```bash
docker run --gpus all -p 8080:80 \
  -v $PWD/data:/data \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-m3
```

**Infinity** (Michael Feil) — multi-model в одном процессе; полезен если нужны BGE-M3 + reranker + ColBERT одновременно. **FastEmbed** — только для dev/prototyping. **Ollama** для embeddings есть, но BGE-M3 sparse не first-class.

---

### E. Frontend & UX

HTMX + SSE для MVP — **прагматично и правильно для solo-разработки**. Главный плюс: streaming response с минимумом JS, тот же серверный рендер. Главный минус: когда понадобится сложная клиентская логика (filter panel для сутт, diff между переводами, inline цитата с tooltip) — придёт SvelteKit. Переход на SvelteKit + Capacitor на Phase 2–3 — разумный; **не стоит начинать с SvelteKit сразу**, потому что MVP-цель — не UI, а проверка качества retrieval.

**UX для grounded RAG по буддийским текстам (специфические требования):**
- **Цитаты с palm leaf reference** (`MN 10 §12.3`) должны быть кликабельны и раскрывать исходный текст сутты целиком (не только retrieved chunk).
- **Confidence indicator** не как число 0.87, а как три уровня: *«direct citation»* / *«synthesized from sources»* / *«interpretive, verify with teacher»*.
- **Parallel texts:** если есть Pali original + English translation — показать side-by-side.
- **Deference language.** UI copy должен избегать тона «AI teacher». Формулировки: «Sources suggest…», «The Pali Canon speaks of… (MN 10)», не «The Buddha says…» в первом лице.
- **Terminology tooltip.** При наведении на Pali термин (`jhāna`) — glossary popover с этимологией, диапазоном переводов, ссылками.
- **Anti-misuse guardrail в UI.** Если вопрос содержит suicide-/crisis-/medical-triggers — фиксированный refusal с redirect на crisis helplines и рекомендацией живого учителя, независимо от retrieval.

**Многоязычный UX.** EN + RU — разумный минимум. Критично: **Pali термины не переводить** — ни в UI-копии, ни в ответах. `jhāna` остаётся `jhāna` (не «погружение»), по желанию с русским пояснением в скобках. Иначе теряется связь с первоисточниками.

---

### F. Voice pipeline

**Pipecat (BSD-2) — правильный выбор orchestration**, лучше LiveKit Agents и существенно лучше OpenAI Realtime / Gemini Live для open-source RAG:

| Критерий | Pipecat | LiveKit Agents | OpenAI Realtime | Gemini Live |
|---|---|---|---|---|
| Лицензия | BSD-2 ✓ | Apache 2.0 ✓ | proprietary | proprietary |
| Self-host | ✓ | ✓ | ✗ | ✗ |
| E2E latency | 600–900 ms cascading | 500–800 ms | ~500 ms S2S | ~500 ms S2S |
| Provider swap | одной строкой | одной строкой | невозможно | невозможно |
| Подходит Dharma | ✅ best fit | ✅ если multi-user WebRTC | ❌ теряется grounded RAG | ❌ |

Причина против S2S-моделей (OpenAI Realtime/Gemini Live): в speech-to-speech архитектуре **нельзя вклинить retrieval/citation шаг** — модель отвечает по своим весам, теряется ground-truth. Cascading STT → RAG → LLM → TTS, как у Pipecat, — единственный способ сохранить доктринальную точность.

**STT для Pali.** Ни один cloud STT не имеет native Pali модели. Подходы:
- **Whisper large-v3-turbo + `initial_prompt`-глоссарий** (`jhāna, anattā, samādhi, paṭicca-samuppāda, satipaṭṭhāna, dukkha, ānāpānasati`). Whisper в pre-training видел много буддийских текстов, лучшее покрытие romanized Pali. Через Groq — ~free tier, ~$0/hr, 216× real-time.
- **Deepgram Nova-3 + Keyterm Prompting** (до ~100 терминов, self-serve) — для real-time voice с <300 ms SLA.

**TTS — действительно сложная проблема.** Без ручной разметки ни один open-source TTS корректно не выговаривает `paṭiccasamuppāda`. Решение — **Pali phonemizer pre-processor** (rule-based G2P: `paṭicca → pa-ti-ccha`, `jhāna → jhaa-na`) + Piper (MIT) либо ElevenLabs с uploaded pronunciation dictionary.

| TTS | Диакритика | IPA control | Лицензия | Для Dharma |
|---|---|---|---|---|
| **Piper (VITS) + espeak-ng** | через phonemizer | ✅ IPA | **MIT ✓** | **default self-host** |
| ElevenLabs Multi v2 | игнорирует, но есть IPA dict | ✅ | proprietary | premium opt-in |
| Cartesia Sonic 2 | phoneme prompts | ✅ | proprietary | быстрый альт |
| F5-TTS | нет IPA control by design | ❌ | **CC-BY-NC** | несовместимо с MIT |
| XTTS v2 | частично | ограниченно | **CPML** | несовместимо с MIT |
| OpenVoice v2 | теряется | ❌ | MIT ✓ | плохое качество |

**On-device (Phase 3 mobile).** Sherpa-ONNX (Apache 2.0) + Whisper-base int8 (~60 MB) + Piper с Pali-G2P. Реальные цифры: iPhone 15 Pro RTF 0.05 (20× real-time), Pixel 8 RTF 0.03 с NNAPI, battery <1–2%/час. Вполне реалистично для локальной voice-mode на смартфонах 2024+.

---

### G. Knowledge Graph (Phase 3)

**Честный вопрос: нужен ли KG для этого use case?** Моя оценка: **~15–25% query требуют graph traversal**:

| Тип query | Пример | Нужен KG? |
|---|---|---|
| Цитатный | «Что в MN 10 про дыхание?» | Нет, BM25+dense |
| Тематический | «Что такое upekkhā?» | Нет, dense + RAPTOR summary |
| Сравнительный | «Anatta vs Advaita» | Частично |
| **Lineage/multi-hop** | «Учителя Thanissaro Bhikkhu и их корни» | **Да** |
| **Causal/doctrinal** | «Какое звено paṭicca-samuppāda ведёт к dukkha?» | **Да** |
| Cross-tradition | «Параллели Zen/Theravāda по anicca» | Да |

**Фреймворки (сравнение зрелости апрель 2026):**

| Framework | Лицензия | Adoption | Сила | Слабость |
|---|---|---|---|---|
| **LightRAG (HKU)** | MIT | ~20k⭐, активная разработка | dual-level retrieval, инкрементальные апдейты без re-index | менее rich hierarchy, чем MS GraphRAG |
| Microsoft GraphRAG | MIT | много POC, мало prod | community detection (Leiden), глобальные саммари | **часто хуже vanilla RAG на факт-QA**: в бенчмарках Han et al. 2025 (arXiv 2506.05690) проигрывает -13.4% accuracy на HotpotQA; дорог на build |
| nano-graphrag | MIT | ~3k⭐, используется стартапами | <1000 LoC, hackable | минимализм, требует доп. работы |
| LlamaIndex PropertyGraphIndex | MIT | зрелый, много интеграций | schema-guided, hybrid vector+graph | boilerplate |
| Neo4j + custom | commercial/community | enterprise-grade | полный контроль, GDS-алгоритмы | требует graph-engineering |

**Рекомендация: LightRAG + RAPTOR как комплементарные слои** (RAPTOR для тематических/нарративных query, LightRAG для сущностей/связей). **Не Microsoft GraphRAG** — он дорог (~$140–400 на 56k чанков при полной пайплайне) и часто уступает vanilla RAG на факт-query, что характерно для Dharma Q&A.

**Стоимость построения на 56k чанков:**

| Модель | Full GraphRAG | LightRAG (~40%) |
|---|---|---|
| GPT-4o-mini | ~$52 | ~$21 |
| DeepSeek V3 | ~$95 | ~$38 |
| Claude Haiku 4.5 | ~$393 | ~$157 |
| Local Qwen 2.5-72B | $0 + 2–3 недели wall-time | — |

Реалистичная one-time стоимость для Dharma-RAG — **$20–60 на gpt-4o-mini + LightRAG**.

**Существующие буддийские онтологии для reuse:**
- **SuttaCentral JSON-first API** + UID-система (`mn10`, `an3.65`) — canonical IDs как основа графа.
- **BDRC (Buddhist Digital Resource Center)** — OWL-ontology на GitHub `buda-base/owl-ontology`, SPARQL-эндпоинт, 28M страниц, lineage chains, golden standard для Tibetan.
- **DILA Authority Database** (Dharma Drum) — 23k teacher-student lineage chains, seed-edges для lineage-графа.
- **FoJin** (xr843/fojin) — готовый агрегатор 503 источников с BGE-M3 эмбеддингами, 31k entities/28k relations, Apache 2.0. **Можно частично reuse** с соблюдением sub-licenses.

**Практичный путь:** импортировать SuttaCentral UID как canonical IDs → link к BDRC через `owl:sameAs` → DILA lineage как seed-edges → LLM-extraction добавляет relations между концептами (anicca, dukkha, anattā и их отношения к nidānas).

---

### H. Evaluation

**Golden eval set должен появиться не позднее Day 5, иначе вся оптимизация retrieval — слепая.**

**Stack:**

| Tool | Лицензия | Для Dharma |
|---|---|---|
| **Ragas** | Apache 2.0 | faithfulness/answer_relevancy/context_precision/recall; TestsetGenerator (knowledge-graph-based); **быстрый старт** |
| **DeepEval** | Apache 2.0 | 50+ метрик, Pytest-native, CI quality-gates; G-Eval, DAG metric; **CI-blocking** |
| TruLens | MIT | OpenTelemetry + feedback functions; после Snowflake-acq momentum снизился |
| Phoenix evals | ELv2 | OTel traces + hallucination evals; хороши как dev-loop |
| LangSmith | commercial | deep LangChain; vendor lock |

**Рекомендация:** **Ragas (метрики + testset generation) + DeepEval (Pytest CI gates в GitHub Actions) + HHEM-2.1-Open для hallucination checks офлайн** (Vectara, Apache 2.0, CPU-friendly, <600 МБ RAM, multilingual).

**Retrieval metrics:** Recall@10, MRR@10, NDCG@5. Цели: Recall@10 >0.85, NDCG@5 >0.70. RAG pipeline: retriever k=20–30 → reranker → top-5 в LLM context.

**Golden test set без buddhology PhD (workflow):**
1. **Synthetic gen через Ragas TestsetGenerator** из corpus; distribution 50:25:25 = simple:reasoning:multi-context. Стоимость ~$2–5 на 200 Q через gpt-4o-mini.
2. **Cross-model check:** те же Q на gpt-4o-mini + Claude Haiku, оставить только Q с ≥70% semantic overlap.
3. **Canonical anchors:** ~30% test-сета — из известных парных текстов (SuttaCentral parallels MN ↔ MA, quotes Ajahn Chah с известным источником) → автоматический ground-truth.
4. **Human verification subset:** 50–80 Q отмечаются волонтёром-практиком (не PhD) по 3-балльной шкале `correct / cites-right / hallucinated`. Время: 2–3 часа.
5. **Taxonomy coverage:** citation/thematic/comparative/lineage/ethical ≈ 40/30/10/10/10.

**Hallucination eval:**

| Подход | Latency | Cost | Accuracy |
|---|---|---|---|
| **HHEM-2.1-Open** (Vectara) | 1.5 s на 2K токенов CPU | $0 | сравним с GPT-4 |
| LLM-as-judge (GPT-4o) | 2–5 s | ~$0.002/eval | хорошо, нестабильно |
| Ragas faithfulness | LLM-based | $ | декомпозиция на statements |
| NLI-based (DeBERTa-v3-mnli) | ~100 ms CPU | $0 | быстрый baseline |

**Attribution check:** regex-парсинг `<cite source=... loc=.../>` → проверка что UID есть в retrieved_context → fail если нет. Для Dharma это важнее, чем для general RAG.

---

### I. Deployment & DevOps

**Free-to-user cost model:** единственный неустранимый cost — LLM generation. Вектора/rerank/eval могут быть $0.

**Инфраструктурные опции (апрель 2026, с учётом **Hetzner +30–35% с 1 апреля 2026**):**

| Опция | Спецификация | Цена | Use case |
|---|---|---|---|
| **OCI Always Free (ARM A1.Flex)** | 4 Ampere cores, 24 ГБ RAM, 200 ГБ, 10 ТБ egress/мес | **$0 навсегда** | MVP/staging; возможно production CPU-RAG при ≤1–2 RPS |
| **Hetzner AX42** | Ryzen 7700, 64 ГБ RAM, NVMe | €39/мес | **основной prod: FastAPI + Qdrant + BGE-M3 CPU + reranker** |
| **Hetzner AX52** | Ryzen 7950, 128 ГБ RAM | €79/мес | запас на рост |
| **Hetzner GEX44** | RTX 4000 SFF Ada 20 ГБ | €184/мес + €79 setup | **batch transcription, KG-build, periodic reindex** |
| Fly.io | shared-cpu, GPU machines | pay-per-use | edge-proxy |
| **RunPod spot A40** | $0.39/h | per-hour | transcription bursts |
| **Modal A10** | $1.10/h | per-second | serverless bursts |
| **Groq Whisper-large-v3-turbo** | $0.04/hr audio | per-min | managed, 216× RT |

**Достаточен ли OCI Always Free для Dharma-RAG MVP?** Моя оценка — **да, до ~1–2 RPS:**

| Компонент | RAM | Fit |
|---|---|---|
| Qdrant (56k × 1024d + HNSW) | 1–2 ГБ | ✅ |
| FastAPI + Uvicorn | 300 МБ | ✅ |
| BGE-M3 CPU inference | 4 ГБ рабочих | ✅, 0.3–1 с/query |
| BGE-reranker-v2-m3 CPU | 3 ГБ рабочих | Tight, но работает; 1–3 с на rerank |
| **Idle total** | ~7–9 ГБ | ✅ комфортно |
| **Peak (2 concurrent)** | ~14–18 ГБ | ✅, близко к лимиту |

**Реальный QPS на CPU (ARM Ampere 4c):**
- BGE-M3 dense query: 40–80 ms короткий, 150–300 ms длинный → 5–15 QPS.
- BGE-reranker-v2-m3 на 10 пар: 400–700 ms → viable, но bottleneck.
- С batching (при bulk embed корпуса): 50–100 chunks/sec.

**Кто платит за LLM:**
1. **BYOK (рекомендую)** — пользователь вводит свой OpenRouter/Anthropic ключ в UI; сервер не хранит. Паттерн LibreChat/open-webui/Aider.
2. Self-host на pooled GPU (GEX44 + vLLM + Qwen3-32B) — €184/мес фикс, требует donation/grant.
3. Freemium + rate-limit (5 Q/day для anonymous, больше для donors).
4. OpenRouter credits, спонсированный проектом (дорого при росте).

**GitHub Actions без GPU:**
- **Unit:** chunking boundaries, citation-parser, UID-validator, metadata extractors.
- **Integration:** Qdrant Docker service + mini-corpus (50 chunks) + all-MiniLM-L6-v2 (80 MB).
- **Eval gates (DeepEval + Ragas):** golden 30–50 Q на gpt-4o-mini (~$0.05/run); fail if faithfulness <0.75.
- **Prompt regression:** diff system-prompt → run eval-suite → PR-comment с метриками.
- **Не делать в CI:** full BGE-M3, reranker (runner RAM limit 7 ГБ), GPU-Whisper — нужны self-hosted runners.

**Финальный targeted stack (free-to-user, ~1 RPS):**
- OCI A1.Flex Always Free ($0) для prod API + Qdrant + embeddings
- Hetzner GEX44 (€184/мес) только на batch transcription/reindex, выключается между сессиями
- LLM: BYOK → $0 для проекта
- Langfuse self-host на том же OCI / Hetzner: $0
- **Total ≤ €220/мес максимум; минимально $0 + BYOK**

---

### J. Data pipeline

**Transcription для ~46k часов Dharmaseed.**

| Модель | Params | Speed (RTX 3090) | Языки | Рекомендация |
|---|---|---|---|---|
| whisper-large-v3 | 1.54B | 2m23s/100min (baseline) | 100 | accuracy |
| **faster-whisper-large-v3-turbo int8** | 809M CT2 | ~19s на 13-мин audio (RTF 0.05–0.1) | 99 multilingual | **best speed/accuracy** |
| distil-large-v3.5 | — | ~1.5× быстрее turbo | EN only | не подходит (нужны multilingual лекции) |

**Оценка cost/time (46k часов):**

| Вариант | Стоимость | Wall-time | Контроль |
|---|---|---|---|
| **Groq Whisper turbo @ $0.04/hr** | **~$1840** | ~2–3 дня @ 216× RT | managed |
| Hetzner GEX44 self-host turbo int8 | €800–920 (4–5 мес €184/мес) | ~130 дней непрерывно | полный |
| Replicate Whisper large-v3 | ~$7800 | быстро | managed, но дорого |
| RunPod spot A40 | ~$1170 | несколько недель с прерываниями | средний |
| Modal A10 | ~$3300 | быстро | managed |

**Рекомендация:** **Groq turbo для одноразового bulk** (дёшево, быстро, managed), далее incremental pipeline на GEX44 для новых добавлений.

**Alignment / Diarization:**
- **WhisperX** (faster-whisper backend + wav2vec2 forced alignment + VAD + pyannote-diarization) — для word-level timestamps и speaker turns.
- **Для Dharma** (часто соло-лекция, реже Q&A с аудиторией): WhisperX + VAD-filter; diarization **включать только для Q&A сегментов** (metadata-flag `is_qa=true`). Экономит 30–50% времени. Pyannote — bottleneck: ~1 ч на 90-мин лекцию на RTX 3090.

**Consent Ledger (юридическая сила).** Публичный YAML в git даёт **good-faith documentation** и DMCA-workflow, но **не заменяет письменное согласие**. Аналоги: Mozilla Common Voice (per-contribution consent), Creative Commons metadata, C2PA provenance, Linux Foundation DCO. Для Dharmaseed нюанс: сам сайт под CC-BY-NC-ND → verbatim redistribution проблематично, но **transformative use (RAG answer + snippet + attribution)** обычно в fair-use territory; per-teacher opt-in даёт legitimacy.

Минимально необходимая схема записи:

```yaml
- source: dharmaseed.org/teacher/42
  teacher: "Ajahn Sucitto"
  license: "CC BY-NC-ND 3.0"
  consent_status: "explicit_email_2025-11-03"
  consent_evidence: "ledger/emails/sucitto_2025-11-03.md.gpg"
  scope: "transcription, indexing, RAG-Q&A, no-redistribution-verbatim"
  revocation_contact: "dharma-rag@..."
  updated: 2026-02-15
```

**Revocation endpoint:** учитель пишет — конкретный `teacher_id` исключается из next-reindex за ≤7 дней. Это критично для moral standing проекта.

---

### K. Privacy & Ethics

**Zero user data collection — реалистичные паттерны:**

1. **Langfuse self-host + server-side masking** через `LANGFUSE_INGESTION_MASKING_CALLBACK_URL` + client-side `mask=pii_masker` → PII не покидает приложение.
2. **Session-only mode:** Redis с TTL=session_end (или in-memory dict); нет persistent DB для user queries.
3. **No-persistence flag:** header `X-No-Log: 1` → skip traces.
4. **Ephemeral session IDs:** без cookies, random per tab, не linked к user.
5. **Presidio (Microsoft)** для NER-based PII в masking-callback.
6. **Self-host всего** (Langfuse, Qdrant, vLLM) — никаких third-party telemetry.
7. **Transparent `/privacy` endpoint** возвращающий актуальный статус и hash конфигурации privacy-settings.

**Ethics для AI-ответов по духовным практикам (lessons из медицинского/юр RAG):**
- **Mandatory disclaimers:** «Не замена прямому контакту с учителем; RAG может ошибаться в тонких доктринальных вопросах».
- **Refusal patterns:** hardcoded no-go на suicide crisis, medical interpretation of meditation side-effects (dukkha nāṇa, dark night), specific advice на traumatic trigger → refuse + redirect на crisis lines / direct teacher contact.
- **Guardrails:** Llama Guard 3 / NeMo Guardrails на input+output. Buddhist-specific: не приписывать цитаты конкретному учителю без чёткого UID в retrieved_context.
- **Citation hard-requirement:** refuse to answer if retrieved context has <2 relevant chunks — **faithfulness over fluency**.
- **Version-pinning:** дата index build + corpus snapshot hash в каждом ответе (reproducibility/auditability).
- **Cross-tradition labeling:** Theravāda/Mahāyāna/Vajrayāna tags на chunks → prompt instructs модель не смешивать без явного пользовательского запроса.
- **Human escalation:** кнопка «Ask a human teacher» с готовой сводкой query+context → форум/email.
- **Soteriological caveats:** для вопросов про stream-entry, jhāna — явный disclaimer о спекулятивности LLM-ответов.
- **Public audit log:** анонимизированные refused-queries публикуются monthly → transparency.

---

## Часть 2. Рекомендации по UX

**Базовые user journeys:**

1. **Первый запрос без регистрации.** Landing с примерами вопросов (`"What is satipaṭṭhāna?"`, `"Show me suttas about right speech"`, `"Difference between samādhi and samatha"`). Клик — сразу streaming ответ + retrieved citations. Зарегистрирован или нет — разницы в MVP нет.
2. **Углубление в тему.** Ответ содержит inline citations `[MN 10 §12]`. Клик открывает side panel с полным текстом сутты + metadata (nikaya, translator, license). Внизу — *«Related questions»* (HyDE-generated на топик).
3. **Навигация по связанным суттам.** Для каждой цитируемой сутты — блок *«Similar passages across Nikāyas»* (top-3 из dense retrieval по самой сутте как query). В Phase 2/3 — visualization графа связей: concept → sutta → related concepts.

**Показ неуверенности (не как число):**
- *«Direct quote from MN 10»* — faithfulness >0.9, ≥2 цитаты на ≥50% ответа.
- *«Synthesized from multiple sources»* — faithfulness 0.7–0.9, ≥3 цитаты.
- *«Interpretive — verify with a teacher»* — faithfulness <0.7 или retrieved context <2 chunks.
- *«I don't have enough source material for this question»* — hardcoded refusal.

**Предотвращение misuse (самолечение ментальных проблем через сутты):**
- Input-classifier (cheap LLM) детектирует crisis/medical triggers → **hardcoded response** с crisis lines (Samaritans, Crisis Text Line, национальные линии) + рекомендацией лицензированного терапевта + ссылкой на списки сертифицированных Buddhist chaplains / trauma-sensitive dharma teachers.
- Для вопросов о meditation side-effects (dark night, dukkha nāṇa, panic during retreat) — **не** отвечать на основе сутт, а вывести на Cheetah House / Brown University Britton Lab resources.
- В footer — постоянный disclaimer «This is not a substitute for a teacher».

**Onboarding без регистрации.** Нужно не более 3-х экранов: hero с примерами → что это / что это не → прямой переход к chat. Регистрация опциональна (сохранение bookmarks, glossary личный).

**Feature ideas (по приоритету):**
- **Pali glossary tooltip** на hover — ethymology, range of translations, links to PTS dictionary. **Высокий приоритет**, простая реализация.
- **Bookmark suttas + export** в markdown/anki — Phase 2.
- **Personal practice tracker (локально, IndexedDB)** — nightly reading list, meditation log. Никогда не отправляется на сервер. Phase 3.
- **Reading lists по темам** (curated by volunteers): Right Speech, Jhāna practice, Death contemplation. Статичные YAML в репо — community contribution.
- **Side-by-side Pali + translation** toggle для сутт. Phase 2.
- **Concept graph visualization** из KG (Phase 3) — clickable network: концепт → связанные концепты → sutta-edges.

**Mobile-first vs desktop-first.** Для MVP — **desktop-first**, потому что основные пользователи (practitioners + researchers) читают сутты за столом. Mobile — после SvelteKit + Capacitor (Phase 3). Voice-mode наоборот — mobile-first, потому что это evening/retreat use-case.

**Поиск vs диалог.** Дать оба режима: *«Search suttas»* (keyword + filter по nikaya/teacher/tradition) и *«Ask a question»* (RAG Q&A). Первый — deterministic, второй — generative. Разделить ментально, иначе пользователи будут использовать Q&A для keyword search и наоборот.

---

## Часть 3. Детальный план на 14 дней (14 апреля — 27 апреля 2026)

**Оговорки к плану.**
- Разработка началась 14 апреля. Дни 1–3 — вероятно Phase 0 Setup (из описания задачи). Я исхожу из того, что репо создан, базовый `pyproject.toml`, `docker-compose.yml`, docs существуют, но код retrieval/RAG ещё не написан. Если это не так — первые 2 дня сжимаются.
- План **несиквенциальный** где возможно: retrieval + eval можно вести параллельно с UI, transcription не входит в 14 дней (Phase 1 MVP = только текстовый корпус 56k чанков).
- **Уровень сложности:** S = ≤4 ч, M = полдня, L = полный день.
- Каждая задача оформляется как GitHub Issue с checkbox-acceptance criteria и labels.

### Таблица высокоуровневого плана

| День | Главная цель | Dependencies | Сложность общая |
|---|---|---|---|
| 1 | Infrastructure baseline up | — | M |
| 2 | Ingest + schema + first 10k чанков в Qdrant | Day 1 | L |
| 3 | Contextual Retrieval pipeline + full index | Day 2 | L |
| 4 | Baseline hybrid retrieval endpoint | Day 3 | M |
| 5 | **Golden eval set + first Ragas run** | Day 4 | L |
| 6 | Reranking + Multi-query expansion | Day 5 | M |
| 7 | LLM-abstraction (LiteLLM) + grounded generation | Day 6 | L |
| 8 | SSE streaming API + prompts + citations | Day 7 | M |
| 9 | Phoenix/Langfuse observability + hallucination eval | Day 8 | M |
| 10 | HTMX UI minimal (chat + citations + streaming) | Day 8 | L |
| 11 | Guardrails + refusal patterns + disclaimer layer | Day 10 | M |
| 12 | Retrieval experiments (Qwen3-reranker, hierarchical) | Day 5 (golden set) | L |
| 13 | Prompt hardening + load test + cost model | Day 11 | M |
| 14 | Docs + demo + v0.1.0 release | все | M |

### Day 1 — Infrastructure baseline

**Цель дня:** поднять все инфраструктурные сервисы локально через docker-compose, убедиться что FastAPI скелет запускается.

**Подзадачи:**
1. **[S, `ops`]** Обновить `docker-compose.yml` с сервисами: Qdrant 1.16+, Redis (queue + cache), Phoenix (или Langfuse), FastAPI placeholder. AC: `docker compose up -d` поднимает всё без ошибок, healthcheck endpoints отвечают.
2. **[S, `ops`]** Настроить `.env.example` со всеми ключами (Qdrant URL, Redis URL, OPENROUTER_API_KEY/ANTHROPIC_API_KEY optional, LANGFUSE_*, EMBEDDING_MODEL=BAAI/bge-m3, RERANKER_MODEL=BAAI/bge-reranker-v2-m3). AC: `.env.example` задокументирован, CI проверяет загрузку.
3. **[M, `backend`]** Создать FastAPI app skeleton с `/health`, `/version`, `/metrics` (Prometheus). AC: `curl localhost:8000/health` → 200.
4. **[S, `docs`]** README с инструкцией `make dev` / `docker compose up`. AC: fresh clone → working local setup ≤5 минут.
5. **[S, `ci`]** GitHub Actions workflow: lint (ruff) + type-check (mypy/pyright) + pytest placeholder. AC: CI зелёный на пустом тесте.

**Риски/блокеры:** Docker-memory на dev-машине если разработчик на Mac с 16 ГБ (ClickHouse Langfuse v3 тяжёлый → рекомендую Phoenix на Day 1).

**В конце дня должно работать:** поднятый local stack, FastAPI с `/health`.

### Day 2 — Ingest + schema + первые 10k чанков

**Цель дня:** определить схему metadata и загрузить sample из SuttaCentral в Qdrant.

**Подзадачи:**
1. **[L, `ingest`]** Написать ingest-скрипт для SuttaCentral Bilara-data (JSON от SuttaCentral API). Извлекать `uid`, `nikaya`, `sutta_number`, `translator`, `license`, `speaker`, `audience`, `language`, `text`. AC: скрипт проходит по ≥1 nikaya (MN, 152 sutt) и возвращает структурированный JSONL.
2. **[M, `ingest`]** Chunking v0: structural (по `<section>` → параграф), chunk_size=384 токенов с overlap 60. Сохранять `{parent_sutta_uid, chunk_index, pericope_id=null, metadata...}`. AC: MN разбит на ≤5k чанков, никакой chunk не рвёт формулу (проверка regex: `Evaṃ me sutaṃ` всегда в начале первого чанка сутты).
3. **[M, `retrieval`]** Qdrant collection schema: named vectors `dense` (1024d, cosine), `sparse` (IDF modifier). Создать индекс через Qdrant client. AC: коллекция создана, `GET /collections/dharma` возвращает корректную схему.
4. **[M, `retrieval`]** BGE-M3 embedding script (FastEmbed или FlagEmbedding). Batch 32, upsert с payload. AC: 10k чанков из MN в Qdrant за <30 мин на CPU.
5. **[S, `eval`]** Проверить что `query_points(prefetch=[dense, sparse], query=FusionQuery(RRF))` возвращает sensible top-5 на 5 smoke-queries («What are the four noble truths?», «satipaṭṭhāna»...). AC: качественная проверка, не метрика.

**Риски:** SuttaCentral API rate limit (кэшировать ответы локально). Pali-диакритика → encoding issues (строго NFC throughout).

**В конце дня:** 10k чанков в Qdrant, работает hybrid retrieval на smoke-queries.

### Day 3 — Contextual Retrieval + full index

**Цель дня:** применить Anthropic Contextual Retrieval ко всем 56k чанков и полный index build.

**Подзадачи:**
1. **[M, `retrieval`, `contextual`]** Prompt-template для contextual summary: 50–100 токенов контекста («This chunk is from the Pali Canon, {nikaya}, {sutta_name} where the Buddha speaks to {audience} about {topic}...»). AC: prompt в git, пример output для 5 чанков вручную проверен.
2. **[L, `retrieval`, `contextual`]** Batch-script: Haiku 4.5 (или gpt-4o-mini для дешевизны) + prompt caching → для каждого чанка сгенерировать context → prepend к тексту перед embedding и BM25 индексацией. Сохранить оригинал и contextualized версии в metadata. AC: 56k чанков обработаны, cost-log <$50.
3. **[M, `retrieval`]** Full re-index: 56k чанков dense + sparse в Qdrant. AC: collection содержит 56684 points, все с тремя полями (text, text_contextual, metadata).
4. **[S, `ingest`]** Добавить BM25 индекс (Qdrant sparse с IDF modifier отдельный канал — на `text_contextual` с ICU normalization для Pali diacritics). AC: BM25 query «jhana» возвращает >10 hits.
5. **[S, `eval`]** Smoke-test top-5 на 5 queries до/после contextual — качественная проверка «стало лучше». AC: документированный diff.

**Риски:** LLM rate limits при batch embedding; решение — async + backoff + resume-from-checkpoint.

**В конце дня:** полный индекс 56k чанков с contextual retrieval, hybrid dense+sparse+BM25 через Qdrant Query API.

### Day 4 — Baseline hybrid retrieval endpoint

**Цель дня:** production-ready retrieval endpoint с Query API, RRF fusion, metadata filters.

**Подзадачи:**
1. **[M, `backend`, `retrieval`]** FastAPI endpoint `POST /retrieve {query, k=20, filters?}`. Internal: embed query (BGE-M3 dense+sparse), Qdrant `query_points(prefetch=[dense, sparse, bm25], fusion=RRF)`. AC: latency <500 ms на CPU для коротких запросов.
2. **[S, `backend`]** Client-side rate limiting (slowapi, 30 req/min per IP). AC: тест с 50 concurrent → 429 начиная с 31.
3. **[S, `backend`]** Async Qdrant client, reuse connection pool. AC: benchmark показывает <2× overhead от raw Qdrant HTTP.
4. **[M, `retrieval`]** Implement weighted RRF config через env var `FUSION_WEIGHTS="dense:1.0,sparse:0.8,bm25:0.6"`. AC: конфиг загружается, A/B легко переключить.
5. **[S, `ops`]** Prometheus metrics: `retrieve_latency_seconds`, `retrieve_results_count`, `fusion_strategy`. AC: метрики видны в Grafana или `/metrics` endpoint.

**Риски:** Qdrant Query API sparse+IDF баги при bulk delete — пока not applicable (корпус статический).

**В конце дня:** `/retrieve` endpoint production-quality, наблюдаемый, rate-limited.

### Day 5 — Golden eval set + first Ragas run 🔑

**Цель дня:** **критическая веха** — без этого всё дальше слепое. Построить golden eval set 150 Q&A и первый Ragas baseline.

**Подзадачи:**
1. **[M, `eval`]** Taxonomy-spec: 40% citation, 30% thematic, 10% comparative, 10% lineage, 10% ethical. AC: документ `docs/eval_taxonomy.md`.
2. **[L, `eval`]** Ragas `TestsetGenerator` на sample из 5k чанков, 150 Q. Distribution simple:reasoning:multi-context = 50:25:25. Cost ≤$5 на gpt-4o-mini. AC: `data/golden/testset_v0.jsonl` в git.
3. **[M, `eval`]** Cross-model check: re-run те же 150 Q на Claude Haiku 4.5, оставить Q с ≥70% semantic overlap. AC: `testset_v0_verified.jsonl` с ~100-120 Q.
4. **[M, `eval`]** Manual human pass на 30 Q (сам разработчик или волонтёр): labels `correct / cites-right / hallucinated`. AC: 30 Q с ground-truth анкорами.
5. **[M, `eval`]** Ragas eval-run baseline: faithfulness, answer_relevancy, context_precision, context_recall. Цели — записать текущие цифры. AC: `reports/eval_baseline_day5.md` с метриками.

**Риски:** Ragas TestsetGenerator на `knowledge_graph`-based требует хорошего extraction; если fails — fallback на random-chunk-based simple Q gen.

**В конце дня:** `data/golden/` с 100+ Q, `reports/eval_baseline_day5.md` с цифрами Ragas. **Это артефакт, вокруг которого крутятся все последующие дни.**

### Day 6 — Reranking + Multi-query expansion

**Цель дня:** добавить reranker-стадию и multi-query expansion.

**Подзадачи:**
1. **[M, `retrieval`, `reranker`]** Подключить BGE-reranker-v2-m3 через TEI или in-process (с `run_in_executor`). Endpoint `POST /retrieve-rerank {query, k_retrieve=30, k_final=5}`. AC: reranker latency <1.5 s CPU на 30 pairs.
2. **[S, `retrieval`]** MMR diversification на top-30 до reranker по `pericope_id` (если определено) или cosine между результатами. AC: документированный diff «dup-suppression» на 3 примерах.
3. **[M, `retrieval`, `llm`]** Multi-query expansion: Haiku/gpt-4o-mini генерирует 3 перефразировки с instruction "include Pali/Sanskrit equivalents". Запускаем retrieve для каждого, склеиваем через RRF. AC: +3–8% recall@10 на golden set.
4. **[M, `eval`]** Re-run Ragas eval на golden set, сравнить с Day 5 baseline. AC: `reports/eval_day6.md` с диффом.
5. **[S, `docs`]** Обновить `RAG_PIPELINE.md` с описанием текущего pipeline.

**Риски:** reranker CPU latency может быть неприемлемой (>3 с на 30 pairs) — fallback k=15 или TEI на small GPU.

**В конце дня:** полный retrieval pipeline (multi-query → hybrid → rerank → mmr), измеренное улучшение над baseline.

### Day 7 — LLM-abstraction + grounded generation

**Цель дня:** LiteLLM/OpenRouter как единая абстракция, grounded prompt с citations.

**Подзадачи:**
1. **[M, `generation`]** Интегрировать LiteLLM. Конфиг `litellm.config.yaml` с моделями: `claude-haiku-4-5`, `claude-sonnet-4-6`, `llama-3.3-70b` (DeepInfra), `qwen3-32b` (Groq), `gpt-4o-mini`. AC: переключение модели через env var, все pass smoke.
2. **[M, `generation`, `prompt`]** System prompt для grounded RAG: XML-citation format `<cite source="MN10" loc="12.3-5"/>`, instructions по deference/не-ответу при недостаточном context, refusal patterns. AC: prompt в `prompts/system_v1.jinja`, версионируется в git.
3. **[M, `generation`]** Если backend=Claude → использовать native Citations API с document blocks; иначе — XML-prompt + post-parser. AC: оба пути рабочие, parser → структурированный response.
4. **[M, `generation`, `routing`]** Простое правило-based routing: дефолт Llama 3.3 70B (DeepInfra); если query content длинный/сложный (>100 токенов) или explicit user-request — escalate на Sonnet/Opus. AC: routing logs показывают split 70/30.
5. **[S, `eval`]** Ragas eval с новой generation: faithfulness приоритет. AC: `reports/eval_day7.md`.

**Риски:** Anthropic Citations API требует plain text document blocks (не .md/.docx), что вы уже имеете — норм.

**В конце дня:** `/ask` endpoint (non-streaming) с цитатами, измеренная faithfulness на golden set.

### Day 8 — SSE streaming + citations UI-ready

**Цель дня:** streaming API + структурированный citation payload для фронта.

**Подзадачи:**
1. **[M, `backend`, `streaming`]** `/ask/stream` endpoint с `EventSourceResponse`. Events: `retrieval_started`, `retrieval_done {chunks:[...]}`, `generation_token {text}`, `citation {source, loc, quoted}`, `done {metrics}`. AC: curl получает structured SSE.
2. **[S, `backend`]** Headers: `X-Accel-Buffering: no`, `Cache-Control: no-cache`; heartbeats 20s. AC: Nginx-tested no buffering.
3. **[M, `generation`]** Streaming parser для XML-citations: поддерживать incremental parse `<cite ...>` в стриме токенов → emit citation event как только тег закрыт. AC: 5 test cases проходят.
4. **[S, `backend`]** `request.is_disconnected()` loop для graceful cancel; abort LLM call. AC: тест с закрытием соединения → generation останавливается.
5. **[S, `docs`]** API-spec в OpenAPI + примеры SSE-payloads.

**Риски:** SSE в некоторых прокси режет chunked encoding; hardened headers обязательны.

**В конце дня:** полноценный streaming API, готовый к подключению UI.

### Day 9 — Observability + hallucination eval

**Цель дня:** tracing и автоматическая hallucination detection.

**Подзадачи:**
1. **[M, `ops`, `observability`]** Phoenix (или Langfuse) integration. Все вызовы LLM, retrieve, rerank — через OTel spans. AC: trace UI показывает полный waterfall query → retrieve → rerank → LLM → parse.
2. **[S, `observability`]** PII-masking callback: regex + Presidio на emails/phones/IDs в user-query до логирования. AC: тест с `email@test.com` → `<EMAIL>` в trace.
3. **[M, `eval`, `hallucination`]** HHEM-2.1-Open integration. Для каждого ответа считать faithfulness score против retrieved context. Если <0.5 — flag в log + optional re-try с Sonnet. AC: HHEM на golden set — записать средний score.
4. **[M, `eval`]** Dashboard (Grafana) с метриками: p50/p95/p99 latency, hallucination-flag rate, cost per 1k queries, model distribution. AC: live dashboard доступен localhost.
5. **[S, `ops`]** Cost-tracking per-model в Phoenix/Langfuse. AC: daily cost-total видим в UI.

**Риски:** HHEM CPU inference ~1.5 с на 2k токенов — лучше запускать async offline для всех прод-запросов; inline — только при отладке.

**В конце дня:** полная observability-картина, hallucination-monitoring.

### Day 10 — HTMX UI minimal

**Цель дня:** минимальный web-интерфейс, достаточный для показа.

**Подзадачи:**
1. **[M, `frontend`]** HTMX + Tailwind layout: landing с примерами, chat-area с SSE rendering. AC: один HTML-файл, работает в Chrome/Firefox/Safari.
2. **[M, `frontend`]** SSE integration: progressive rendering tokens, live citation badges `[MN 10]` с клик-раскрытием source chunk. AC: streaming виден, citations clickable.
3. **[S, `frontend`]** Confidence indicator (3 tier): direct quote / synthesized / interpretive. Mapping из faithfulness score. AC: UI badge на каждом ответе.
4. **[S, `frontend`]** Language toggle EN/RU только для UI copy (ответы остаются в языке запроса). AC: `?lang=ru` работает.
5. **[S, `frontend`]** Footer disclaimer постоянный («Not a substitute for a teacher, see /privacy»).

**Риски:** SSE handling в HTMX 2.x — надо использовать `hx-ext="sse"`; тестировать на real browser.

**В конце дня:** работающее демо в браузере.

### Day 11 — Guardrails + refusal + disclaimers

**Цель дня:** поведение на sensitive inputs, правильный отказ.

**Подзадачи:**
1. **[M, `guardrails`]** Input classifier (cheap LLM или regex-rules) для no-go: crisis/suicide, medical interpretation of meditation side-effects, specific advice on trauma. При match → hardcoded response с crisis lines + «consult a teacher». AC: 15 тест-cases все correctly refused.
2. **[S, `guardrails`]** Hard-gate: если retrieved context <2 chunks или top-1 score <0.5 → «I don't have enough source material for this question». AC: тест с нелепыми запросами.
3. **[M, `guardrails`]** Attribution verifier: regex-parse `<cite source="X"/>` в response → verify X в retrieved_context UID-set → если нет, flag как attribution-hallucination. AC: тест с fake citation → flag.
4. **[S, `prompt`]** Deference-check: post-process answer для замены «The Buddha says» → «According to MN 10». AC: regex unit tests.
5. **[S, `docs`]** `docs/SAFETY.md` с полным списком guardrails.

**Риски:** false-positives refusal classifier на «how did Buddha deal with suicide in the suttas» (legitimate academic question). Two-stage: если detected crisis → second classifier «academic vs personal» → academic путь.

**В конце дня:** ответы на sensitive queries безопасны, задокументированные паттерны.

### Day 12 — Retrieval experiments (опциональный, но ценный)

**Цель дня:** A/B-тесты критических retrieval-решений.

**Подзадачи:**
1. **[M, `experiments`, `retrieval`]** Qwen3-Reranker-0.6B или 4B в place of BGE-reranker-v2-m3. AC: Ragas diff на golden set, решение принять/отклонить.
2. **[M, `experiments`, `retrieval`]** Hierarchical retrieval: child chunks 384t / parent = полная sutta (или section). Retrieve child, для LLM-context — parent. AC: faithfulness diff.
3. **[M, `experiments`, `retrieval`]** Late chunking (full-sutta forward pass + span-pooling через BGE-M3). AC: только для sutta ≤8192 токенов; для более длинных — fallback на normal chunking.
4. **[S, `experiments`, `retrieval`]** HyPE (pre-generate 3-5 questions per chunk, index вместе). AC: запустить на 10k sample, measure.
5. **[S, `docs`]** `reports/retrieval_experiments_day12.md`: какие выиграли, какие в следующий раз.

**Риски:** Qwen3-reranker-4B требует GPU — если нет, тестировать только 0.6B.

**В конце дня:** основанные-на-данных улучшения retrieval.

### Day 13 — Prompt hardening + load test + cost model

**Цель дня:** production-readiness.

**Подзадачи:**
1. **[M, `prompt`]** Prompt regression suite: 20 edge-cases (длинный Pali термин, multi-sutta сравнение, потенциально-сектантский вопрос, запрос перевода). AC: все проходят через Pytest.
2. **[M, `ops`, `loadtest`]** Locust/k6 load test: 50 concurrent users, 10 мин. Измерить p99 latency, error rate, LLM cost. AC: `reports/loadtest_day13.md`.
3. **[M, `ops`, `cost`]** Cost-model документ: при 100/1000/10000 req/day на каждой конфигурации (all Haiku / routing / Llama DeepInfra / local Qwen3). AC: `docs/COST_MODEL.md`.
4. **[S, `ops`]** Backup strategy для Qdrant: snapshots API → S3/MinIO; cron weekly. AC: тест restore из snapshot.
5. **[S, `security`]** Basic security scan: `safety check` на dependencies, bandit на код. AC: зелёный отчёт или documented exceptions.

**Риски:** load test откроет bottleneck на BGE-M3 CPU — решение: horizontal scaling FastAPI + shared TEI.

**В конце дня:** известные performance-границы, cost-prognosis.

### Day 14 — Docs + demo + v0.1.0 release

**Цель дня:** finalize + public-facing materials.

**Подзадачи:**
1. **[M, `docs`]** README.md finalized: quick-start, architecture diagram (mermaid), examples, links to all docs. AC: fresh reader понимает проект за 5 минут.
2. **[M, `docs`]** `docs/ARCHITECTURE.md`: updated с реальным стеком Day 1–13 (не pre-code версия). AC: совпадает с кодом.
3. **[S, `docs`]** CHANGELOG.md для v0.1.0: все фичи, known issues, next steps. AC: semver-compliant.
4. **[M, `demo`]** Public demo screencast (5–10 мин): сетап, пример queries с citations, streaming, guardrails. AC: mp4 или youtube link.
5. **[S, `ops`]** `v0.1.0` git tag + GitHub release с release notes + Docker image на GHCR. AC: `docker pull ghcr.io/.../dharma-rag:0.1.0` работает.
6. **[S, `community`]** CONTRIBUTING.md с guidelines, issue templates (bug, feature, source proposal), CoC. AC: GitHub issues templates активны.

**Риски:** release train часто обрастает дополнительными bugs — зарезервировать последние 2 часа дня на firefighting.

**В конце дня:** v0.1.0 Foundation зарелижен, публично видим, demo работает.

---

## Приложение: критичные risk flags и шорт-лист неочевидных ошибок

1. **Hetzner поднял цены на 30–35% с 1 апреля 2026** — пересчитать бюджет, если изначальный план опирался на 2025 price list.
2. **Microsoft GraphRAG часто хуже vanilla RAG на факт-query** (Han et al. 2025, arXiv 2506.05690, −13.4% accuracy на HotpotQA) — не строить KG «на всякий случай» в Phase 3, сначала доказать на golden set что ≥15% query требуют graph traversal.
3. **Jina v3, XTTS v2, F5-TTS имеют non-commercial licences** (CC-BY-NC, CPML, CC-BY-NC-4.0) — несовместимы с MIT distribution. Исключить из архитектуры.
4. **pg_search (ParadeDB) под AGPL v3** — cognitive dissonance с MIT-этосом, хотя технически self-hosted без модификаций OK.
5. **Langfuse v3 требует Postgres + ClickHouse + Redis + S3 + 2 контейнера** — минимум 16 ГБ RAM. Для маленького self-hosted проекта рассмотреть Phoenix (single container).
6. **BGE-M3 IDF modifier в Qdrant 1.10+ имеет баг с retention IDF после массовых delete** (issue #6735) — для вашего статического корпуса не страшно, но документировать.
7. **Native Whisper / любой cloud STT не имеют Pali модели** — работает только через `initial_prompt` / keyterms со словарём-глоссарием.
8. **Ни один TTS «из коробки» не выговаривает диакритику** — без Pali-G2P-препроцессора пользователь услышит искажения.
9. **Claude в центре RAG — прямой conflict с MIT-этосом**, если это не opt-in BYOK. Либо переформулировать в README как «премиум-опция», либо заменить default на Llama 3.3 70B / Qwen3-32B.
10. **Golden eval set на Day 5 — не Day 10+.** Без него решения по chunking/rerankers/промптам — без компаса.

Это и есть 14-дневный plan-of-record с room for experimentation: Day 5 (golden set) и Day 9 (observability) — два узких места, всё остальное параллелизуется или скользит по датам. Если на Day 8 становится ясно, что faithfulness <0.7 — Day 12 (experiments) следует поднять вперёд. Если же baseline держит faithfulness >0.85 — Day 12 становится advanced features day (HyPE, hierarchical).

Удачи с сангхой и с графами.
