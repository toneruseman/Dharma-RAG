# Dharma RAG: обзор архитектуры и рекомендации по технологиям на 2026

> **Документ:** Архитектурный обзор и критика текущих решений
> **Дата:** Апрель 2026
> **Статус:** Рекомендации к внедрению
> **Аудитория:** Соло-разработчик, Phase 1 → Phase 3

---

## TL;DR

**Текущая архитектура Dharma RAG в целом верная, но содержит несколько критически устаревших компонентов.** Самое срочное — реранкер ms-marco-MiniLM-L-6-v2, отстающий от современных альтернатив на 20+ процентных пунктов по точности, и ставка на dense-only retrieval, провал которого подтверждают собственные бенчмарки проекта (2% ref_hit@5). Специализированная модель для буддийского NLP — **MITRA** (опубликована в январе 2026) — полностью меняет ландшафт для поиска по палийским текстам. Бюджет транскрипции можно сократить с прогнозных ~$14 000 до менее чем $1 000 через Groq Batch API. Live-голосовой чат достижим с задержкой <800мс и стоимостью $0.009/мин через связку Deepgram + Claude Haiku + self-hosted Kokoro TTS — но требует аккуратной инженерии под медитативные сценарии.

---

## Сводный вердикт по текущим архитектурным решениям

| Компонент | Текущий выбор | Вердикт | Рекомендуемая альтернатива |
|---|---|---|---|
| Embedding-модель | BGE-M3 (dense-only) | **АПГРЕЙД** | BGE-M3 hybrid (dense+sparse+ColBERT) + MITRA-E для палийского |
| Векторная БД | Qdrant | **ОСТАВИТЬ** | Qdrant + scalar quantization + mmap на NVMe |
| Hybrid search | Не реализован | **ВНЕДРИТЬ** | RRF-фьюжн dense + sparse + BM25 |
| Реранкер | ms-marco-MiniLM-L-6-v2 | **ЗАМЕНИТЬ** | BGE-reranker-v2-m3 или Cohere Rerank 4 Pro |
| Contextual Retrieval | Планируется | **ВНЕДРИТЬ** | Метод Anthropic через Claude Haiku, разово $20-50 |
| Чанкинг | Parent-child 150/600 слов | **ОСТАВИТЬ + УЛУЧШИТЬ** | Добавить contextual-префиксы; late chunking |
| Транскрипция | OpenAI Whisper API (~$14K) | **ЗАМЕНИТЬ** | Groq Batch API turbo (~$700) + палийский initial_prompt |
| Бэкенд | FastAPI | **ОСТАВИТЬ** | Узкое место — LLM-задержка, не фреймворк |
| Фронтенд Фаза 1 | HTML/JS | **АПГРЕЙД** | HTMX + Jinja2 для streaming SSE без сборки |
| Фронтенд Фаза 2 | SvelteKit | **ОСТАВИТЬ** | SvelteKit 2 + Svelte 5 runes |
| Мобилка | Capacitor | **ОСТАВИТЬ** | + Sherpa-ONNX для on-device voice |
| Telegram-бот | python-telegram-bot | **ЗАМЕНИТЬ** | aiogram 3.x — async-native, FSM |
| Оркестрация LLM | Claude API напрямую | **ОСТАВИТЬ → РАЗВИВАТЬ** | + Pydantic AI для tool use; избегать LangChain |
| Observability | Не указано | **ДОБАВИТЬ** | Langfuse self-hosted (MIT, бесплатно) |
| Voice-чат | Ещё не построен | **СТРОИТЬ** | Pipecat (MVP) → LiveKit Agents (prod) |
| Хостинг | VPS 8GB | **ОСТАВИТЬ** | Hetzner CX32 (€9/мес) → CCX33 (€60/мес) |

---

## A. Embedding и retrieval: стеку нужна хирургия, а не замена

### A.1. Реранкер — апгрейд с наивысшим ROI

Текущий cross-encoder ms-marco-MiniLM-L-6-v2 даёт ~62-65% Hit@1. Современные реранкеры ушли далеко вперёд:

- **BGE-reranker-v2-m3** — ~78% Hit@1, Apache 2.0, мультиязычный, <600M параметров → **+15-20пп drop-in**
- **Cohere Rerank 4 Pro** — ELO 1629, 100+ языков, $2/1K поисков, +170 ELO к предыдущей версии
- **gte-reranker-modernbert-base** — качество миллиардных моделей при 149M параметров и 66мс задержки
- **Zerank 2** — лидирует в рейтинге ELO (1638), задержка 265мс
- **jina-reranker-v3** — 64 документа за проход, контекст 131K токенов, 188мс

