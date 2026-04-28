# Feature Roadmap

> Куда движется Dharma-RAG за пределами Phase 1 retrieval+answer.
> Источник идей: реальные практики западных учителей, InsightTimer,
> Plum Village, Waking Up, наш собственный value-prop vs Claude Opus
> по подписке (см. `docs/concepts/00-value-vs-opus.md`).
>
> **Статус:** living doc. Приоритеты пересматриваются после каждой
> end-to-end вертикали. Не commitment — это то, во что мы _можем_
> вложиться, когда core-pipeline стабилен.

## Принцип приоритизации

Каждая фича оценивается по двум осям:

- **Value** — пользу даёт только эта система (Opus не повторит)
- **Feasibility** — сколько недель работы, какие зависимости

Phase 1 → 2 → 3 → 4 — не временная последовательность, а уровень
зависимостей: фичи Phase 4 требуют voice-cloning pipeline'а, Phase 2
требует только текстовый corpus + UI.

---

## Tier 1 — Высокая полезность, низкие зависимости (next 1-3 мес)

### 1. «Спроси у учителя» (text Q&A в стиле учителя)

Frontend: dropdown `Учитель: Аджан Чаа / Тханиссаро / Бхикху Бодхи /
Goenka / Joseph Goldstein`. Backend: добавляем фильтр
`teacher_id` к retrieval'у + style-prompt в `AnswerService`,
которая инструктирует LLM писать «as if Ajahn Chah were answering».

**Что новое:** ответ опирается на корпус **этого** учителя, цитаты —
из его talks. Opus не различит стилей по запросу — нет corpus'а.

**Зависимости:** ingest Dharmaseed transcripts (~9000 talks) с
metadata `teacher`, `lineage`, `tradition`. Пока этого нет — уже
сейчас можно прототипировать на 4-5 учителях из текстов в `data/`.

**Effort:** 2 недели после готового Dharmaseed pipeline'а.

### 2. Контекстный поиск по конкретной talk'е

User слушает retreat-аудио — pause, спрашивает «а что Goenka сказал
про anicca в этой sessions, и что это значит?». Backend ищет
**только в этой talk'е** + расширяет термины через глоссарий +
объясняет на основе всего corpus'а.

**Что новое:** «pause-and-ask» UX, которого нет ни у одного
meditation-app. Связывает аудио-плеер с RAG.

**Зависимости:** transcripts с timestamp'ами + audio-player в web/.

**Effort:** 1 неделя backend (фильтр `talk_id`) + 2 недели UI.

### 3. Daily reading + commentary

Каждый день — короткий sutta-фрагмент (~200 слов) + LLM-комментарий
с практическим смыслом + кнопка «спросить дальше». Cron Job +
deterministic seed → один и тот же текст каждому пользователю
в один день.

**Что новое:** Calm/Headspace-style ритуал, но с реальными
буддийскими источниками вместо обобщённой «mindfulness».

**Effort:** 1 неделя — простая cron-задача + frontend page.

---

## Tier 2 — Дифференциация, средние зависимости (3-6 мес)

### 4. AI-guided retreat в стиле учителя

User выбирает «3-day retreat with Ajahn Chah» — система генерирует
расписание sessions, утренние beats, evening Q&A, всё в **тоне
выбранного учителя**. Phase 4: с voice-cloning тот же script
озвучивается голосом учителя (с явным consent / public-domain
clearance).

**Что новое:** персональный retreat без стоимости поездки в Forest
Monastery. Live audio retreat companion — в InsightTimer этого нет.

**Зависимости:** Tier 1 #1 + voice cloning (XTTS-v2 / OpenVoice) +
copyright clearance per teacher.

**Effort:** 3 недели после Tier 1 готов. Voice — отдельные 2-4 нед.

### 5. Adaptive timer

Timer with bells — но bells подбираются под тип практики (anapana
vs metta vs noting), длительность подбирается по история сессий
(«вы делали 20 мин три дня — попробуем 25»), end-bell + короткий
reflection prompt от LLM.

**Что новое:** обычные timers — статичные. Этот — учится из истории.

**Effort:** 2 недели — IndexedDB session history + LLM reflection.

### 6. Rewrite talk in style

«Возьми эту talk Ajahn Chah'а и перепиши в стиле Joseph Goldstein,
оставив все цитаты sutta'ы». Полезно для cross-tradition study.

**Effort:** 1 неделя — это просто style-prompt + retrieval source-mode.

---

## Tier 3 — Sangha и translation (6-12 мес)

### 7. Sangha discussion bot

Многопользовательский Q&A — group of practitioners задаёт вопросы,
бот отвечает с цитатами. Можно «pin» полезные обмены, делать
weekly digest. Discord-style threading.

**Зависимости:** auth, multi-tenancy.

**Effort:** 1 месяц.

### 8. Annotated parallel translations

Sutta MN10 рядом: Pāli (BGE-original) — Pāli (transliterated
cyrillic) — RU (Парибок) — EN (Bhikkhu Bodhi) — RU (Сыркин).
Hover на термин — DPD glossary popup. Кликаем «спросить» — RAG
с context'ом этого фрагмента.

**Зависимости:** parallel-aligned corpus (есть для Tipiṭaka-canon —
Pāli + EN; RU переводы — частичные, нужен ingest).

**Effort:** 2 недели backend (alignment) + 2 недели UI.

---

## Tier 4 — Practice tools (12+ мес)

### 9. Practice journal с auto-tagging

User пишет journal entry о practice — LLM авто-теги (`#anicca`,
`#hindrances:sloth`, `#progress:access-concentration`), trends по
неделям, обнаружение паттернов (`«вы 5 дней пишете о torpor — может,
поменяйте время практики?»`).

**Effort:** 2 недели после auth готов.

### 10. Sutta study tracker

Reading plan по Tipiṭaka — Majjhima Nikāya за 2 года, Saṃyutta за
3 — progress, mark «read+understood / read+confused / re-read»,
RAG offer по непонятным фрагментам.

**Effort:** 1 неделя UI + sutta-index (один раз).

---

## Tier 5 — Long shots (Phase 5+)

### 11. Multimodal art recognition

«Вот фото статуи / тханки — что это?» → image-classification +
RAG с контекстом по символике. iconography как дверь к учению.

### 12. Pāli pronunciation coach

Browser MediaRecorder → Whisper STT → diff против reference. Coach
для chanting practice.

### 13. Retreat companion offline

PWA + on-device retrieval (~10MB embeddings + WebGPU LLM) — full
RAG without internet, для retreat'ов в Asia.

---

## Top-5 next features (2026-Q2 → Q3)

После app-day-N (Reading Room MVP) и Dharmaseed corpus ingestion:

1. **Tier 1 #1** «Спроси у учителя» — biggest moat vs Opus
2. **Tier 1 #3** Daily reading — простой ритуал, retention driver
3. **Tier 2 #5** Adaptive timer — engagement loop
4. **Tier 1 #2** Контекстный поиск по talk'е — уникальный UX
5. **Tier 2 #4** AI-guided retreat — flagship feature, voice-clone optional

## Как меняется этот список

- После каждой фичи — review tier'ов: что сместилось?
- Если user-feedback покажет что нужна другая фича — переключаемся
- Voice-cloning может уехать в Phase 4+ если copyright issues

## Что НЕ делаем

- **Generic mindfulness app** (Calm/Headspace clone) — рынок забит
- **Социальная сеть для буддистов** — outside scope
- **Donation/dana platform** — отдельный проект
- **Translation services без learning** — DeepL уже есть
