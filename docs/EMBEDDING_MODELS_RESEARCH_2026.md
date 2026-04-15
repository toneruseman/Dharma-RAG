# Исследование Embedding моделей для Dharma RAG

> **Дата:** Апрель 2026
> **Цель:** Выбрать оптимальную embedding модель для мультиязычного RAG на буддийских текстах
> **Критерии:** качество retrieval, мультиязычность (EN/RU/палийский), стоимость, простота деплоя, поддержка hybrid search

---

## TL;DR — Рекомендация для Dharma RAG

**Основная модель:** BGE-M3 (self-hosted, бесплатно)
**Причины:** единственная модель с нативным dense + sparse + ColBERT за один проход, MIT лицензия, 100+ языков, отличная поддержка hybrid search в Qdrant, 568M параметров — работает на CPU и слабых GPU.

**Для палийского контента:** MITRA-E (domain-specific, Gemma 2 based)
**Причины:** специализирована на буддийских текстах (Pāli, Sanskrit, Buddhist Chinese, Tibetan), обгоняет BGE-M3 и LaBSE на буддийских бенчмарках.

**Бюджетная альтернатива через API:** Google text-embedding-005 ($0.006/1M токенов) или Gemini Embedding 001 (free tier).

**Если нужен абсолютный максимум качества:** Voyage voyage-3-large ($0.18/1M) или Gemini Embedding 2 ($0.20/1M).

---

## 1. Ландшафт embedding моделей: апрель 2026

### 1.1. Что изменилось за последний год

Рынок embedding моделей кардинально изменился:

- **Open-source догнал и обогнал** закрытые модели по бенчмаркам (NV-Embed-v2: 72.31, Qwen3-Embedding-8B: 70.58 vs лучшая API-модель Gemini: 68.32)
- **Matryoshka Representation Learning (MRL)** стал стандартом — можно уменьшать размерность без потери качества
- **Мультимодальные embeddings** появились (Gemini Embedding 2: текст + изображения + видео + аудио + PDF)
- **Специализированные доменные модели** доказали превосходство над general-purpose (MITRA-E для буддизма, Voyage code-3 для кода)
- **OpenAI text-embedding-3-large не обновлялся с января 2024** — теперь 7-9 место в рейтингах

---

## 2. Полная таблица моделей

### 2.1. Закрытые API-модели

| Модель | Провайдер | MTEB Avg | MTEB Retrieval | Цена/1M tok | Dim | Контекст | Языки | Matryoshka | Лицензия |
|--------|-----------|----------|----------------|-------------|-----|----------|-------|------------|----------|
| **Gemini Embedding 001** | Google | **68.32** | **67.71** | Free tier / $0.10 | 768-3072 | 2,048 | 100+ | ✅ | Closed |
| **Gemini Embedding 2** | Google | 68.16 | ~67 | $0.20 | 3072 | 8,192 | 100+ | ✅ | Closed |
| **Voyage voyage-3-large** | Voyage AI | 65.1 | 67.2 | $0.18 | 1024 | 32,000 | Multi | ✅ | Closed |
| **Voyage voyage-4** | Voyage AI | ~66 | ~68 | $0.06 | 1024 | 32,000 | Multi | ✅ | Closed |
| **Voyage voyage-4-lite** | Voyage AI | ~62 | ~63 | $0.02 | 512 | 32,000 | Multi | ✅ | Closed |
| **Cohere embed-v4** | Cohere | 65.2 | ~64.2 | $0.12 | 1024-1536 | 128,000 | 100+ | ✅ | Closed |
| **text-embedding-3-large** | OpenAI | 64.6 | ~63 | $0.13 | 256-3072 | 8,191 | Multi | ✅ | Closed |
| **text-embedding-3-small** | OpenAI | 62.3 | ~61 | $0.02 | 512-1536 | 8,191 | Multi | ✅ | Closed |
| **text-embedding-005** | Google | 63.8 | ~62 | **$0.006** | 768 | 2,048 | Multi | ❌ | Closed |
| **jina-embeddings-v3** | Jina AI | 63.5 | ~62 | $0.02 | 1024 | 8,192 | 89+ | ✅ | CC-BY-NC* |
| **Mistral Embed** | Mistral | ~62 | ~61 | $0.01 | 1024 | 8,192 | Multi | ❌ | Closed |

