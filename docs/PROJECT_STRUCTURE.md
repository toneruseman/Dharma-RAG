# Project Structure

> Структура файлов и каталогов репозитория Dharma RAG.

```
dharma-rag/
├── README.md                       # Главная страница
├── LICENSE                         # MIT
├── ROADMAP.md                      # Дорожная карта
├── CHANGELOG.md                    # История изменений (создаётся постепенно)
├── pyproject.toml                  # Python зависимости и конфиг
├── docker-compose.yml              # Локальная разработка (Qdrant, Langfuse)
├── docker-compose.prod.yml         # Production (создаётся в Phase 4)
├── Dockerfile                      # Образ приложения (создаётся в Phase 4)
├── .env.example                    # Шаблон переменных окружения
├── .gitignore
├── .github/
│   └── workflows/
│       ├── test.yml                # CI: pytest, ruff, mypy
│       └── deploy.yml              # CD: автодеплой на VPS
│
├── docs/                           # Вся документация
│   ├── ARCHITECTURE_REVIEW.md      # Полный обзор архитектуры с критикой
│   ├── DAY_BY_DAY_PLAN.md          # Пошаговый план реализации
│   ├── PROJECT_STRUCTURE.md        # Этот файл
│   ├── SOURCES_CATALOG.md          # Каталог источников данных
│   ├── TRANSCRIPTION_PIPELINE.md   # Детали пайплайна транскрипции
│   ├── RAG_PIPELINE.md             # Детали RAG (создаётся к дню 14)
│   ├── VOICE_PIPELINE.md           # Детали voice (Phase 3)
│   ├── EVALUATION.md               # Методология оценки
│   ├── DEPLOYMENT.md               # Деплой
│   ├── PRIVACY.md                  # Приватность
│   ├── DEVELOPMENT.md              # Setup для разработчиков
│   ├── CONTRIBUTING.md             # Гайдлайн для контрибьюторов
│   ├── SECURITY.md                 # Reporting vulnerabilities
│   ├── PROMPTS.md                  # Документация по prompts
│   ├── COST_MODEL.md               # Модель стоимости
│   ├── COOKBOOK.md                 # Примеры использования
│   ├── PALI_HANDLING.md            # Работа с палийской терминологией
│   ├── EVAL_RESULTS.md             # История метрик
│   └── PHASE2_RESULTS.md           # Отчёт по Phase 2
│
├── consent-ledger/                 # YAML-реестр разрешений на источники
│   ├── README.md                   # Как работает Consent Ledger
│   ├── public-domain/              # Public Domain источники
│   │   ├── suttacentral-cc0.yaml
│   │   ├── pa-auk-knowing-and-seeing.yaml
│   │   └── visuddhimagga-pe-maung-tin.yaml
│   ├── open-license/               # CC, free distribution
│   │   ├── dhammatalks-org.yaml
│   │   ├── access-to-insight.yaml
│   │   ├── pts-cc-works.yaml
│   │   ├── ancient-buddhist-texts.yaml
│   │   ├── academic-papers.yaml
│   │   └── mahasi-free-works.yaml
│   └── explicit-permission/        # Phase 2 — требуют письменного разрешения
│       └── (заполняется по мере получения)
│
├── src/                            # Исходный код
│   ├── __init__.py
│   ├── config.py                   # Settings via pydantic-settings
│   ├── logging.py                  # structlog setup
│   ├── cli.py                      # CLI entry point (`dharma-rag`)
│   │
│   ├── ingest/                     # Загрузка данных из источников
│   │   ├── __init__.py
│   │   ├── base.py                 # Абстрактный базовый класс
│   │   ├── suttacentral.py
│   │   ├── dhammatalks.py
│   │   ├── access_to_insight.py
│   │   ├── mahasi.py
│   │   ├── academic.py
│   │   ├── visuddhimagga.py
│   │   └── dharmaseed.py           # Phase 1.5
│   │
│   ├── processing/                 # Обработка текста
│   │   ├── __init__.py
│   │   ├── cleaner.py              # Unicode NFC, HTML strip, Pāli diacritics
│   │   ├── chunker.py              # Parent-child semantic chunking
│   │   ├── contextual.py           # Anthropic Contextual Retrieval
│   │   └── normalizer.py           # Pāli romanization normalization
│   │
│   ├── transcription/              # Пайплайн транскрипции (Phase 1.5)
│   │   ├── __init__.py
│   │   ├── groq_batch.py           # Groq Batch API клиент
│   │   ├── vad.py                  # Silero VAD pre-processing
│   │   ├── correction.py           # LLM Pāli correction
│   │   ├── diarization.py          # pyannote для Q&A talks
│   │   └── alignment.py            # WhisperX forced alignment
│   │
│   ├── embeddings/                 # Embedding модели
│   │   ├── __init__.py
│   │   ├── base.py                 # Абстрактный класс
│   │   ├── bge_m3.py               # BGE-M3 (dense + sparse + ColBERT)
│   │   ├── mitra.py                # MITRA-E для палийского
│   │   └── store.py                # Qdrant operations
│   │
│   ├── rag/                        # RAG пайплайн
│   │   ├── __init__.py
│   │   ├── pipeline.py             # Главный оркестратор
│   │   ├── retriever.py            # Hybrid retrieval (dense + sparse + BM25)
│   │   ├── bm25.py                 # BM25 с палийским токенайзером
│   │   ├── reranker.py             # Cross-encoder reranking
│   │   ├── query_expansion.py      # Pāli expansion + HyDE
│   │   ├── generator.py            # Claude generation + streaming
│   │   ├── router.py               # LLM routing (Haiku/Sonnet/Opus)
│   │   ├── citations.py            # Citation extraction & verification
│   │   ├── context_builder.py      # Format chunks for LLM
│   │   └── prompts.py              # System prompts + few-shot
│   │
│   ├── cache/                      # Семантический кеш
│   │   ├── __init__.py
│   │   └── semantic_cache.py
│   │
│   ├── language/                   # Мультиязычность
│   │   ├── __init__.py
│   │   ├── detector.py             # Language detection
│   │   └── glossary.py             # Pāli term glossary loader
│   │
│   ├── eval/                       # Evaluation framework
│   │   ├── __init__.py
│   │   ├── runner.py               # Прогон test queries
│   │   ├── metrics.py              # ref_hit, topic_hit, faithfulness
│   │   └── ragas_integration.py    # Ragas metrics
│   │
│   ├── api/                        # FastAPI приложение (Phase 4)
│   │   ├── __init__.py
│   │   ├── app.py                  # FastAPI instance + middleware
│   │   ├── routes.py               # API endpoints
│   │   ├── schemas.py              # Pydantic models
│   │   └── dependencies.py         # Dependency injection
│   │
│   ├── bot/                        # Telegram bot (Phase 5)
│   │   ├── __init__.py
│   │   ├── main.py                 # Entry point
│   │   ├── handlers/
│   │   │   ├── start.py
│   │   │   ├── query.py
│   │   │   ├── meditate.py
│   │   │   └── lesson.py
│   │   └── states.py               # FSM states
│   │
│   └── voice/                      # Voice pipeline (Phase 8-9)
│       ├── __init__.py
│       ├── pipeline.py             # Pipecat → LiveKit pipeline
│       ├── stt.py                  # STT abstraction
│       ├── tts.py                  # TTS abstraction
│       ├── meditation.py           # Meditation-specific features
│       └── pronunciation.py        # Pāli pronunciation dictionary
│
├── frontend/                       # Web UI
│   ├── templates/                  # Phase 4: Jinja2 + HTMX
│   │   ├── base.html
│   │   ├── index.html
│   │   └── components/
│   │       ├── chat_message.html
│   │       └── source_citation.html
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   └── svelte/                     # Phase 7: SvelteKit
│       ├── package.json
│       ├── svelte.config.js
│       ├── src/
│       │   ├── routes/
│       │   ├── lib/
│       │   └── app.html
│       └── capacitor.config.ts
│
├── scripts/                        # Утилитарные скрипты
│   ├── audit_sources.py
│   ├── build_index.py
│   ├── build_index_hybrid.py
│   ├── add_context.py              # Contextual Retrieval batch
│   ├── prepare_audio.py
│   ├── post_process_transcripts.py
│   ├── test_setup.py
│   └── migrate_to_qdrant.py
│
├── tests/                          # Тесты
│   ├── unit/
│   │   ├── test_chunker.py
│   │   ├── test_retriever.py
│   │   ├── test_reranker.py
│   │   └── test_cache.py
│   ├── integration/
│   │   └── test_pipeline_e2e.py
│   └── eval/                       # Eval test set
│       ├── test_queries.yaml
│       ├── golden_answers.yaml
│       ├── eval_corpus.jsonl       # gitignored (большой)
│       └── results/                # JSON-ы с историей метрик (gitignored)
│
└── data/                           # Данные (gitignored, кроме README)
    ├── README.md                   # Инструкции по загрузке
    ├── raw/                        # Сырые данные из источников
    │   ├── suttacentral/
    │   ├── dhammatalks/
    │   ├── access_to_insight/
    │   └── ... (по источникам)
    ├── processed/                  # JSONL чанки
    │   ├── suttacentral/
    │   ├── dhammatalks/
    │   └── ...
    ├── audio/                      # MP3 файлы Dharmaseed (Phase 1.5)
    ├── transcripts/                # Транскрипты после Whisper
    └── glossary/
        └── pali.yaml               # Палийский глоссарий (200+ терминов)
```

