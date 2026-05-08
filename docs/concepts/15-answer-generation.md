# 15 — LLM-генерация ответов (rag-day-24)

> **Статус:** реализовано в rag-day-24. Endpoint `POST /api/answer`,
> default LLM `anthropic/claude-haiku-4.5` через OpenRouter.

## Зачем нужно

`POST /api/query` (rag-day-19) возвращает 5 source-чанков из корпуса —
голый retrieval, без ответа на вопрос. Phase 2 декларировала **«add
LLM generation on top of retrieval»** — этот день закрывает.

Новый endpoint `POST /api/answer` принимает запрос, делает retrieval
(переиспользуя `RAGService`), и отдаёт **связный ответ** с inline-
цитатами в формате `[mn36]`, `[sn56.11]` — пользователь сразу видит
текст ответа и список цитированных суттр.

## Архитектура

```
┌─────────────────────────────────────────┐
│        POST /api/answer                 │
│        (src/api/answer.py)              │
└────────────┬────────────────────────────┘
             ↓
┌─────────────────────────────────────────┐
│  AnswerService                          │  src/answer/service.py
│  ┌─────────────────────────────────┐    │
│  │ 1. RAGService.query()           │────┼──→ /api/query layer
│  │    (sources, metadata)          │    │     (retrieval + glossary
│  │                                 │    │      + parent expansion)
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │ 2. AsyncOpenRouterLLM.complete()│────┼──→ OpenRouter API
│  │    (system_prompt + sources +   │    │     (Claude Haiku 4.5)
│  │     query → answer text)        │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │ 3. _extract_citations()         │    │
│  │    (parse [work_id] mentions)   │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
             ↓
        AnswerResponse
        ├─ answer: "Mindfulness is taught in [mn10]..."
        ├─ sources: [...]            ← copied from RAG
        ├─ citations: ["mn10", ...]  ← extracted from answer
        ├─ latency_ms                ← total
        ├─ retrieval_latency_ms      ← split
        ├─ llm_latency_ms            ← split
        └─ metadata
            ├─ pipeline_version
            ├─ llm_model
            ├─ llm_tokens_in/out
            └─ retrieval_metadata    ← embedded full PipelineMetadata
```

**Композиция, не наследование.** `AnswerService` не реализует
retrieval сам — он зависит от `RAGServiceProtocol`. То же для LLM —
зависит от `AsyncOpenRouterLLM` (тонкая обёртка над `openai.AsyncOpenAI`).
Каждый слой можно стабовать независимо в тестах.

## System prompt

Полный текст в `src/answer/service.py::SYSTEM_PROMPT`. Ключевые
правила:

1. **Отвечать ТОЛЬКО на основе предоставленных source-passage'ей.**
   Никакого outside knowledge, никаких догадок.
2. **Язык ответа = язык вопроса.** Русский вопрос → русский ответ;
   английский → английский. Claude хорошо распознаёт это сам.
3. **Inline-цитаты в формате `[work_id]`.** Например «как учил Будда
   [mn36]». work_id показан над каждым source-passage в user message.
4. **Если источников недостаточно — честно сказать «не знаю».**
   Образцы fallback'а в обоих языках: «На основе предоставленных
   источников нельзя ответить» / «The provided passages do not
   directly address X.»
5. **Палийские термины с диакритиками** (jhāna, paṭiccasamuppāda,
   dukkha) при первом упоминании; transliteration или перевод —
   опционально дальше.
6. **Theravāda-корректность.** Не смешивать с Mahāyāna / Vajrayāna,
   если source явно их не упоминает.
7. **Краткость.** 2-4 предложения с цитатами лучше длинного
   парафраза.

## Формат user message

```
The following passages from the Pāli Canon were retrieved as relevant to the user's question.

--- Source 1 [mn10] (mn10:8.1) ---
{full text of parent chunk, ~1024-2048 tokens}

--- Source 2 [sn56.11] (sn56.11:5.1) ---
{full text of parent chunk}

User question: что такое дуккха?
```

work_id в квадратных скобках над каждым passage — это **ключ к
цитированию**. Модель учится цитировать ровно эти id'ы.

## Citation extraction

`_extract_citations(answer_text, source_ids)` — простой regex
`\[([a-zA-Z0-9._-]+)\]` против set'а реально retrieved work_id'ов.

- Совпало с известным id → попадает в `citations` массив
- Совпало с неизвестным (галлюцинация модели) → **пропускается**
- Дубликаты убираются с сохранением first-appearance order

В answer-тексте hallucinated `[an99.99]` остаётся как есть (мы не
переписываем ответ модели), но в structured `citations` поле его нет.

## Production-параметры

### LLM модель

Default: **`deepseek/deepseek-v4-flash`** через OpenRouter (выбран после
16-моделей сравнения — см. [`docs/EVAL_ANSWER_MODELS.md`](../EVAL_ANSWER_MODELS.md)).
Альтернативные tier'ы:

| tier | модель | $/req | latency | когда использовать |
|---|---|---:|---:|---|
| **default** | `deepseek/deepseek-v4-flash` | $0.003 | 14-25s | balanced cost/quality |
| **premium** | `moonshotai/kimi-k2-thinking` | $0.012 | 49s | максимальная глубина (резерв) |
| **fast** | `google/gemini-3-flash-preview` | $0.007 | 7s | UX-aware (для будущего streaming endpoint) |
| **gold** (eval ref) | `anthropic/claude-opus-4.6` | $0.10 | 40-48s | golden standard |