### A.2. Hybrid-режим BGE-M3 — ключ, который проект ещё не повернул

BGE-M3 — **единственная embedding-модель, выдающая dense + learned sparse + ColBERT за один проход**. Dense-only проваливается на палийских терминах, потому что subword-токенайзеры режут "satipaṭṭhāna" на бессмысленные куски. Sparse-векторы делают term-level matching аналогично BM25, но с выученными весами.

**Рекомендуемый пайплайн — трёхстадийный:**

1. **Hybrid retrieval (top-100):** BGE-M3 dense + BGE-M3 sparse + BM25 с палийским токенайзером, RRF-фьюжн (k=60)
2. **Реранкинг (top-100 → top-10):** BGE-reranker-v2-m3 (self-hosted) или Cohere Rerank 4 Pro
3. **Генерация:** Claude Haiku/Sonnet с top-10 чанками

### A.3. MITRA меняет всё для поиска по палийским текстам

Самая важная находка: **MITRA** (arXiv 2601.06400, январь 2026) — специализированный фреймворк для буддийского NLP, содержащий 1.74M параллельных пар предложений между санскритом, китайским и тибетским, плюс **Gemma 2 MITRA-E** — domain-specific embedding-модель, обгоняющая BGE-M3, BM25, FastText и LaBSE на буддийских бенчмарках. Открытая лицензия. **Нужно оценить немедленно** как основную embedding-модель для палийского/санскритского контента, параллельно с универсальной моделью для английского через RRF-фьюжн.

### A.4. Иерархия практичности доменной адаптации

1. **Палийский глоссарий для query expansion** — 0 стоимости, немедленный эффект
2. **Contextual Retrieval препроцессинг** (Anthropic method) — Claude Haiku добавляет к каждому чанку буддийский контекст, разово $20-50 на 370K чанков, **−49% до −67% ошибок retrieval**
3. **LoRA файнтюн Qwen3-Embedding-8B или BGE-M3** на буддийских парах — +10-30% по домену

### A.5. Ландшафт embedding-моделей сильно изменился

- **Gemini Embedding 2** (март 2026) — лидер retrieval 67.71, мультимодальная, 3072 dim, $0.10/1M токенов batch
- **Microsoft Harrier-OSS-v1** (MIT) — возглавляет MTEB v2 с 74.3, но требует 80GB+ VRAM
- **Qwen3-Embedding-8B** (Apache 2.0) — 70.58 на MMTEB, 100+ языков, лучший open-source
- **Voyage-4-large** — MoE-архитектура, +14% к OpenAI, $0.12/1M токенов
- **OpenAI text-embedding-3-large** — не обновлялся с января 2024, уже 7-9 место, **не рекомендую для новых проектов**

### A.6. Qdrant остаётся, но нужна правильная конфигурация

Со **scalar quantization + mmap на NVMe** 1M векторов (1024 dim) помещаются в **~1.5-2GB RAM**. Алгоритм ACORN делает фильтрацию по метаданным во время HNSW-обхода (не post-filter). Нативный hybrid через named vectors, встроенная ColBERT late-interaction.

LanceDB — достойная альтернатива (используется Netflix, CodeRabbit), но для соло-разработчика Qdrant проще. Pinecone/Turbopuffer — только облако, не нужны. Milvus переусложнён для 1M векторов.

### A.7. Продвинутый retrieval: LightRAG вместо GraphRAG

Microsoft GraphRAG строит граф через LLM в **100-1000× стоимости vector RAG** ($50-500+ на 370K чанков). **LightRAG** — сопоставимые результаты в 6000× дешевле, с инкрементальными обновлениями. **LazyGraphRAG** (Microsoft 2025) снижает стоимость до уровня vector RAG.

Для буддийских текстов с межтекстовыми связями ценен лёгкий граф на ~200-500 ключевых концепций. В Фазе 1 — вручную как JSON/YAML, в Фазе 2 — LightRAG для автоматической экстракции. Neo4j полностью исключить.

**HyDE** стоит внедрить для концептуальных запросов — генерация гипотетического отрывка даёт embedding ближе к сутте. Турецкие исследования: 85% точности vs 78.7% baseline за одну дополнительную LLM-вызов.