*jina-embeddings-v3: API использование — $0.02/MTok; self-hosting требует коммерческую лицензию.

### 2.2. Open-source модели (self-hosted)

| Модель | Разработчик | MTEB Avg | MTEB Retrieval | Параметры | Dim | Контекст | Языки | Hybrid | Лицензия | GPU RAM |
|--------|-------------|----------|----------------|-----------|-----|----------|-------|--------|----------|---------|
| **NV-Embed-v2** | NVIDIA | **72.31** | 62.65 | 7.85B | 4096 | 32,768 | EN only | ❌ | CC-BY-NC | 16+ GB |
| **Qwen3-Embedding-8B** | Alibaba | 70.58 | ~65 | 8B | 32-4096 | 32K | 100+ | ❌ | Apache 2.0 | 16+ GB |
| **Qwen3-Embedding-4B** | Alibaba | ~68 | ~63 | 4B | 32-4096 | 32K | 100+ | ❌ | Apache 2.0 | 8+ GB |
| **Qwen3-Embedding-0.6B** | Alibaba | ~65 | ~60 | 0.6B | 32-1024 | 32K | 100+ | ❌ | Apache 2.0 | 2+ GB |
| **BGE-M3** | BAAI | ~63 | ~62 | **568M** | 1024 | 8,192 | **100+** | **✅ D+S+C** | **MIT** | **2-4 GB** |
| **BGE-en-ICL** | BAAI | 71.24 | ~66 | 7B | 4096 | 32K | EN only | ❌ | MIT | 14+ GB |
| **Jina v5-text-small** | Jina AI | 71.7 (v2) | ~64 | 677M | 1024 | 8,192 | 89+ | ❌ | Apache 2.0 | 3 GB |
| **EmbeddingGemma-300M** | Google DM | ~62 | ~60 | 300M | 768 | 8,192 | Multi | ✅ | Open | 1-2 GB |
| **nomic-embed-text-v1.5** | Nomic AI | ~62 | ~60 | 137M | 64-768 | 8,192 | EN | ✅ | Apache 2.0 | <1 GB |
| **all-MiniLM-L6-v2** | Microsoft | ~56 | ~52 | 22.7M | 384 | 512 | EN | ❌ | Apache 2.0 | <1 GB |
| **MITRA-E** | Buddhist NLP | N/A* | SOTA буддизм | ~2B (Gemma2) | ~768 | ~8K | Pāli/San/Zh/Ti | ❌ | Open | 4-8 GB |
| **Microsoft Harrier-OSS-v1** | Microsoft | 74.3 (v2) | ~68 | 27B | 1024 | 8K | Multi | ❌ | MIT | 54+ GB |

*MITRA-E не тестировалась на общем MTEB — только на специализированном буддийском бенчмарке.

**Обозначения Hybrid:** D = Dense, S = Sparse, C = ColBERT (multi-vector)

---

## 3. Детальный анализ ТОП-10 моделей

### 3.1. BGE-M3 (BAAI) — ⭐ РЕКОМЕНДАЦИЯ ДЛЯ DHARMA RAG

**Почему это лучший выбор для нашего проекта:**

1. **Единственная модель с нативным hybrid retrieval** — dense + learned sparse + ColBERT за один forward pass. Не нужно запускать 3 разные модели.

2. **MIT лицензия** — полностью бесплатно для коммерческого и некоммерческого использования.

3. **100+ языков** — английский, русский, палийский (через транслитерацию), санскрит.

4. **568M параметров** — компактная модель:
   - Запускается на CPU (медленнее, но работает)
   - На GTX 1080 Ti (11GB) — комфортно
   - На обычном VPS с 8GB RAM — через CPU inference

5. **8,192 токенов контекста** — достаточно для parent chunks 600 слов.

6. **Отличная интеграция с Qdrant** — native named vectors для dense + sparse, ColBERT late interaction.

**Производительность:**

