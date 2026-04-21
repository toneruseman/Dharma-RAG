# Dharma RAG

> Открытая, бесплатная, мультиязычная RAG-платформа для буддийских созерцательных учений (Тхеравада, практика джханы, прагматическая дхарма). Пользователи задают вопросы о медитации/буддизме/дхарме голосом или текстом — система находит релевантные отрывки в курируемом корпусе реальных учений и генерирует обоснованные ответы со ссылками на источники, на языке пользователя.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Pre-Alpha](https://img.shields.io/badge/Status-Pre--Alpha-orange)]()
[![Phase: 1 (MVP)](https://img.shields.io/badge/Phase-1%20MVP-blue)]()

---

## Миссия

Сделать мудрость созерцательных традиций доступной каждому практикующему на любом языке, с верностью оригинальным учениям.

## Принципы

1. **Grounded RAG, не chatbot** — каждый ответ цитирует источники
2. **100% бесплатно, open-source (MIT)** — без рекламы, регистрации, подписок
3. **Dual-track development** — публичный код использует только разрешённый контент
4. **Consent Ledger** — публичный YAML-реестр разрешений на каждый источник
5. **Tool, not teacher** — помогает находить учения, не заменяет учителей
6. **Privacy by default** — нулевой сбор пользовательских данных на сервере

---

## Что сделано (Phase 1 — день 6 из 21)

- ✅ Docker Compose стек для локальной разработки: Postgres 16 (`dharma-db`) + Qdrant + Langfuse
- ✅ Postgres FRBR schema (Work → Expression → Instance → Chunk) + Alembic миграции
- ✅ Ingest pipeline SuttaCentral: **3 413 сутт / 124 532 чанка** из переводов Бхиккху Суджато (MN/DN/SN/AN), идемпотентный (повторный запуск — no-op)
- ✅ Text cleaner: Unicode NFC, Pali IAST нормализация (`ṁ → ṃ`), ASCII-fold колонка (`satipaṭṭhāna → satipatthana`) для BM25 поиска
- ✅ FastAPI `/health` endpoint
- 🔄 Parent/child chunker (день 7)

## Что планируется в Phase 1 (дни 7-21)

- ⏳ Parent/child структурное chunking (384 / 1024-2048 токенов) — день 7
- ⏳ BGE-M3 embeddings (dense 1024d + sparse) и Qdrant indexing с named vectors — дни 8-10
- ⏳ BM25 через Postgres FTS с Pali-aware токенизацией — день 11
- ⏳ Hybrid retrieval через RRF (Reciprocal Rank Fusion) — день 12
- ⏳ Reranking (BGE-reranker-v2-m3 на GPU) — день 13
- ⏳ Baseline eval через Ragas (faithfulness, ref_hit@5) — день 14
- ⏳ Contextual Retrieval (префикс Claude Haiku) — дни 15-17
- ⏳ `POST /api/query` endpoint — день 19
- ⏳ **v0.1.0 релиз** — день 21
- ⏳ Дополнительные источники (DhammaTalks.org, Access to Insight, ...) — Phase 2+
- ⏳ Web UI (HTMX + SSE streaming), Telegram bot (aiogram 3.x) — APP-трек, отдельный план

## Видение Phase 2 / Phase 3 (месяцы 3-12)

**Phase 2 (Месяцы 3-6):**
- Мобильные приложения Android/iOS (Capacitor + SvelteKit)
- Композитор ретритов
- Генератор уроков
- Концепт-графы (Cytoscape.js)
- Voice MVP (Pipecat + Deepgram + ElevenLabs)
- Транскрипция всего корпуса Dharmaseed (~46 000 лекций)

**Phase 3 (Месяцы 6-12):**
- Live voice chat (LiveKit Agents, <800ms задержка)
- On-device STT/TTS (Sherpa-ONNX) для приватности
- Audio companion для медитации
- LightRAG knowledge graph
- Curriculum planner с интервальными повторениями

---

## Быстрый старт

### Требования

- Python **3.12+** (проверено на 3.12.10)
- Docker + Docker Compose (для локального стека Postgres / Qdrant / Langfuse)
- ~10 GB свободного места (клон `bilara-data` + будущий векторный индекс)
- Опционально: NVIDIA GPU с ≥12 GB VRAM для reranker (добавится на дне 13)

### Установка

```bash
# Клонировать
git clone https://github.com/toneruseman/Dharma-RAG.git
cd Dharma-RAG

# Установить зависимости (Python 3.12+)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Скопировать конфиг
cp .env.example .env
# Отредактировать .env, добавить ANTHROPIC_API_KEY (опционально на дне 6)

# Поднять локальный стек: Postgres 16 + Qdrant + Langfuse
docker compose up -d

# Применить миграции БД
alembic upgrade head

# Проверить health check (единственный работающий endpoint на дне 6)
python -m uvicorn src.api.app:app --reload &
curl http://localhost:8000/health
```

### Опционально: загрузить корпус SuttaCentral

```bash
# Клонировать bilara-data (~500 MB)
git clone --depth 1 --branch published \
  https://github.com/suttacentral/bilara-data.git data/raw/suttacentral

# Ingest в Postgres (~90 секунд, 3 413 сутт, 124 532 чанка)
python scripts/ingest_sc.py --nikayas mn,dn,sn,an
```

`POST /api/query` endpoint появится на дне 19.

---

## Документация

**Активные планы и решения:**
- [docs/STATUS.md](docs/STATUS.md) — единый трекер прогресса (RAG + APP), обновляется на каждом merge
- [docs/decisions/0001-phase1-architecture.md](docs/decisions/0001-phase1-architecture.md) — **ADR-0001**, авторитетный источник архитектурных решений Phase 1
- [docs/RAG_DEVELOPMENT_PLAN.md](docs/RAG_DEVELOPMENT_PLAN.md) — 120-дневный план RAG-ядра
- [docs/APP_DEVELOPMENT_PLAN.md](docs/APP_DEVELOPMENT_PLAN.md) — 60-дневный план приложения (backend + frontend + mobile)
- [CHANGELOG.md](CHANGELOG.md) — по-дневный список изменений
- [ROADMAP.md](ROADMAP.md) — долгосрочное видение фаз

**Research и справочные материалы:**
- [docs/Dharma-RAG-Research-EN.md](docs/Dharma-RAG-Research-EN.md) — полное описание проекта на английском (3432 строки)
- [docs/Dharma-RAG.md](docs/Dharma-RAG.md) — рабочий документ с описанием архитектуры и источников

## Структура репозитория

```
Dharma-RAG/
├── README.md                   ← вы здесь
├── LICENSE                     ← MIT
├── CHANGELOG.md
├── ROADMAP.md
├── docker-compose.yml          ← Postgres + Qdrant + Langfuse
├── pyproject.toml              ← Python 3.12+, зависимости
├── alembic.ini + alembic/      ← DB миграции (asyncpg + psycopg)
├── docs/                       ← см. секцию "Документация" выше
├── consent-ledger/             ← YAML-реестр лицензий по источникам
│   ├── public-domain/          ← CC0, public domain
│   ├── open-license/           ← CC-BY, CC-BY-NC и т.п.
│   └── explicit-permission/    ← контент с личного разрешения автора
├── src/
│   ├── api/                    ← FastAPI app (/health сейчас)
│   ├── config.py               ← Pydantic Settings
│   ├── db/                     ← SQLAlchemy 2.x FRBR models + сессии
│   ├── ingest/suttacentral/    ← парсер bilara + loader в Postgres
│   ├── processing/             ← cleaner (NFC, IAST, ASCII fold)
│   ├── logging_config.py       ← structlog
│   └── cli.py                  ← command-line утилиты
├── scripts/
│   ├── ingest_sc.py            ← CLI для ingest SuttaCentral
│   ├── sc_dryrun.py            ← проверка парсера (10 записей)
│   └── reclean_chunks.py       ← backfill cleaner на существующие строки
├── tests/
│   ├── unit/                   ← быстрые тесты без DB (47 шт)
│   ├── integration/            ← тесты с реальным Postgres (13 шт)
│   └── eval/                   ← golden set (добавляется с буддологом)
└── data/                       ← gitignored: raw/, processed/, qdrant_storage/
```

---

## Лицензия

**Код:** MIT (см. [LICENSE](LICENSE))
**Документация:** CC-BY-SA 4.0
**Данные:** см. [consent-ledger/](consent-ledger/) — каждый источник имеет свою лицензию

---

## Контакты

- GitHub: [@toneruseman](https://github.com/toneruseman)
- Issues: [github.com/toneruseman/Dharma-RAG/issues](https://github.com/toneruseman/Dharma-RAG/issues)

> "Sabbe sattā sukhitā hontu" — Пусть все существа будут счастливы.

## Статус разработки

🚀 **Начало разработки:** 14 апреля 2026
📍 **Текущая фаза:** Phase 1 Foundation — неделя 1 (день **6** из 21)
🎯 **Следующий milestone:** `v0.1.0` — Foundation (день 21, ~конец мая 2026)

Подробный трекер по дням — в [docs/STATUS.md](docs/STATUS.md).