---

## B. Стратегия транскрипции: $700 вместо $14 000

### B.1. Groq Batch API делает экономику тривиальной

| Подход | Стоимость 35K часов | Время | WER |
|---|---|---|---|
| **Groq Batch turbo** | **~$700** | Часы | ~11% |
| **Groq Batch large-v3** | **~$1 943** | Часы | ~10.3% |
| SaladCloud (100 GPU) | ~$200-440 | 1-2 дня | ~7.9% |
| Vast.ai 4×RTX 4090 | ~$400-600 | 2-3 дня | ~7.9% |
| AssemblyAI Universal-2 | ~$5 250 | Дни | ~8.4% |
| OpenAI Whisper API | ~$12 600 | Дни | ~7.9% |
| Локальный GTX 1080 Ti | ~$200 электричество | **200-400 дней** | ~7.9% |

GTX 1080 Ti **отбросить полностью**. Даже б/у RTX 3090 ($700) — 60-90 дней, экономика хуже по всем параметрам.

### B.2. Палийская лексика — четырёхслойная коррекция

**Слой 1: Whisper initial_prompt** — включить ~200 палийских терминов. Бесплатно, немедленно:

```
"This is a Buddhist dharma talk discussing jhāna, dukkha, satipaṭṭhāna,
vedanā, pīti, nimitta, samādhi, vipassanā, ānāpānasati, mettā,
paṭicca samuppāda, anicca, anattā, nibbāna..."
```

**Слой 2: LLM-постобработка** — GPT-4o-mini или Claude Haiku с буддийским глоссарием стандартизирует написания ("sati patana" → "satipaṭṭhāna"). ~$0.003/1K токенов — ничтожно.

**Слой 3: LoRA файнтюн** — 458 лекций Роба Бёрбиа **уже транскрибированы Hermes Amāra Foundation** с правильными написаниями. Идеальный датасет. LoRA (r=32, q_proj/v_proj) на A100, 1-5 часов, ~$50, **−30-50% ошибок палийских терминов**.

**Слой 4: Silero VAD препроцессинг (обязательно)** — Whisper галлюцинирует в тишине ("Subtitles by Amara.org"). `vad_filter=True`, `hallucination_silence_threshold=2`. Calm-Whisper (arXiv 2505.12969) файнтюнит 3 decoder attention heads, снижает non-speech галлюцинации на 80%.

### B.3. NVIDIA Parakeet — джокер по скорости

**Parakeet TDT 1.1B** — RTFx 2000+, 35 000 часов за <30 GPU-часов, **~$20 на A100**. Нативные пунктуация/капитализация, WER 1.8% на LibriSpeech. Минус: только английский, нет initial_prompt, только в NeMo. Двухпроходный подход (Parakeet + LLM-коррекция) — общая стоимость <$100.

### B.4. Рекомендуемый пайплайн транскрипции

```
Аудио → Silero VAD (убрать тишину >2с)
      → Нормализация (16kHz mono, loudnorm)
      → Groq Batch turbo (initial_prompt с палийскими терминами)
      → WhisperX forced alignment (word-level timestamps)
      → pyannote diarization (только Q&A, ~20% корпуса)
      → LLM палийская коррекция (GPT-4o-mini)
      → Сегментация на параграфы
      → Детекция галлюцинаций
      → JSON/VTT с метаданными
```

**Общая стоимость: $950-2 800 за 4-6 недель.**

---

## C. Архитектура продукта: прагматичный минимализм для соло-разработчика

### C.1. FastAPI остаётся

Узкое место RAG — LLM inference (1-5 сек), не сериализация. 2× преимущество Litestar через msgspec нерелевантно. FastAPI: 10K+ req/s, нативные SSE/WebSocket, общий event loop с aiogram и Qdrant-клиентом, 80K+ GitHub stars, first-class интеграция со всеми AI-библиотеками.

### C.2. Frontend: HTMX для Фазы 1

Замените HTML/JS на **HTMX + Jinja2 server-rendered templates**. HTMX — 14KB, streaming SSE chat без JS-сборки:

```html
<div hx-ext="sse" sse-connect="/stream" sse-swap="message"></div>
```

Фаза 2 — **SvelteKit 2 + Svelte 5 runes**: компилируется в vanilla JS, бандлы на 30-50% меньше Next.js, reactivity без React `useEffect`.

