# Dharma-RAG

[🇬🇧 English](README.md) · 🇷🇺 **Русский**

> **Dharma-RAG** — открытый инструмент для изучения буддийской практики и канона.
>
> Задайте вопрос о технике медитации, отрывке из сутты или палийском термине — система найдёт точные места в курируемом корпусе (палийский канон + учения современных мастеров), приведёт цитаты и ответит на вашем языке. В фокусе: **Тхеравада**, **традиции jhāna**, **прагматическая дхарма**.
>
> Лицензия MIT. Без регистрации, подписок и рекламы.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Pre-Alpha](https://img.shields.io/badge/Status-Pre--Alpha-orange)]()
[![Phase: 1 Foundation](https://img.shields.io/badge/Phase-1%20Foundation-blue)]()
[![Release: v0.0.2](https://img.shields.io/badge/Release-v0.0.2-green)](https://github.com/toneruseman/Dharma-RAG/releases/tag/v0.0.2)

---

## Миссия

Сделать мудрость созерцательных традиций доступной каждому практикующему, на любом языке, с верностью оригинальным учениям.

## Принципы

1. **Grounded RAG, не chatbot** — каждый ответ цитирует источники.
2. **Открытый код (MIT), бесплатно** — без рекламы, регистрации, подписок.
3. **Dual-track development** — в публичный репозиторий попадает только разрешённый контент.
4. **Consent Ledger** — у каждого источника в корпусе есть YAML-запись с объяснением как получено разрешение.
5. **Tool, not teacher** — Dharma-RAG помогает находить учения; он не заменяет живого учителя или квалифицированного специалиста.
6. **Privacy by default** — пользовательские данные на серверах не собираются.

---

## Состояние (Phase 1 — день 7 из 21)

### Сделано

- ✅ Локальный dev-стек через Docker Compose: Postgres 16 (`dharma-db`) + Qdrant + Langfuse.
- ✅ Postgres FRBR-схема (Work → Expression → Instance → Chunk) + миграции Alembic.
- ✅ Ingest-пайплайн SuttaCentral: **3 413 сутт / 10 227 чанков** (3 749 parent + 6 478 child) из английских переводов Бхиккху Суджато MN/DN/SN/AN. Идемпотентный повторный запуск через `content_hash`.
- ✅ Text cleaner: Unicode NFC, канонизация палийской диакритики IAST (`ṁ → ṃ`), теневая ASCII-fold колонка (`satipaṭṭhāna → satipatthana`) для BM25.
- ✅ Parent/child структурный chunker (родитель ~1536 токенов, ребёнок ~384 токена) — паттерн Parent Document Retrieval.
- ✅ FastAPI `/health`, структурное логирование через structlog.
- ✅ 79 тестов (65 unit + 14 integration), pre-commit на ruff / mypy / detect-secrets.

### В работе (дни 8-21)

- ⏳ BGE-M3 embeddings (dense 1024d + sparse) и Qdrant с named vectors (дни 8-10).
- ⏳ BM25 через Postgres FTS с Pali-aware токенизацией (день 11).
- ⏳ Гибридный retrieval через Reciprocal Rank Fusion (день 12).
- ⏳ Reranking через BGE-reranker-v2-m3 на GPU (день 13).
- ⏳ Baseline-оценка через Ragas — faithfulness, ref_hit@5, citation_validity (день 14).
- ⏳ Contextual Retrieval (контекстные префиксы от Claude Haiku) — дни 15-17.
- ⏳ Endpoint `POST /api/query` (день 19).
- ⏳ **Релиз v0.1.0** (день 21).

### Долгосрочный горизонт

- **Phase 2** (месяцы 3-6) — расширение корпуса (DhammaTalks.org, Access to Insight, PTS, академические статьи), fine-tuning BGE-M3, палийский глоссарий, regression CI, golden set из 100 вопросов.
- **Phase 3** (месяцы 6-12) — мобильные приложения (Capacitor + SvelteKit), Voice MVP (Pipecat + Deepgram + ElevenLabs), аудиокорпус Dharmaseed (~46 000 лекций), live voice через LiveKit Agents, on-device STT/TTS (Sherpa-ONNX) для приватности.

---

## Быстрый старт

### Требования

- **Python 3.12+** (проверено на 3.12.10).
- Docker + Docker Compose (для локального стека Postgres / Qdrant / Langfuse).
- ~10 GB свободного места (клон `bilara-data` + будущий векторный индекс).
- Опционально: NVIDIA GPU с ≥12 GB VRAM для reranker-а (подключится на дне 13).

### Установка

```bash
git clone https://github.com/toneruseman/Dharma-RAG.git
cd Dharma-RAG

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env                # заполнить ANTHROPIC_API_KEY при необходимости

docker compose up -d                # Postgres + Qdrant + Langfuse
alembic upgrade head

# Smoke-тест — сегодня живой только /health.
python -m uvicorn src.api.app:app --reload &
curl http://localhost:8000/health
```

### Опционально: загрузить корпус SuttaCentral

```bash
git clone --depth 1 --branch published \
  https://github.com/suttacentral/bilara-data.git data/raw/suttacentral

python scripts/ingest_sc.py --nikayas mn,dn,sn,an
# → 3 413 сутт / 10 227 чанков в базе за ~90 секунд
```

`POST /api/query` появится на дне 19.

---

## Документация

**Актуальные планы и решения**

- [docs/STATUS.md](docs/STATUS.md) — единый по-дневный трекер прогресса (RAG + APP), обновляется на каждом merge.
- [docs/decisions/0001-phase1-architecture.md](docs/decisions/0001-phase1-architecture.md) — **ADR-0001**, авторитетный источник архитектурных решений Phase 1.
- [docs/RAG_DEVELOPMENT_PLAN.md](docs/RAG_DEVELOPMENT_PLAN.md) — 120-дневный план RAG-ядра.
- [docs/APP_DEVELOPMENT_PLAN.md](docs/APP_DEVELOPMENT_PLAN.md) — 60-дневный план приложения (backend + frontend + mobile).
- [CHANGELOG.md](CHANGELOG.md) — по-дневный список изменений.
- [ROADMAP.md](ROADMAP.md) — долгосрочное видение фаз.

**Research и справочные материалы**

- [docs/Dharma-RAG-Research-EN.md](docs/Dharma-RAG-Research-EN.md) — полное описание проекта на английском (3432 строки).
- [docs/Dharma-RAG.md](docs/Dharma-RAG.md) — рабочий документ с описанием архитектуры и источников.

---

## Структура репозитория

```
Dharma-RAG/
├── README.md / README.ru.md        ← вы здесь (EN / RU)
├── LICENSE                         ← MIT
├── CHANGELOG.md / ROADMAP.md
├── docker-compose.yml              ← Postgres + Qdrant + Langfuse
├── pyproject.toml                  ← Python 3.12+, зависимости
├── alembic.ini + alembic/          ← миграции БД (asyncpg + psycopg)
├── .claude/agents/                 ← общие Claude Code subagent-ы проекта
├── docs/                           ← см. секцию «Документация» выше
├── consent-ledger/                 ← YAML-реестр лицензий по источникам
│   ├── public-domain/              ← CC0, public domain
│   ├── open-license/               ← CC-BY, CC-BY-NC и т.п.
│   └── explicit-permission/        ← контент по личному разрешению автора
├── src/
│   ├── api/                        ← FastAPI app (пока только `/health`)
│   ├── config.py                   ← Pydantic Settings
│   ├── db/                         ← SQLAlchemy 2.x FRBR-модели + async сессии
│   ├── ingest/suttacentral/        ← парсер bilara + loader в Postgres
│   ├── processing/                 ← cleaner (NFC, IAST, ASCII fold), chunker
│   ├── logging_config.py           ← structlog
│   └── cli.py                      ← command-line утилиты
├── scripts/
│   ├── ingest_sc.py                ← CLI для ingest SuttaCentral
│   ├── sc_dryrun.py                ← проверка парсера (10 записей)
│   ├── reclean_chunks.py           ← backfill cleaner на существующие строки
│   └── rechunk.py                  ← backfill parent/child chunker
├── tests/
│   ├── unit/                       ← быстрые тесты без БД (65 шт)
│   ├── integration/                ← тесты с реальным Postgres (14 шт)
│   └── eval/                       ← golden set (добавится с буддологом — блокер #8)
└── data/                           ← gitignored: raw/, processed/, qdrant_storage/
```

---

## Лицензия

- **Код:** MIT (см. [LICENSE](LICENSE)).
- **Документация:** CC-BY-SA 4.0.
- **Данные:** см. [consent-ledger/](consent-ledger/) — у каждого источника своя лицензия.

---

## Контакты

- GitHub: [@toneruseman](https://github.com/toneruseman)
- Issues: [github.com/toneruseman/Dharma-RAG/issues](https://github.com/toneruseman/Dharma-RAG/issues)

---

🚀 Начало разработки: **14 апреля 2026**.
📍 Текущая фаза: **Phase 1 Foundation** — неделя 1 (день **7** из 21).
🎯 Следующий milestone: **v0.1.0 — Foundation** (день 21, ~конец мая 2026).

Подробный трекер по дням — в [docs/STATUS.md](docs/STATUS.md).

> *«Sabbe sattā sukhitā hontu»* — Пусть все существа будут счастливы.