Premium tier настраивается через `Settings.answer_llm_model_premium` и
зарезервирован для будущего slow-endpoint'а с богатыми ответами.

#### Pre-day-24-follow-up history

Изначальный default был `anthropic/claude-haiku-4.5`. Прогон через
все 16 моделей показал что Haiku теряет канонические similes (банщик /
озеро / лотос / ткань) и пишет короче 1000 токенов на `style=detailed` —
проигрывает DeepSeek V4 Flash по качеству при **~5× большей цене**.

| параметр | значение | почему |
|---|---|---|
| temperature | 0.2 | низкое — модель «честная» к источникам, не творческая |
| max_tokens | 1024 | хватает на длинный многоязычный ответ с цитатами |
| API | OpenRouter (OpenAI-compatible) | единый шлюз для Anthropic/Google/DeepSeek |
| Per-call override | `request.model` | A/B без рестарта |

### Settings

```python
answer_llm_model: str = Field(default="anthropic/claude-haiku-4.5")
```

Меняется через env: `ANSWER_LLM_MODEL=anthropic/claude-3.5-haiku`.

### Latency (на GTX 1080 Ti, prod-сетап)

- Retrieval: ~80 мс (rag-day-19)
- LLM на 5 sources: ~1.5-3 сек (Haiku 4.5)
- **Total: ~2-3 сек**

Не подходит для streaming-UX. Для real-time UI понадобится Server-
Sent Events (SSE) — в следующей итерации.

## Backend selection (stub vs real)

Тот же паттерн что и в rag-day-19/app-day-02:

| `RAG_BACKEND` | `/api/answer` поведение |
|---|---|
| **stub** | `StubAnswerService` — fixture-ответ ~2 ms, без OpenRouter |
| **real** | `AnswerService` — full retrieval + Claude Haiku 4.5 |

Stub-ответ:

```
[Stub answer — RAG_BACKEND=stub.] Mindfulness of the body is central
to liberation, taught in the Satipaṭṭhāna Sutta [mn10] and its longer
parallel [dn22]. The First Noble Truth declares all five aggregates
as dukkha [sn56.11]. This response is fixture data — set
RAG_BACKEND=real for genuine LLM output.
```

— детерминированный, цитирует все 3 fixture-source'а из stub-RAG'а,
позволяет фронтенду тестировать citation-rendering без OpenRouter
ключа.

## Что **не** делаем сегодня

- **Streaming (SSE)** — добавим в app-track когда UI потребует. POST
  endpoint возвращает целиком собранный ответ.
- **Conversation history (multi-turn)** — каждый запрос изолирован.
- **Function/tool calling** — out of scope, чистый RAG.
- **Citation verification** — не проверяем что цитата `[mn36]` реально
  ссылается на корректное содержание retrieved-source'а; верим
  модели.
- **Адаптивный prompt по языку** — один system prompt на всех. RU/EN
  разводит сама модель.
- **Rate limiting** — нет на endpoint'е.

## API контракт

См. [`docs/CONTRACT_ANSWER.md`](../CONTRACT_ANSWER.md). Кратко:

```http
POST /api/answer
Content-Type: application/json

{
  "query": "что такое джхана?",
  "top_k": 5,
  "expand_pali": null,
  "forbidden_works": null,
  "model": null
}
```

Ответ:

```json
{
  "query": "что такое джхана?",
  "answer": "Джхана — это глубокое медитативное погружение [mn36]...",
  "sources": [
    {"work_canonical_id": "mn36", "text": "...", "snippet": "...", "score": 0.91, ...},
    ...
  ],
  "citations": ["mn36", "an9.36"],
  "latency_ms": 2154.3,
  "retrieval_latency_ms": 84.1,
  "llm_latency_ms": 2068.0,
  "metadata": {
    "pipeline_version": "dharma_v2-rerank0-parents1-pali1",
    "llm_model": "openrouter/anthropic/claude-haiku-4.5",
    "llm_tokens_in": 1820,
    "llm_tokens_out": 124,
    "retrieval_metadata": {...}
  }
}
```

## Файлы

| файл | роль |
|---|---|
| `src/answer/schemas.py` | `AnswerRequest`, `AnswerResponse`, `AnswerMetadata` |
| `src/answer/protocol.py` | `AnswerServiceProtocol` для stub/real seam |
| `src/answer/service.py` | `AnswerService` + `SYSTEM_PROMPT` + цитирование |
| `src/answer/llm.py` | `AsyncOpenRouterLLM` async-обёртка |
| `src/answer/factory.py` | `get_answer_service` диспатч по `rag_backend` |
| `src/api/_answer_stub.py` | `StubAnswerService` для frontend dev |
| `src/api/answer.py` | router + `install_router` |
| `src/api/app.py` | mount answer router после query router |
| `docs/CONTRACT_ANSWER.md` | публичный API контракт (для frontend) |

## Связанные документы

- [docs/concepts/13-rag-service-contract.md](13-rag-service-contract.md) — `/api/query` контракт
- [docs/concepts/14-pali-glossary.md](14-pali-glossary.md) — глоссарий, который влияет на retrieval
- [docs/CONTRACT_ANSWER.md](../CONTRACT_ANSWER.md) — публичный контракт endpoint'а