- Embedding скорость: ~500 docs/sec на GPU, ~50 docs/sec на CPU
- 56,684 чанка: ~2 мин на GPU, ~20 мин на CPU
- 900K чанков (Phase 1.5): ~30 мин GPU, ~5 часов CPU

**Использование:**

```python
from FlagEmbedding import BGEM3FlagModel

model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)

# Получить ВСЕ типы embeddings за один проход
output = model.encode(
    ["What is jhāna?"],
    return_dense=True,
    return_sparse=True,
    return_colbert_vecs=True
)

dense = output['dense_vecs']      # shape: (1, 1024) — для semantic search
sparse = output['lexical_weights'] # dict: {token_id: weight} — для keyword matching
colbert = output['colbert_vecs']   # shape: (1, seq_len, 1024) — для fine-grained matching
```

**Слабости:**
- MTEB score (~63) ниже чем у 7-8B моделей — это ожидаемо при 568M параметрах
- Нет Matryoshka (фиксированные 1024 dim) — но это не проблема для нашего масштаба
- Не domain-specific для буддийского NLP

---

### 3.2. MITRA-E (Buddhist NLP) — ДОМЕН-СПЕЦИФИЧНАЯ МОДЕЛЬ

**Уникальность:** единственная embedding модель, специализированная на буддийских текстах.

**Что внутри:**
- Основа: Gemma 2 (9B параметров), continuously pre-trained на буддийском корпусе
- Fine-tuned на 1.74M параллельных пар (Sanskrit ↔ Chinese ↔ Tibetan)
- Semantic embedding benchmark на буддийских текстах — SOTA

**Результаты на буддийском бенчмарке:**
- Обгоняет BGE-M3, LaBSE, FastText на retrieval буддийского контента
- Особенно сильна на cross-lingual retrieval (Pāli query → English document)

**Для Dharma RAG:**
- Использовать как **вторую модель** параллельно с BGE-M3
- RRF fusion: BGE-M3 (general) + MITRA-E (domain) → объединённый результат
- Особенно ценна для палийских/санскритских запросов

**Ограничения:**
- ~9B параметров → нужен GPU с 16+ GB VRAM
- Не тестировалась на general benchmarks (MTEB)
- Может быть слабее на "обычных" запросах
- Нет sparse/ColBERT — только dense embeddings

**Рекомендация:** оценить на eval set (дни 15-16 плана), использовать если даёт +10% на палийских запросах.

---

### 3.3. Gemini Embedding 001 (Google) — ЛУЧШИЙ API ПО БЕНЧМАРКАМ