### C.3. Мобилка: Capacitor + on-device voice

Capacitor + SvelteKit = **95%+ переиспользования кода**. WebView: ~100мс cold-start — ничтожно для контентного приложения.

**Ключевое улучшение:** on-device через **Sherpa-ONNX** — Whisper-tiny/Zipformer для STT (RTF 0.05, 45MB RAM на iPhone 15 Pro), Kokoro-82M для TTS (~160MB, ELO 1 059). Минус 200мс задержки, 0 стоимости за минуту, офлайн на ретрите, аудио не покидает устройство.

### C.4. LLM-оркестрация: Pydantic AI вместо LangChain

**Слоистый подход:**

1. **Фаза 1:** raw Claude API через `anthropic` SDK — максимум контроля
2. **Фаза 2:** **Pydantic AI** (v1.0 с сентября 2025) для структурированных выводов и tool use (композитор ретритов, генератор уроков)
3. **Выборочно:** компоненты **LlamaIndex** для retrieval-оптимизации

**LangChain полностью пропустить** — сложность непропорциональна пользе, API-нестабильность = нагрузка для соло-разработчика.

**Дополнительно:**
- **DSPy** — 3.5мс overhead, для программной оптимизации промптов
- **Instructor** — для структурированных выводов из Claude (планы уроков, расписания)

### C.5. Observability обязательна

**Langfuse** (MIT, self-hosted Docker Compose):
- 0 стоимости на VPS
- OpenTelemetry → framework-agnostic
- 20K+ GitHub stars, нет vendor lock-in
- На 1M traces/мес: $0 vs ~$2 500 за LangSmith

В паре:
- **Ragas** — метрики retrieval (context precision, faithfulness, answer relevancy)
- **DeepEval** — quality gates в CI/CD через pytest
- **Golden test set** из 150+ дхарма Q&A-пар + кастомная метрика **доктринальной точности**

### C.6. Хостинг: Hetzner + Docker Compose

| Фаза | Сервер | Характеристики | Стоимость/мес |
|---|---|---|---|
| Фаза 1 | Hetzner CX32 | 4 vCPU, 8GB RAM, 80GB NVMe | €9 |
| Фаза 2 | Hetzner CCX33 | 8 dedicated vCPU, 32GB RAM | €60 |
| GPU on-demand | Modal.com | Serverless GPU | $1-2/час |

**Docker Compose достаточно** для 3-5 сервисов. Kubernetes (даже K3s) — +512MB-1GB RAM overhead + операционная сложность. Миграция: `kompose` конвертирует docker-compose.yml в K3s при необходимости.

### C.7. Telegram: aiogram 3.x

**aiogram 3.x:**
- Async-native (python-telegram-bot ретрофитил async в v20)
- Встроенная FSM → guided meditation-флоу
- Middleware для логирования и rate limiting
- Сильное русскоязычное сообщество

---

## D. Live-голосовой чат: дхарма-разговоры за <800мс реальны

### D.1. Pipeline побеждает для буддийского контента

**Оценены три архитектуры:**

1. **Native speech-to-speech** (OpenAI Realtime $0.30/мин, Gemini Live) — низкая задержка, НО нет контроля RAG, нельзя инжектить точные цитаты, 6 пресетов голоса
2. **Hybrid S2S с function calling** — частично решает RAG, но ограничивает качество голоса и палийское произношение
3. **Pipeline STT → Text RAG → TTS — ПОБЕЖДАЕТ:**
   - Точная инъекция цитат между STT и LLM
   - Кастомный спокойный медитативный голос через TTS-клонирование
   - SSML phoneme-подсказки для палийских терминов

У Anthropic **нет voice API на апрель 2026** — pipeline единственный путь для Claude + voice RAG.

### D.2. Бюджет задержки: <800мс достижимы

| Компонент | Цель | Лучший случай | Провайдер |
|---|---|---|---|
| Захват + сеть | 50мс | 20мс | WebRTC через LiveKit |
| STT | 200мс | 150мс | Deepgram Nova-3 streaming |
| End-of-turn detection | 300мс | 200мс | LiveKit turn-detection |
| RAG retrieval + rerank | 100мс | 50мс | Co-located Qdrant |
| LLM first token | 300мс | 150мс | Claude 3.5 Haiku |
| TTS first byte | 200мс | 40мс | Cartesia Sonic Turbo / ElevenLabs Flash 75мс |
| **ИТОГО** | **<800мс** | **~450мс** | — |

