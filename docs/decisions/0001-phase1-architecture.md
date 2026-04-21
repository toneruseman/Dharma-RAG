# ADR-0001: Архитектура Phase 1 (RAG-ядро)

- **Статус:** принято
- **Дата:** 2026-04-21
- **Контекст фазы:** Phase 1 — MVP RAG на SuttaCentral + Access to Insight (~15-80K чанков)

## Контекст

Репозиторий `toneruseman/Dharma-RAG` прошёл несколько итераций планирования.
Ранние коммиты (Day 1–3) и существующий `docker-compose.yml`, `CLAUDE.md`,
`ROADMAP.md` отражают **первоначальную версию плана** с параметрами,
которые были пересмотрены в консолидированном документе `docs/Dharma-RAG.md`
(апрель 2026).

Этот ADR фиксирует окончательные архитектурные решения, на которые мы
опираемся **с Day 1 Phase 1 и далее**, и явно отмечает отличия от ранее
выбранных параметров, чтобы избежать дрейфа.

## Решение

### 1. Модель эмбеддингов

- **Основная (Phase 1):** `BAAI/bge-m3` (568M, MIT), self-hosted.
- **Миграционный путь:** через Qdrant **named vectors** можно параллельно
  добавить второй эмбеддинг (Qwen3-Embedding-4B / GigaEmbeddings для RU)
  без переиндексации. Решение о переключении default — по данным A/B на
  golden set, не раньше Phase 2.

### 2. Векторная БД

- **Qdrant 1.12.x**, self-hosted, Apache 2.0.
- Collection `dharma_v1` с named vectors: `bge_m3_dense` (1024 dim),
  `bge_m3_sparse`.
- FP16 quantization по умолчанию; FP8 рассматривается в Phase 2 после
  выхода стабильных релизов Qdrant с его поддержкой.

### 3. Chunking

- **Структурный**, по границам sutta / section / параграфа.
- **Child-chunk:** ≈384 токена с 15% overlap (fallback, если структурный
  split даёт слишком крупный фрагмент).
- **Parent-chunk:** 1024–2048 токенов для LLM-контекста через
  parent-child retrieval.
- **Pericope-aware:** повторяющиеся канонические формулы (satipaṭṭhāna,
  jhāna и т. п.) хранятся в одном экземпляре с ссылкой на все места
  употребления.

Отличие от ранней версии плана: в `CLAUDE.md` написано «parent-child
150/600 слов». Это **устаревший параметр**; `CLAUDE.md` подлежит
обновлению при следующем техническом проходе по документам.

### 4. Hybrid retrieval

- **3 канала параллельно:** dense (BGE-M3), sparse (BGE-M3 sparse),
  BM25 (Postgres FTS с Pali-aware tokenizer).
- **Fusion:** Reciprocal Rank Fusion (k=60), веса [1.0, 0.8, 0.6] для
  dense/sparse/BM25.
- **Output:** top-20–30 кандидатов → reranker.

### 5. Reranker

- **BGE-reranker-v2-m3** (MIT, 568M), self-hosted.
- Top-30 → top-8 для передачи в LLM.

### 6. Contextual Retrieval

- **Обязательно** для Phase 1 (не опционально).
- Claude Haiku 4.5 через prompt caching, ~$30 одноразово на 56K чанков.
- Prompt-template под буддийский корпус специфичен и лежит в
  `src/processing/contextual_prompt.py`.

### 7. Observability — переход Langfuse → Phoenix

- **Текущее состояние `docker-compose.yml`:** содержит Langfuse + его
  Postgres (из ранней версии плана).
- **Целевое состояние для Day 9 Phase 1:** добавить Phoenix (Arize) как
  primary observability. Langfuse остаётся до тех пор, пока не мигрируем
  трейсинг окончательно.
- **Причина:** Phoenix легче (2 GB RAM vs 16 GB у Langfuse v3), имеет
  готовые RAG-evals и OpenInference-первоклассный, что хорошо ложится
  на наш pipeline. Langfuse рассматривается как апгрейд в Phase 2, если
  понадобится prompt versioning.

### 8. LLM

- **Phase 1 default:** Claude Sonnet 4.6 через Anthropic API (BYOK
  паттерн).
- **Routing:** Haiku для classification / contextual prefix generation,
  Sonnet для основных Q&A, Opus для сложных доктринальных вопросов.
- **Citations API** Anthropic используется как встроенный механизм
  привязки цитат к chars.

### 9. Observability (исходные метрики Phase 1)

Цели Phase 1 (на golden set ≥ 100 QA):

- `ref_hit@5` ≥ 70%
- `faithfulness` ≥ 0.85
- `doctrinal_accuracy` ≥ 4/5 (экспертная оценка буддолога)
- `Krippendorff α` ≥ 0.7 на разметке golden set

### 10. Python / packaging

- Python **3.12+** (3.13 подходит). Версия 3.14 пока исключена из-за
  нестабильности зависимостей.
- Packaging через `hatchling` + PEP 621 (как в текущем `pyproject.toml`).
- Layout: **flat `src/` без вложенного пакета `dharma_rag`**. Импорты
  вида `from src.config import get_settings`. Это расходится с
  предлагаемой ранее вложенной схемой, но соответствует уже коммитнутому
  коду — переключаться на вложенную схему в середине Phase 1
  экономически не оправдано.

## Следствия

1. `CLAUDE.md`, `ROADMAP.md` и прочие документы с параметрами 150/600
   слов, с упоминаниями Langfuse как primary — считаются устаревшими и
   подлежат обновлению в рамках отдельной задачи «docs alignment pass».
2. Любой код-ревью сверяет фактические параметры с этим ADR, а не с
   `CLAUDE.md`, до завершения «docs alignment pass».
3. Изменение любого из пунктов 1–10 требует нового ADR (0002, 0003, …).
4. Миграция Langfuse → Phoenix запланирована на Day 9 Phase 1 и
   трекается отдельно.

## Референсы

- Консолидированный план: `docs/Dharma-RAG.md`
- Day-by-day план разработки RAG-ядра — обсуждается в чате планирования.
