# LLM-модели для `/api/answer` — сравнительная оценка (rag-day-24)

> **RELATIVE METRICS — NOT AUTHORITATIVE.** Цифры из эмпирических
> прогонов одного типичного запроса («что такое джхана?») через
> production pipeline. Дельты между моделями валидны для ranking —
> абсолютные утверждения о качестве LLM-вывода требуют буддологической
> валидации (B-001).

## Зачем этот документ

После запуска `POST /api/answer` (rag-day-24) обнаружились два вопроса:
1. **Текущий default `claude-haiku-4.5` теряет канонические similes** —
   запоминающиеся метафоры из Pali Canon (банщик / озеро / лотос /
   белая ткань) не появляются в ответах Haiku.
2. **Opus 4.6** даёт эталонное качество, но стоит **$0.10 за запрос** —
   слишком дорого для дефолта.

Прогнал 16 моделей через `scripts/compare_answer_models.py` против
gold-стандарта (Opus 4.6) чтобы найти best cost/quality tradeoff.

## Тестовый запрос

- **Query**: «что такое джхана?» (русский, фундаментальный буддийский
  термин — требует depth)
- **Style**: `detailed` (max_tokens=3072)
- **top_k**: 5 (стандартная конфигурация retrieval'а)
- **Pipeline**: `dharma_v2 + rerank=False + expand_parents=True + expand_pali=True`

Вход: ~9-10K токенов (system + 5 source-passage'ей по 1.5-2K + query).

## Критерии оценки

1. **Канонические similes** — есть ли все 4: банщик (Sutta MN 39),
   озеро питаемое родником, лотосы, человек укутанный белой тканью.
   Это **часть канона**, не украшение.
2. **Anupubba-nirodha** — отдельная секция «что прекращается на каждом
   уровне» (DN 33): чувственные восприятия (1-я), vitakka-vicāra (2-я),
   восторг (3-я), дыхание (4-я). Niche, но дифференциатор глубины.
3. **Prerequisites** — пять помех (nīvaraṇa) с метафорой долг / болезнь
   / тюрьма / рабство / пустыня (MN 39).
4. **Pāli с диакритиками** — `jhāna`, `samādhi`, `vitakka`, `vicāra`,
   `upekkhā`, `nīvaraṇa`. Кириллическая транслитерация — допустимо, но
   полные diacritics предпочтительнее для буддийского контекста.
5. **9 прогрессивных медитаций** — 4 джханы + 4 бесформенных + cessation.
6. **Три высших знания** — past lives / death+rebirth / āsavakkhaya.
7. **Citation format** — корректный `[work_id]` или `[mn39, dn10]`,
   без галлюцинаций.
8. **Length / detail** — соответствие `style=detailed`.

## Полная таблица 16 моделей

| модель | $/Mtok in | $/Mtok out | $ /req | latency | tok_out | similes | anupubba | Pāli | prereq | grade |
|---|---:|---:|---:|---:|---:|:---:|:---:|---|:---:|---|
| `anthropic/claude-opus-4.6` | $5.00 | $25.00 | $0.10 | 40-48s | 2070-2405 | ✅✅✅✅ | ✅ | full | ✅ | **A+ (gold)** |
| `moonshotai/kimi-k2-thinking` | $0.60 | $2.50 | $0.012 | 49s | 2667 | ✅✅✅✅ | ❌ | partial | ✅ | **A** |
| `deepseek/deepseek-v4-flash` | $0.14 | $0.28 | **$0.003** | 14-25s | 1074-2018 | ✅✅✅✅ | ⚠️частично | full | ✅ | **A−** |
| `x-ai/grok-4.1-fast` | $0.20 | $0.50 | $0.003 | 13-16s | 1820-1911 | ✅✅✅✅ | ✅ | full | ✅ | A− (lang-mix) |
| `google/gemini-3-flash-preview` | $0.50 | $3.00 | $0.007 | **6.7s** | 883 | ✅ | ❌ | full | ✅ | A− |
| `anthropic/claude-sonnet-4.6` (rag-23 test) | $3.00 | $15.00 | $0.047 | 23s | 1174 | ✅✅✅✅ | ❌ | ✅ | ✅ | A− |
| `anthropic/claude-opus-4.5` | $5.00 | $25.00 | $0.085 | 28s | 1464 | ✅✅✅✅ | ❌ | ✅ | ✅ | A− |
| `anthropic/claude-opus-4.7` | $5.00 | $25.00 | $0.113 | 23s | 1847 | ✅✅✅✅ | ✅ | full | ✅ | A− |
| `qwen/qwen3-235b-a22b-2507` | $0.07 | $0.10 | $0.001 | 37-53s | 1395-1479 | ✅✅✅✅ | ❌ | ✅ | cyrillic only | B+ |
| `deepseek/deepseek-r1` | $0.70 | $2.50 | $0.011 | 69s | 1801 | ✅✅✅✅ | ❌ | ✅ | extensive | B+ |
| `anthropic/claude-sonnet-4.5` | $3.00 | $15.00 | $0.051 | 25s | 1445 | ❌ | ❌ | excellent | ❌ | B+ |
| `z-ai/glm-4.5-air` | $0.13 | $0.85 | $0.002 | 20s | 1349 | ✅✅✅✅ | ⚠️частично | partial | ✅ | B+ |
| `deepseek/deepseek-v3.2` | $0.25 | $0.38 | $0.003 | 20-26s | 871-872 | ✅✅ | ❌ | partial | ✅ | B |
| `mistralai/mistral-small-3.2-24b-instruct` | $0.07 | $0.20 | $0.001 | 7-12s | 835-1058 | ❌ | ❌ | min | ❌ | C (broken `()` cite) |
| `anthropic/claude-haiku-4.5` (prior default) | $1.00 | $5.00 | $0.014 | 19-36s | 657-766 | ❌ | ❌ | min | ❌ | C |
| `qwen/qwen3-next-80b-a3b-thinking` | $0.10 | $0.78 | $0.001-0.005 | 34s | 6573 (thinking) | ❌ | ❌ | partial | ❌ | C+ |
| `meta-llama/llama-4-maverick` | $0.15 | $0.60 | $0.001 | 9-19s | **369-459** | ❌ | ❌ | partial | ✅ | D+ |
| `meta-llama/llama-4-scout` | $0.08 | $0.30 | $0.001 | 2-6s | **309-362** | ❌ | ❌ | min | ❌ | F (too short) |
| `openai/gpt-4o-mini` | $0.15 | $0.60 | $0.001 | 4s | **392-395** | ❌ | ❌ | min | ❌ | D (too short) |
| `google/gemini-2.0-flash-lite-001` | $0.07 | $0.30 | $0.001 | **3.6s** | 426-434 | ❌ | ❌ | min | ❌ | D (too short) |

## Рекомендация по tier'ам

| tier | модель | $/req | latency | use-case |
|---|---|---:|---:|---|
| **gold (reference)** | `anthropic/claude-opus-4.6` | $0.10 | 40-48s | golden standard для eval, единственный с anupubba-nirodha |
| **premium** | `moonshotai/kimi-k2-thinking` | $0.012 | 49s | future `/api/answer?premium=true`, ~A качество за **8×** меньше Opus |
| **default** ⭐ | `deepseek/deepseek-v4-flash` | **$0.003** | 14-25s | balanced cost/quality, **15× дешевле прежнего Haiku 4.5** |
| **fast (UX)** | `google/gemini-3-flash-preview` | $0.007 | **7s** | если важен real-time UX |
| **budget** | `z-ai/glm-4.5-air` | $0.002 | 20s | дешевейший competent |

Текущая прод-конфигурация (после rag-day-24 follow-up):
- `Settings.answer_llm_model = "deepseek/deepseek-v4-flash"`
- `Settings.answer_llm_model_premium = "moonshotai/kimi-k2-thinking"`

## Главные insights

### 1. Llama 4 family не подходит для `style=detailed`

И **Scout** (309-362 tok) и **Maverick** (369-459 tok) на нашем prompt'е
выдают короткие ответы независимо от `style=detailed`. System prompt их
не разворачивает. Возможно, Llama-4 instruct-tuning делает их
по-умолчанию краткими. **Не ставить ни в один tier.**

### 2. Mistral Small 3.2 — broken citation format

Цитирует через `(mn65, mn39)` (круглые скобки) вместо канонического
`[mn65]`. Наш regex `\[([^\[\]]+)\]` корректно отвергает — `citations`
остаётся пустым. Это **provider-specific instruction-following**
проблема. Можно фиксить более строгим prompt'ом, но дешевле просто не
использовать Mistral.

### 3. Reasoning-mode не помогает (для нашей задачи)

- **Qwen3-next-thinking**: 6573 «thinking» токенов → короткий и мелкий
  visible answer (~600 слов, без similes). Cost ↑ без quality.
- **DeepSeek R1**: 69s latency, 1801 tok — depth есть, но без anupubba
  и формless attainments. **5× медленнее** V4 Flash, не стоит цены.

Reasoning-режим помогает на математике/логике; для retrieval-grounded
RAG-Q&A он не даёт прироста.

### 4. Pāli с диакритиками — provider-specific

- **Anthropic** family — образцовый (jhāna, paṭiccasamuppāda везде)
- **DeepSeek V4 Flash** — почти не уступает (rūpa-jhāna, arūpa-samāpatti)
- **Grok 4.1 Fast** — full diacritics, но **mixing английский** в quote'ах
- **Qwen / GLM / DeepSeek V3.2** — кириллической транслитерацией
  курсивом (читабельно, но менее канонично)
- **Llama / GPT-4o-mini / Gemini Lite** — минимум, только `jhāna`

### 5. Latency-cost-quality frontier

После gold (`Opus 4.6 @ $0.10/40s`) реальный pareto-frontier:
- **`Kimi K2 Thinking @ $0.012/49s`** — premium tier
- **`DeepSeek V4 Flash @ $0.003/14s`** — default
- **`Gemini 3 Flash Preview @ $0.007/7s`** — fast UX
- **`GLM 4.5 Air @ $0.002/20s`** — budget

Всё, что выше этих по $/quality — overpriced. Всё, что ниже — недостаточное качество.

## Воспроизведение

```bash
# 1. Запустить uvicorn в real-режиме (real backend, OPENROUTER_API_KEY в env)
$env:RAG_BACKEND="real"; .venv\Scripts\python.exe -m uvicorn src.api.app:app --reload

# 2. В новом окне — запустить comparison
.venv\Scripts\python.exe scripts\compare_answer_models.py "что такое джхана?" --style detailed --top-k 5 --models anthropic/claude-opus-4.6,deepseek/deepseek-v4-flash,moonshotai/kimi-k2-thinking,google/gemini-3-flash-preview,z-ai/glm-4.5-air

# Wallclock ~3-5 мин, стоимость ~$0.13.
```

Per-run отчёты пишутся в `docs/MODEL_COMPARISON_<timestamp>.md`
(gitignored — это эфемерные артефакты). Этот файл — стабильный
сводный референс.

## Связанные документы

- [docs/concepts/15-answer-generation.md](concepts/15-answer-generation.md) — концепт-док `/api/answer`
- [docs/CONTRACT_ANSWER.md](CONTRACT_ANSWER.md) — публичный API контракт
- [scripts/compare_answer_models.py](../scripts/compare_answer_models.py) — comparison-скрипт

## Следующие шаги

1. **Buddhologist eval (B-001)** — все эти оценки relative.
   Авторитетные качественные claims требуют буддолога.
2. **Streaming (SSE)** — для UX даже Gemini 3 Flash 7s заметная задержка.
   Когда дойдём до Reading Room (app-day-04), нужен streaming endpoint.
3. **Periodic re-eval** — модели на OpenRouter обновляются. Гонять этот
   compare-skript раз в квартал или после announcements о новых
   flagship-моделях.