**Скрытое узкое место — end-of-turn detection**. Системы добавляют 200-500мс паддинг. LiveKit turn-detection + Pipecat VAD-настройки тюнятся агрессивно. Играть ambient-звук (поющая чаша, природа) ~100мс во время gap — задержка становится психологически невидимой.

### D.3. Модель стоимости делает голос устойчивым

| Конфигурация | Total/мин | 100 юзеров × 10 мин/день |
|---|---|---|
| **Бюджетная** (Deepgram + Haiku + Kokoro self-hosted) | **$0.009** | **$27/мес** |
| **Сбалансированная** (Deepgram + Sonnet + ElevenLabs Flash) | **$0.046** | **$138/мес** |
| **Премиум** (Deepgram + Sonnet + ElevenLabs v3) | **$0.098** | **$294/мес** |
| **OpenAI Realtime** | **$0.30** | **$900/мес** |

При бюджетной конфигурации **10 000 concurrent × 10 мин = ~$27 000/мес** — доля от $900 000/мес OpenAI Realtime на том же масштабе. Self-hosted Kokoro-82M (ELO 1 059, #9 TTS Arena) — рычаг стоимости.

### D.4. Voice-фреймворк: Pipecat для MVP, LiveKit для prod

- **Pipecat** (Daily.co, open-source) — Python-first, transport-agnostic, пайплайн STT→LLM→TTS. MVP за часы.
- **LiveKit Agents** — WebRTC-native, превосходный turn-detection, обработка прерываний, горизонтальный скейлинг.

### D.5. Инженерия под медитацию

Voice-чат для guided-медитации требует **фич, которых нет ни в одном фреймворке**:

- **Push-to-talk во время активной медитации** — предотвращает случайную активацию голоса
- **VAD с повышенным порогом** — только намеренная речь триггерит систему
- **SSML-паузы** `<break time="5s"/>` — натуральная тишина без интерпретации как команды продолжить
- **Микшер Web Audio API** — TTS + ambient (колокола, чаши, природа) через `AudioContext` и `GainNode`
- **Трекинг состояния сессии** — фаза медитации, elapsed time, reported state, прерывания возобновляются с правильной точки
- **Словарь палийского произношения** → SSML:
  ```xml
  <phoneme alphabet="ipa" ph="dʒʰɑːnə">jhāna</phoneme>
  ```

### D.6. Архитектура приватности

Voice-данные медитации — **биометрические по GDPR**, контекст уязвимых лиц → обязательный DPIA.

- **On-device STT/TTS по умолчанию** через Sherpa-ONNX — аудио не покидает устройство
- **Облако только для LLM+RAG** — отправлять текст, не аудио. Claude API по умолчанию не использует данные для обучения
- **Zero-retention** для всех облачных сервисов (Deepgram, Anthropic, Groq — поддерживают)
- **Авто-удаление данных сессии** через 30 дней; GDPR Article 17 → немедленное удаление по запросу
- **Без логирования аудио** — обработать и отбросить

---

## Критические проблемы, не отражённые в текущем плане

**1. Dharmaseed CC-BY-NC-ND блокирует derivatives.** 46 219 лекций под "No Derivatives". Транскрипция может быть derivative. Нужен явный юридический анализ или разрешение до публикации транскриптов. Consent Ledger должен адресовать это явно.

**2. 2% ref_hit@5 — провал не только модели, но и чанкинга.** Hybrid search поможет, но если 150-словные children режутся посередине концепции, retrieval провалится независимо от embedding. Оценить **proposition-based chunking** (87% vs 13% для fixed-size в клинических исследованиях) и **late chunking** для длинных лекций.

**3. Нет фреймворка оценки.** Без golden test set и метрик каждое изменение — догадка. Построить 150+ Q&A пар **немедленно** — до любых изменений моделей. Цели: faithfulness >0.85, context precision >0.8, кастомная доктринальная точность.

**4. Семантическое кеширование отсутствует.** Дхарма-запросы высоко кешируемы: "Как справляться с беспокойством" ≈ "Что делать с помехой беспокойства" ≈ "Беспокойство в медитации". Отдельная Qdrant-коллекция (question-embedding + response, cosine >0.92) даёт **40-60% cache hit rate** → резкое снижение LLM-стоимости.

**5. Нет graceful degradation.** Сбои Claude API, rate limits, задержки случаются. Нужен fallback (Claude → OpenAI → локальная Llama) через **LiteLLM**, кешированные ответы, ambient-аудио во время задержек в voice-чате.

**6. Audio-компаньон и uncanny valley.** AI-сгенерированный гид, звучащий чуть неправильно, может нарушить медитацию сильнее, чем отсутствие гида. Рассмотреть пред-генерацию и human-review медитативных скриптов для guided-сессий вместо real-time.

**7. Палийская романизация.** Разные источники: satipaṭṭhāna vs satipattana vs sati-patthana. Нужен слой нормализации в каноническую форму до embedding и поиска.

---

## Рекомендуемая архитектура v2

### Фаза 1 — MVP ($80-130/мес, недели 1-8)

```
┌─────────────────────────────────────────────────┐
│ Hetzner CX32 (8GB, €9/мес) — Docker Compose     │
│                                                  │
│  ┌────────────┐  ┌──────────────────────────┐   │
│  │  FastAPI   │  │  Qdrant (scalar quant    │   │
│  │  + HTMX    │←→│  + mmap, ~2GB RAM)       │   │
│  │  + SSE     │  │  Dense + Sparse + Cache  │   │
│  └─────┬──────┘  └──────────────────────────┘   │
│        │                                          │
│  ┌─────┴──────┐  ┌──────────────────────────┐   │
│  │ aiogram 3  │  │  Langfuse (self-hosted)  │   │
│  │ Telegram   │  │  Observability           │   │
│  └────────────┘  └──────────────────────────┘   │
└─────────────────────────────────────────────────┘
        ↕                    ↕
  Claude API             Cloudflare Pages
  (Haiku/Sonnet)         (HTMX фронтенд)
```

**Стек Фазы 1:**
- Embedding: BGE-M3 hybrid + MITRA-E для палийского, RRF-фьюжн
- Реранкер: BGE-reranker-v2-m3 self-hosted
- LLM: Claude Haiku (роутинг) → Sonnet (сложное) через raw SDK
- Frontend: HTMX + Jinja2 + SSE
- Cache: семантический в Qdrant

### Фаза 2 — Полная платформа ($300-500/мес, месяцы 3-6)

+ SvelteKit 2, + Capacitor Android/iOS, + Pydantic AI (retreat composer, lesson generator), + LlamaIndex retrieval, + Cytoscape.js concept graphs, + Voice MVP (Pipecat + Deepgram + ElevenLabs Flash). Апгрейд Hetzner CCX33 (32GB, €60/мес).

### Фаза 3 — Voice и масштаб ($500-1000/мес, месяцы 6-12)

+ LiveKit Agents, + Sherpa-ONNX on-device в Capacitor, + LightRAG knowledge graph, + self-hosted Kokoro-82M, + медитативные voice-фичи.

---

## Модель стоимости v2

### Разовые затраты

| Элемент | Стоимость |
|---|---|
| Транскрипция 35K часов (Groq Batch turbo) | $700-2 000 |
| Палийская LLM-коррекция (GPT-4o-mini) | $200-500 |
| Speaker diarization 7K часов Q&A | $100-150 |
| LoRA файнтюн (A100 × 5ч) | $50 |
| Contextual Retrieval препроцессинг | $20-50 |
| Embedding-генерация 1M чанков | $10-60 |
| **ИТОГО разовых** | **$1 080-2 810** |

### Ежемесячные затраты

| Компонент | Фаза 1 | Фаза 2 | Фаза 3 |
|---|---|---|---|
| Hetzner сервер | €9 | €60 | €60-120 |
| Claude API | $50-100 | $150-300 | $200-400 |
| Voice (Deepgram + TTS) | $0 | $30-60 | $50-200 |
| Embedding API | $5-10 | $10-20 | $10-20 |
| Домен/DNS/CDN | $2 | $22 | $22 |
| Modal GPU on-demand | $0 | $10-30 | $20-50 |
| **ИТОГО/мес** | **$70-125** | **$290-500** | **$370-820** |

---

## План внедрения

### Недели 1-2: Фундамент
- **Golden eval test set** (150+ Q&A) — до любых изменений моделей
- Langfuse observability
- BGE-M3 hybrid (sparse + ColBERT в Qdrant)
- Замена реранкера на BGE-reranker-v2-m3
- Оценка MITRA-E на палийском
- *Параллельно:* Groq Batch на 100 пилотных лекциях

### Недели 3-4: Качество retrieval
- Contextual Retrieval для всех 370K чанков
- Палийский глоссарий (200-500 терминов)
- Семантический кеш в Qdrant
- HTMX фронтенд с SSE
- *Параллельно:* LoRA-файнтюн Whisper на транскриптах Бёрбиа

### Недели 5-8: Пайплайн транскрипции
- Полная 35K-часовая транскрипция Groq Batch
- LLM палийская коррекция
- Diarization для Q&A
- Chunk + embed в Qdrant
- aiogram Telegram-бот

### Месяцы 3-4: Фронтенд + мобилка
- SvelteKit 2 + streaming chat
- Capacitor Android/iOS
- Pydantic AI для retreat composer, lesson generator
- Cytoscape.js concept graphs

### Месяцы 5-6: Voice MVP
- Pipecat + Deepgram + Haiku + ElevenLabs Flash
- Словарь палийского произношения для TTS
- WebSocket streaming в FastAPI
- End-to-end тест latency budget

### Месяцы 7-12: Voice prod + advanced
- Миграция на LiveKit Agents
- Sherpa-ONNX on-device в Capacitor
- Медитативные voice-фичи
- LightRAG knowledge graph
- Self-hosted Kokoro-82M
- Curriculum planner + spaced repetition

---

## Анализ рисков

| Риск | Тяжесть | Вероятность | Митигация |
|---|---|---|---|
| **CC-BY-NC-ND Dharmaseed блокирует публикацию** | Критично | Средняя | Искать разрешение; fair-use анализ; worst case — внутреннее использование без публикации |
| **Палийские термины стабильно мистранскрибируются** | Высокая | Высокая | 4-слойный пайплайн; LoRA файнтюн; human-review глоссария |
| **Claude API стоимость взлетает с voice** | Высокая | Средняя | Semantic cache (40-60% hit), fallback на Haiku, self-hosted Llama, rate limiting |
| **Задержка голоса >800мс в prod** | Средняя | Средняя | Ambient-аудио во время gap; pre-cache guided meditations; on-device bypass |
| **Выгорание соло-разработчика** | Высокая | Высокая | Фазировать безжалостно; web-first; Capacitor code reuse |
| **Qdrant OOM на 8GB VPS** | Средняя | Низкая | Scalar quant + mmap → ~2GB RAM; апгрейд 16GB (+€4/мес) |
| **Доктринальная неточность** | Критично | Средняя | Faithfulness >0.85; обязательные цитаты; дисклеймер "AI — не учитель" |
| **Утечка voice-приватности** | Критично | Низкая | On-device по умолчанию; zero-retention API; без логов; DPIA |
| **Vendor lock-in** | Средняя | Средняя | Pipeline позволяет замену; LiteLLM; Kokoro fallback |

### Самый опасный риск — доктринальный

RAG-система, уверенно искажающая буддийские учения — смешивающая Тхераваду и Махаяну по anattā, или неправильно описывающая факторы джханы — может нанести реальный вред практикующим. **Каждый ответ должен цитировать конкретные источники** (имя сутты, параграф, timestamp лекции). System prompt обязан **явно инструктировать Claude говорить "я не знаю"** вместо фабрикации. Метрика faithfulness не опциональна — это единственный самый важный quality gate всей системы.

---

## Источники и ссылки

- MITRA: arXiv 2601.06400 (январь 2026)
- Anthropic Contextual Retrieval: anthropic.com/news/contextual-retrieval
- Calm-Whisper: arXiv 2505.12969
- Hermes Amāra Foundation (транскрипты Роба Бёрбиа): hermesamara.org
- Groq Batch API pricing: groq.com/pricing
- Hetzner Cloud: hetzner.com/cloud
- BGE-M3: huggingface.co/BAAI/bge-m3
- BGE-reranker-v2-m3: huggingface.co/BAAI/bge-reranker-v2-m3
- Pipecat: github.com/pipecat-ai/pipecat
- LiveKit Agents: docs.livekit.io/agents
- Langfuse: langfuse.com
- Ragas: docs.ragas.io
- Sherpa-ONNX: github.com/k2-fsa/sherpa-onnx
- Kokoro TTS: huggingface.co/hexgrad/Kokoro-82M

---

*Документ создан для проекта Dharma RAG. Лицензия документа: CC-BY-SA 4.0.*
