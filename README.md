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

## Что работает (Phase 1, в разработке)

- ✅ 56 684 чанка из 7 открыто-лицензированных источников (SuttaCentral, DhammaTalks.org, Access to Insight и др.)
- 🔄 Hybrid retrieval (BGE-M3 dense + sparse + BM25)
- 🔄 Reranking (BGE-reranker-v2-m3)
- 🔄 Generation через Claude API (Haiku/Sonnet routing)
- ⏳ Web UI (HTMX + SSE streaming)
- ⏳ Telegram bot (aiogram 3.x)

## Что планируется

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

```bash
# Клонировать
git clone https://github.com/toneruseman/dharma-rag.git
cd dharma-rag

# Установить зависимости
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Скопировать конфиг
cp .env.example .env
# Отредактировать .env, добавить ANTHROPIC_API_KEY

# Поднять Qdrant + Langfuse
docker compose up -d

# Запустить сервер
python -m uvicorn src.api.app:app --reload

# Тестовый запрос
curl http://localhost:8000/api/query -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "What is jhāna?"}'
```

Подробнее — в [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

---

## Структура репозитория

```
dharma-rag/
├── README.md                   ← вы здесь
├── LICENSE                     ← MIT
├── ROADMAP.md                  ← фазы и видение
├── docs/
│   ├── ARCHITECTURE_REVIEW.md  ← полный обзор архитектуры
│   ├── DAY_BY_DAY_PLAN.md      ← пошаговый план реализации
│   ├── SOURCES_CATALOG.md      ← каталог источников данных
│   ├── TRANSCRIPTION_PIPELINE.md
│   ├── RAG_PIPELINE.md
│   ├── VOICE_PIPELINE.md
│   ├── EVALUATION.md
│   ├── DEPLOYMENT.md
│   ├── PRIVACY.md
│   ├── DEVELOPMENT.md
│   ├── CONTRIBUTING.md
│   └── PROJECT_STRUCTURE.md
├── consent-ledger/
│   ├── README.md
│   ├── public-domain/
│   ├── open-license/
│   └── explicit-permission/
├── src/                        ← исходный код (создаётся в процессе)
├── tests/                      ← тесты + eval корпус
├── scripts/                    ← скрипты ингеста, миграций
├── data/                       ← данные (gitignored)
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## Лицензия

**Код:** MIT (см. [LICENSE](LICENSE))
**Документация:** CC-BY-SA 4.0
**Данные:** см. [consent-ledger/](consent-ledger/) — каждый источник имеет свою лицензию

---

## Контакты

- GitHub: [@toneruseman](https://github.com/toneruseman)
- Issues: [github.com/toneruseman/dharma-rag/issues](https://github.com/toneruseman/dharma-rag/issues)

> "Sabbe sattā sukhitā hontu" — Пусть все существа будут счастливы.