---

## Пояснения

### Почему такая структура?

**`src/` flat layout с `__init__.py`** — стандартный Python пакет, импортируется как `from src.rag.pipeline import RAGPipeline`. Альтернатива (`src/dharma_rag/`) тоже валидна, но усложняет имена.

**`docs/` всё в markdown** — рендерится прямо на GitHub, не нужна отдельная сборка. В Phase 4+ можно перейти на Astro Starlight для документационного сайта.

**`consent-ledger/` отдельно** — это юридический артефакт, должен быть рядом с кодом и под версионным контролем. YAML формат прост для community-вкладов.

**`frontend/` отдельно от `src/`** — потому что в Phase 7 это будет отдельный SvelteKit проект со своим `package.json`. До этого — простые Jinja2 templates.

**`data/` gitignored** — данные большие (1.1 GB+) и имеют свои лицензии. Инструкции загрузки в `data/README.md`.

---

## Что НЕ коммитим

- `data/` (кроме README) — большие файлы, чужие лицензии
- `.env` — секреты
- `qdrant_storage/`, `langfuse_data/` — runtime данные
- `models/` — скачанные модели (BGE-M3 и др.)
- `*.log`, `logs/`
- `tests/eval/results/*.json` — только структуру, не контент
- `__pycache__/`, `.venv/`, `node_modules/`

---

## Соглашения

- **Имена файлов:** `snake_case.py`
- **Имена классов:** `PascalCase`
- **Константы:** `UPPER_SNAKE_CASE`
- **Все Python-модули содержат `__init__.py`**, даже пустой
- **Импорты:** absolute (`from src.rag.pipeline`), не relative
- **Type hints обязательны** для публичных функций
- **Docstrings обязательны** для публичных классов и функций (Google style)

---

## Эволюция структуры

Структура будет расти постепенно по мере прогресса по [DAY_BY_DAY_PLAN](DAY_BY_DAY_PLAN.md):

- **День 3:** базовый `src/` создан
- **День 7:** `src/embeddings/`, `src/rag/retriever.py`
- **День 14:** полный retrieval pipeline
- **День 28:** Phase 2 quality
- **День 36:** `src/cli.py` + полный pipeline
- **День 44:** `src/api/`, `frontend/templates/`
- **День 58:** `src/bot/`
- **День 64:** `src/transcription/`
- **Месяц 4:** `frontend/svelte/`
- **Месяц 6:** `src/voice/`