**Ключевые метрики:**
- MTEB Avg: 68.32 (#1 среди API моделей)
- MTEB Retrieval: 67.71 (#1 среди всех моделей на retrieval)
- Cross-lingual retrieval: 0.997 (лучший показатель)
- Цена: **Free tier** (1,500 запросов/день) или $0.10/MTok на paid tier

**Почему стоит рассмотреть:**
- Лучший retrieval score среди всех моделей — для RAG это ключевая метрика
- Free tier достаточен для разработки и тестирования
- Matryoshka: 768/1536/3072 dim
- 100+ языков с лучшим cross-lingual transfer

**Почему НЕ выбрали как основную:**
- Закрытая модель → vendor lock-in на Google
- Контекст всего 2,048 токенов (наши parent chunks могут быть длиннее)
- Нет sparse/ColBERT → только dense retrieval
- Free tier: 1,500 req/день = ~5 мин непрерывного embedding (для ингеста не хватит)
- Данные проходят через Google → privacy concern для voice в Phase 3

**Рекомендация:** использовать для A/B тестирования. Бесплатно сравнить с BGE-M3 на eval set. Если значительно лучше — рассмотреть для query-side embedding (queries через API, documents через BGE-M3 self-hosted).

---

### 3.4. Qwen3-Embedding (Alibaba) — ЛУЧШИЙ OPEN-SOURCE ПО КАЧЕСТВУ

**Семейство моделей:**
| Размер | MTEB | GPU RAM | Скорость | Использование |
|--------|------|---------|----------|---------------|
| 0.6B | ~65 | 2 GB | Быстро | Прототипирование, edge |
| 4B | ~68 | 8 GB | Средне | Production balance |
| 8B | 70.58 | 16 GB | Медленно | Максимальное качество |

**Преимущества:**
- Apache 2.0 — полностью свободная лицензия
- 100+ языков + programming languages
- Instruction-aware: "Instruct: Find a Buddhist sutta about..." → +1-5% точности
- Matryoshka: 32 до 4096 dim → гибкость хранения
- Контекст 32K (0.6B) / 128K (8B)

**Для Dharma RAG:**
- Qwen3-Embedding-0.6B — отличная альтернатива BGE-M3 по качеству/размеру
- Qwen3-Embedding-4B — лучшее качество если есть GPU 8+ GB
- НО: нет нативного sparse/ColBERT → для hybrid search нужен отдельный BM25

**Рекомендация:** оценить Qwen3-0.6B как drop-in замену BGE-M3 (dense-only). Если качество выше — использовать Qwen3 для dense + BM25 отдельно для sparse.

---

### 3.5. Voyage AI (voyage-3-large / voyage-4) — ЛУЧШИЙ ДЛЯ ДОМЕН-СПЕЦИФИЧНОГО RETRIEVAL

**Ключевые особенности:**
- Лидирует на retrieval-специфичных бенчмарках (67.2 MTEB retrieval)
- Предобучен на "tricky negatives" — различает "похоже, но неправильно"
- Контекст 32,000 токенов — можно embed целые лекции
- MoE архитектура (voyage-4) — на 40% дешевле в inference

**Модели и цены:**
| Модель | Цена/MTok | MTEB | Dim | Free tier |
|--------|-----------|------|-----|-----------|
| voyage-4-large | $0.12 | ~66 | 1024 | 200M tok |
| voyage-4 | $0.06 | ~65 | 1024 | 200M tok |
| voyage-4-lite | $0.02 | ~62 | 512 | 200M tok |
| voyage-4-nano | **$0** (open) | ~59 | 512 | Apache 2.0 |

**Для Dharma RAG:**
- 200M бесплатных токенов = ~50K чанков бесплатно (покрывает Phase 1!)
- voyage-4-nano (Apache 2.0) — можно self-host бесплатно
- НО: нет sparse/ColBERT

**Рекомендация:** использовать free tier для evaluation наряду с BGE-M3 и Gemini.

---

### 3.6. Cohere embed-v4 — ЛУЧШИЙ ДЛЯ ДЛИННЫХ ДОКУМЕНТОВ

**Уникальность:**
- Контекст **128,000 токенов** — можно embed целую книгу за один проход
- Мультимодальный (текст + изображения)
- Типизированные inputs: search_document, search_query, classification, clustering

**Для Dharma RAG:**
- Не нужен — наши чанки 150-600 слов, не 128K
- Дорого ($0.12/MTok) для нашего масштаба
- Нет преимуществ для short-chunk retrieval

---

### 3.7. OpenAI text-embedding-3-large — LEGACY, НЕ РЕКОМЕНДУЕТСЯ

**Статус:** не обновлялся с января 2024. Теперь 7-9 место в рейтингах.

**Для Dharma RAG:** нет причин выбирать. Дороже ($0.13/MTok), хуже по качеству, чем Gemini (бесплатный) или BGE-M3 (self-hosted бесплатно).

**Единственный аргумент:** если уже используешь OpenAI API для всего остального (не наш случай — мы на Claude).

---

### 3.8. NV-Embed-v2 (NVIDIA) — ЛУЧШИЙ ПО MTEB, НО НЕ ДЛЯ НАС

**MTEB Avg: 72.31** — абсолютный лидер.

**Почему НЕ для нас:**
- CC-BY-NC-4.0 — запрещено коммерческое использование (наш MIT проект подразумевает коммерческую свободу)
- 7.85B параметров → 16+ GB VRAM
- Только английский
- 4096 dim → дорогое хранение
- Нет sparse/ColBERT

---

### 3.9. Microsoft Harrier-OSS-v1 — ТЕОРЕТИЧЕСКИЙ ЛИДЕР

**MTEB v2: 74.3** — лучший в мире. Но:
- 27B параметров → нужно 54+ GB VRAM (A100 80GB)
- Нереалистично для соло-разработчика
- MIT лицензия — если бы был меньше, идеальный выбор

---

### 3.10. EmbeddingGemma-300M (Google DeepMind) — ЛЁГКАЯ АЛЬТЕРНАТИВА

**Для edge/mobile:**
- 300M параметров — запускается на телефоне
- Matryoshka + 100+ языков
- Open license

**Для Dharma RAG:**
- Кандидат для on-device embedding в Phase 3 (мобильное приложение)
- Для серверного RAG — слишком слабая модель

---

## 4. Стоимость embedding 56K чанков (Phase 1)

Расчёт: 56,684 чанка × ~150 слов × ~200 токенов = ~11.3M токенов

| Модель | Стоимость Phase 1 | Стоимость 900K чанков (Phase 1.5) |
|--------|-------------------|-----------------------------------|
| BGE-M3 (self-hosted, CPU) | **$0** | **$0** |
| BGE-M3 (self-hosted, GPU) | **$0** | **$0** |
| Qwen3-Embedding-0.6B (self-hosted) | **$0** | **$0** |
| MITRA-E (self-hosted) | **$0** | **$0** |
| Google text-embedding-005 | $0.07 | $1.08 |
| Gemini Embedding 001 (free tier) | **$0** | ~$12 (paid) |
| Voyage voyage-4-nano (open) | **$0** | **$0** |
| Voyage voyage-4-lite (API) | $0.23 | $3.60 |
| OpenAI text-embedding-3-small | $0.23 | $3.60 |
| Jina v3 (API) | $0.23 | $3.60 |
| Cohere embed-v4 | $1.13 | $18.00 |
| OpenAI text-embedding-3-large | $1.47 | $23.40 |
| Voyage voyage-3-large | $2.03 | $32.40 |
| Gemini Embedding 2 | $2.26 | $36.00 |

**Вывод:** при нашем масштабе (56K → 900K чанков) стоимость API минимальна ($0-36). Но при многократном re-embedding (эксперименты, смена модели) self-hosted экономит значительно.

---

## 5. Стоимость GPU для self-hosted моделей

### 5.1. Локально (твой компьютер)

| Модель | Параметры | GPU RAM | Твой GTX 1080 Ti (11GB) | Скорость |
|--------|-----------|---------|-------------------------|----------|
| all-MiniLM-L6-v2 | 22.7M | <1 GB | ✅ отлично | ~5000 docs/sec |
| nomic-embed-text | 137M | <1 GB | ✅ отлично | ~2000 docs/sec |
| EmbeddingGemma-300M | 300M | 1-2 GB | ✅ хорошо | ~1000 docs/sec |
| BGE-M3 | 568M | 2-4 GB | ✅ хорошо (FP16) | ~500 docs/sec |
| Qwen3-Embedding-0.6B | 0.6B | 2 GB | ✅ хорошо | ~500 docs/sec |
| Jina v5-small | 677M | 3 GB | ✅ нормально | ~400 docs/sec |
| MITRA-E (~2B Gemma2) | ~2B | 4-8 GB | ⚠️ тесно (FP16) | ~100 docs/sec |
| Qwen3-Embedding-4B | 4B | 8 GB | ⚠️ тесно (INT8) | ~50 docs/sec |
| NV-Embed-v2 | 7.85B | 16 GB | ❌ не влезет | — |
| Qwen3-Embedding-8B | 8B | 16 GB | ❌ не влезет | — |

### 5.2. На VPS (Hetzner CX32, 8GB RAM, CPU only)

| Модель | CPU inference | 56K чанков | 900K чанков |
|--------|-------------|------------|-------------|
| all-MiniLM-L6-v2 | ~500 docs/sec | 2 мин | 30 мин |
| BGE-M3 | ~30-50 docs/sec | 20-30 мин | 5-8 часов |
| Qwen3-Embedding-0.6B | ~20-40 docs/sec | 25-45 мин | 6-10 часов |
| MITRA-E (~2B) | ~5-10 docs/sec | 1.5-3 часа | 25-50 часов |

### 5.3. Облачный GPU (on-demand)

| Провайдер | GPU | Цена/час | BGE-M3 скорость | Время 900K |
|-----------|-----|----------|-----------------|------------|
| Modal.com | A10G (24GB) | $1.10 | ~2000 docs/sec | ~8 мин |
| Vast.ai | RTX 3090 (24GB) | $0.20-0.40 | ~1500 docs/sec | ~10 мин |
| RunPod | A100 (40GB) | $1.64 | ~5000 docs/sec | ~3 мин |
| Lambda Labs | A100 (80GB) | $2.49 | ~5000 docs/sec | ~3 мин |
| Hetzner GEX44 | RTX 4000 SFF (20GB) | €0.25 (€184/мес) | ~1500 docs/sec | ~10 мин |

**Стоимость одноразового embedding 900K чанков на облачном GPU:**
- Vast.ai RTX 3090: ~$0.07 (10 мин × $0.40)
- Modal.com A10G: ~$0.15 (8 мин × $1.10)
- Полностью ничтожная стоимость.

### 5.4. Managed API для self-hosted моделей

| Платформа | BGE-M3 цена | Qwen3-8B цена | Особенности |
|-----------|-------------|---------------|-------------|
| Fireworks.ai | $0.016/MTok | $0.016/MTok | Быстро, без инфра |
| Together.ai | $0.008/MTok | $0.008/MTok | Дёшево |
| DeepInfra | $0.006/MTok | $0.015/MTok | Низкая задержка |
| Baseten | Custom | Custom | Enterprise |
| Ollama (локально) | **$0** | **$0** | Простейший setup |

---

## 6. Критические параметры для Dharma RAG

### 6.1. Мультиязычность (EN, RU, Pāli)

| Модель | Английский | Русский | Pāli/Sanskrit | Cross-lingual |
|--------|-----------|---------|---------------|---------------|
| Gemini Embedding 001 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 0.997 (лучший) |
| BGE-M3 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | Хороший |
| Qwen3-Embedding | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | Хороший |
| MITRA-E | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | SOTA Buddhist |
| Cohere embed-v4 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | Очень хороший |
| Voyage voyage-4 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | Хороший |
| OpenAI 3-large | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | Средний |
| NV-Embed-v2 | ⭐⭐⭐⭐⭐ | ❌ | ❌ | ❌ EN-only |

**Вывод:** для нашего мультиязычного проекта (EN + RU + Pāli) NV-Embed-v2 и другие EN-only модели отпадают.

### 6.2. Hybrid Search Support

| Модель | Dense | Sparse | ColBERT | Нужен отдельный BM25? |
|--------|-------|--------|---------|----------------------|
| **BGE-M3** | ✅ | ✅ | ✅ | **Нет** (всё в одном) |
| Qwen3-Embedding | ✅ | ❌ | ❌ | Да |
| Gemini | ✅ | ❌ | ❌ | Да |
| Voyage | ✅ | ❌ | ❌ | Да |
| Cohere | ✅ | ❌ | ❌ | Да |
| OpenAI | ✅ | ❌ | ❌ | Да |

**BGE-M3 — единственная модель с нативным hybrid search.** Это критическое преимущество: один forward pass вместо трёх отдельных моделей, простота архитектуры, меньше infrastructure debt.

### 6.3. Приватность (для Phase 3, voice)

| Модель | Данные покидают устройство? | Zero-retention? |
|--------|---------------------------|-----------------|
| BGE-M3 (self-hosted) | ❌ | N/A |
| Qwen3 (self-hosted) | ❌ | N/A |
| MITRA-E (self-hosted) | ❌ | N/A |
| Gemini | ✅ Google | ? |
| Voyage | ✅ Voyage AI | Да |
| Cohere | ✅ Cohere | Да (VPC option) |
| OpenAI | ✅ OpenAI | Да |

**Для voice mediation data (Phase 3):** self-hosted модели обязательны по GDPR.

---

## 7. Практические рекомендации по фазам

### Phase 1 (дни 4-14): BGE-M3 self-hosted

```
Retrieval pipeline:
  Query → BGE-M3 (dense + sparse) → Qdrant hybrid search → top-100
       → BM25 с палийским токенайзером → RRF fusion
       → BGE-reranker-v2-m3 → top-10
```

**Стоимость:** $0 (self-hosted на CPU вашего VPS)
**Время embedding 56K чанков:** ~20-30 мин на CPU

### Phase 1 eval (дни 15-16): Параллельная оценка

Запустить eval set на:
1. BGE-M3 (baseline)
2. MITRA-E (Buddhist domain)
3. Qwen3-Embedding-0.6B (dense-only, сравнить с BGE-M3 dense)
4. Gemini Embedding 001 (free tier, API)

**Стоимость:** $0 (все бесплатны)

### Phase 1.5 (дни 64-90): Полная переиндексация

- BGE-M3 для 900K чанков
- Если MITRA-E показала +10% на Pāli — добавить как second index
- GPU: Vast.ai RTX 3090, $0.40/час × 10 мин = $0.07 за полную индексацию

### Phase 3 (месяцы 6-12): On-device

- EmbeddingGemma-300M или nomic-embed-text для mobile (Capacitor + Sherpa-ONNX)
- Кеш частых запросов → не нужен embedding на лету

---

## 8. Финальная рекомендация — Decision Matrix

| Критерий | Вес | BGE-M3 | Qwen3-0.6B | Gemini Emb 001 | MITRA-E | Voyage-4 |
|----------|-----|--------|------------|----------------|---------|----------|
| Retrieval quality | 25% | 7 | 7 | **9** | 8 (Pāli) | 8 |
| Hybrid search native | 20% | **10** | 3 | 3 | 3 | 3 |
| Multilingual (EN+RU+Pāli) | 15% | 8 | 8 | **9** | **10** (Pāli) | 7 |
| Self-host (privacy) | 15% | **10** | **10** | 3 | **10** | 5 |
| Cost (self-host vs API) | 10% | **10** | **10** | 8 | **10** | 7 |
| Ease of setup | 10% | 8 | 8 | **10** | 6 | **10** |
| License (MIT compat) | 5% | **10** | **10** | 5 | 8 | 5 |
| **Взвешенный итог** | 100% | **8.65** | 7.55 | 6.95 | 7.65 | 6.45 |

### Итог

**Первичная модель: BGE-M3** — побеждает за счёт уникального hybrid search и zero-cost self-hosting.

**Вторичная модель: MITRA-E** — для палийского/санскритского контента, если eval подтвердит преимущество.

**Fallback API: Gemini Embedding 001** — если нужен быстрый A/B тест или query-side embedding через API.

---

## 9. Что НЕ стоит делать

1. ❌ **Не использовать OpenAI text-embedding-3-large** — устарел, дорого, нет преимуществ
2. ❌ **Не ставить NV-Embed-v2** — CC-BY-NC (несовместимо с MIT), EN-only
3. ❌ **Не платить за Cohere embed-v4** — 128K контекст не нужен для наших коротких чанков
4. ❌ **Не запускать 8B+ модели на CPU** — слишком медленно для production
5. ❌ **Не привязываться к одному API-провайдеру** — vendor lock-in + re-embedding при смене
6. ❌ **Не пропускать собственный eval** — MTEB scores не переносятся на domain-specific данные

---

## 10. Источники

- MTEB Leaderboard: https://huggingface.co/spaces/mteb/leaderboard (апрель 2026)
- MITRA paper: arXiv 2601.06400 (январь 2026)
- BGE-M3: https://huggingface.co/BAAI/bge-m3
- Qwen3-Embedding: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B
- Gemini Embedding: https://ai.google.dev/gemini-api/docs/embeddings
- Voyage AI: https://docs.voyageai.com
- Cohere embed-v4: https://docs.cohere.com/docs/embed
- Pricing comparison: awesomeagents.ai, tokenmix.ai, pecollective.com (апрель 2026)
- Independent benchmark: zc277584121.github.io (март 2026)

---

*Документ для проекта Dharma RAG. Обновлять при выходе новых моделей.*
