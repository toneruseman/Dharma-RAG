# Dharma RAG — Дорожная карта

> Высокоуровневое видение проекта на 12 месяцев. Детальные шаги — в [docs/DAY_BY_DAY_PLAN.md](docs/DAY_BY_DAY_PLAN.md).

---

## Видение

К концу года 1: **публичная RAG-платформа на 1000+ активных пользователей** с веб, мобильным и голосовым интерфейсами, работающая на корпусе из ~900 000 чанков из 47+ источников буддийских учений.

---

## Текущий статус

**Phase 0 (Setup) — в разработке** ⏱️

Уже сделано в предыдущей инкарнации проекта:
- ✅ 56,684 чанков из 7 источников обработаны
- ✅ Базовая структура src/ (требует переноса)
- ✅ Eval framework (50 запросов)
- ✅ Сравнение моделей embedding запущено

---

## Фазы

### 🏗️ Phase 1: MVP (Месяцы 1-2, дни 1-90)

**Цель:** Работающий публичный RAG для текстовых запросов.

**Milestones:**
- **v0.1.0** (день 14) — Foundation: Qdrant + базовый retrieval + eval
- **v0.2.0** (день 28) — Quality: hybrid search + reranking + contextual retrieval
- **v0.3.0** (день 42) — Generation: Claude integration + CLI
- **v0.4.0** (день 56) — Web MVP: FastAPI + HTMX + публичный URL
- **v0.5.0** (день 63) — Telegram bot
- **v0.6.0** (день 90) — Полный корпус Dharmaseed транскрибирован

**Бюджет:** ~$1500 (в основном транскрипция)

---

### 📱 Phase 2: Cross-Platform (Месяцы 3-5)

**Цель:** Доступность через мобильные устройства + улучшенные функции.

**Milestones:**
- **v0.7.0** (месяц 4) — SvelteKit фронтенд
- **v0.8.0** (месяц 5) — Capacitor Android (alpha)
- **v0.9.0** (месяц 5) — Lesson generator + retreat composer + concept graphs

**Бюджет:** ~$300 (Google Play + улучшения хостинга)

---

### 🎙️ Phase 3: Voice (Месяцы 5-9)

**Цель:** Live voice chat с буддийскими учениями.

**Milestones:**
- **v0.10.0** (месяц 6) — Voice MVP (Pipecat + Deepgram + ElevenLabs)
- **v0.11.0** (месяц 7) — LiveKit production
- **v0.12.0** (месяц 8) — Meditation features (guided sessions, ambient audio)
- **v0.13.0** (месяц 9) — On-device STT/TTS, Kokoro self-hosted

**Бюджет:** ~$800 (LiveKit, ElevenLabs, GPU для TTS)

---

### 🚀 Phase 4: Scale & Polish (Месяцы 9-12)

**Цель:** Production-ready, community, public launch.

**Milestones:**
- **v0.14.0** (месяц 10) — LightRAG knowledge graph
- **v0.15.0** (месяц 11) — Curriculum planner + spaced repetition
- **v1.0.0** (месяц 12) — Public launch + community

**Бюджет:** ~$1000 (knowledge graph, маркетинг, инфраструктура)

---

## Метрики успеха

### Качество

| Метрика | Phase 1 (день 90) | v1.0 (месяц 12) |
|---------|-------------------|------------------|
| ref_hit@5 | >70% | >85% |
| topic_hit@5 | >85% | >92% |
| Faithfulness | >0.85 | >0.92 |
| Cache hit rate | >40% | >60% |
| Voice latency p95 | n/a | <800ms |

### Использование

| Метрика | Phase 1 | Phase 2 | Phase 3 | v1.0 |
|---------|---------|---------|---------|------|
| Daily Active Users | 10 | 100 | 500 | 1000 |
| Queries / day | 50 | 500 | 5000 | 10000 |
| Voice minutes / day | - | - | 100 | 1000 |

### Сообщество

| Метрика | v1.0 |
|---------|------|
| GitHub stars | 500+ |
| Contributors | 50+ |
| Languages supported | 5+ |
| Public corpus chunks | 1M+ |

---

## Бюджет (12 месяцев)

| Категория | Сумма |
|-----------|-------|
| Хостинг (Hetzner) | $400 |
| Claude API | $1500 |
| Транскрипция (Groq Batch) | $1500 |
| Voice services | $500 |
| Domain + DNS + email | $100 |
| Google Play + Apple Dev | $125 |
| Прочее (GPU compute, инструменты) | $500 |
| **ИТОГО** | **~$4625** |

---

## Риски и митигации

См. [docs/ARCHITECTURE_REVIEW.md#анализ-рисков](docs/ARCHITECTURE_REVIEW.md#анализ-рисков).

Главные риски:
1. **Доктринальная неточность ответов** → строгая faithfulness метрика, обязательное цитирование
2. **Dharmaseed CC-BY-NC-ND** → запрос разрешения параллельно с разработкой
3. **Выгорание соло-разработчика** → рекрутинг контрибьюторов после v0.5.0
4. **Стоимость voice взлетает** → semantic cache, on-device STT/TTS

---

## Следующее действие

См. [docs/DAY_BY_DAY_PLAN.md](docs/DAY_BY_DAY_PLAN.md) → **День 1**.
