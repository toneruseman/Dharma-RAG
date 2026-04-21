# Dharma-RAG: архитектурное исследование слоя приложений и UX

## Дисклеймер: репозиторий недоступен

**Критичный факт**: репозиторий `https://github.com/toneruseman/Dharma-RAG` не удалось открыть ни прямым `web_fetch`, ни через `raw.githubusercontent.com`, ни через GitHub Search API, ни через Google/поисковые запросы с разными формулировками. Пользователь `toneruseman` также не индексируется. Варианты: приватный репо, удалён, опечатка в имени, либо создан очень недавно и не проиндексирован. Ни одной строчки README/docs/кода получить не удалось.

Поэтому пункт 1 задачи (анализ самого репо) в этом отчёте **не заполнен фактами из репо** — только рекомендация перепроверить URL, плюс ориентир на один из лучших публично доступных аналогов: **FoJin (`xr843/fojin`)** — открытая буддистская digital platform 9,200+ текстов с RAG на BGE-M3 + HNSW, 8 UI-языков, knowledge graph, CBETA-style reading, Apache-2.0. Де-факто это самый близкий публичный «бенчмарк» к тому, что, видимо, строит Dharma-RAG. Ниже я буду периодически использовать его как reference-implementation.

Всё остальное (пункты 2–7) — покрыто на основе исследования современного стека, UX-паттернов RAG и сравнительного анализа существующих проектов по древним/религиозным текстам.

---

## 1. Статус репозитория и что делать пользователю

**Проверить в первую очередь:**

- Точен ли URL (`toneruseman` / `Dharma-RAG`, регистр, дефис vs подчёркивание)?
- Публичный ли репо (если приватный — дать доступ или прислать выгрузку ключевых файлов: README, docs/, pyproject.toml, docker-compose.yml)?
- Не переименован ли автор/репо (новые URL GitHub делает редиректы, но только при существующем аккаунте)?

Пока доступа нет, ниже приводится **общая архитектурная карта** и рекомендации, которые справедливы для любого реалистичного дизайна Dharma-RAG.

---

## 2. Типовые риски, которые точно возникнут в слое приложений Dharma-RAG

Опишу их на основе типовых ошибок проектов такого класса (выявлены в анализе FoJin, BuddhaNexus, bible-rag, DharmaSutra и собственных наблюдений):

| Риск | Чем опасен | Типичный симптом |
|---|---|---|
| **Chat-first UX** | Пользователь уходит от текста в чат; текст превращается в «базу для LLM», а не в первичную сущность | Низкое доверие, галлюцинации; перестают читать сутры |
| **Отсутствие stable segment IDs** | Нельзя ссылаться на точное место; параллели/версии ломаются | Версионный ад, ответы без anchor |
| **Inline-citations как «чипы внизу»** | Пользователь не видит, что подкреплено источником, а что — нет | Легко пропустить галлюцинацию |
| **Монолитная БД текстов** | Нельзя отделить канон от комментариев, переводы от оригиналов | Путаница в ретривале, юзер не может фильтровать |
| **Один embedding для всех языков, без multilingual-aware retrieval** | Тибетский/санскрит проваливаются, EN-перекос | Запрос по-русски не находит тибетские параллели |
| **Велосипедный reader** | Не поддерживает Devanagari/Tibetan shaping, тяжёлые сутры лагают | Safari iOS особенно страдает |
| **Нет versioning переводов** | Учёный не может процитировать «ту самую версию 2024-03-11» | Академическая бесполезность |
| **Нет явного "источник недоступен/не использован"** | Непрозрачный ретривал, псевдо-научный флёр | Критика со стороны academia |
| **Tight coupling LLM в ядро UX** | Смена провайдера = переписать половину фронта | Lock-in, дорогие эксперименты |
| **Auth выбран слишком рано** | Перегруз single-user проекта | Ненужная сложность |

---

## 3. Типы пользовательских приложений поверх Dharma-RAG

Для RAG по дхармическим текстам реалистичны **пять различных product surfaces**, которые имеет смысл разделить архитектурно, а не сжимать в один «чат»:

| Поверхность | Для кого | Ядро UX | Critical UX details |
|---|---|---|---|
| **Reading Room** | практик/читатель | параллельный показ оригинал↔перевод, hover-glossary, сноски, закладки, прогресс | stable segment-ID в URL; sync-scroll; IAST/Wylie/Devanagari toggle |
| **Research Workbench** | философ/переводчик | граф параллелей (BuddhaNexus-like), table-view совпадений, alignment viewer, экспорт BibTeX/RIS | facet search, версионирование, TMX, diff между редакциями |
| **Dharma Q&A (chat)** | непрофессионал | chat с inline-цитатами Perplexity-style, pull-quotes, "explain in simpler terms" | обязательно клик→jump-to-source; "sources not used" прозрачно |
| **Study Companion** | изучающий | SRS-флэшкарты (термины, мантры), планы изучения, прогресс, аннотации | офлайн (ретриты), PWA, синхронизация через Yjs/Automerge |
| **API / MCP server** | разработчики/интеграции | REST + MCP endpoint для других AI-tools | OpenAPI, rate-limit, citation-embedded responses |

**Анти-рекомендация**: НЕ пытаться сразу все пять. Лучше 1–2 poverхности сделать превосходно, чем пять — посредственно. В FoJin реализованы 1+3 + частично 2, и это уже беспрецедентный объём работы.

---

## 4. Сравнительная матрица RAG-платформ для app-слоя

Полная матрица, 12 кандидатов (на основе исследования 2025–2026):

| # | Платформа | Лицензия | Стек (be / fe) | Тип | Глубина кастомизации | Inline citations | Multilingual UI | Звёзды / активность 2025 | Главная слабость |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **Dify** | Apache 2.0 (+патч) | Flask / Next.js | No-code + BaaS | Pipeline — да, UI — форк | Да, встроенные refs | Да (RU+) | ~110k⭐, очень активен | Монолит, кастом UI = форк |
| 2 | **Flowise** | Apache 2.0 (+EE dir) | Node.js / React | No-code | Pipeline — да, UI сырой | Частично | Частично | ~48k⭐ | Node плохо дружит с indic-NLP |
| 3 | **Langflow** | MIT | FastAPI / React | Low-code | Pipeline — да; embedded-chat виджет | Кастомно | Частично | ~100k⭐, CVE-2025 серия | Не production UI; security-history |
| 4 | **create-llama + LlamaIndex** | MIT | FastAPI или Next / Next + @llamaindex/chat-ui | Code-first scaffold | Полная | **First-class** (`CitationQueryEngine`, PDF pages) | i18n сами | ~46k⭐, активен | Не продукт — scaffold |
| 5 | **AnythingLLM** | MIT | Node/Express / React + Electron | No-code | Workspace-уровень, слабо | Чипы внизу; **inline нет** | Широкая i18n | ~54k⭐ | Нет inline-цитат (#2064) |
| 6 | **Onyx (ex-Danswer)** | MIT (CE) + EE | FastAPI + Vespa / Next | Code-first enterprise search | Hybrid index, рерank, 40+ коннекторов | Да | Частично (EN-first) | ~15–20k⭐ | Overkill, enterprise-фокус |
| 7 | **Khoj** | **AGPL-3.0** | Django / Next (Bun) | Code-first | Ограниченная | Есть | Да | ~30k⭐+ | AGPL вирусная; не book-QA |
| 8 | **RAGFlow** | Apache 2.0 | Python + Infinity/ES / React | No-code + API | Deep-doc parsing, GraphRAG, RAPTOR, visual chunk edit | **First-class «traceable citations»** с превью в PDF | CN/EN основные | ~70k⭐, Octoverse-лидер 2025 | Тяжёлый деплой; OCR тиб/devanagari — под вопросом |
| 9 | **Verba** | BSD-3 | FastAPI + Weaviate / Next | Code-first modular | Reader/Chunker/Embedder pluggable | Да | От embedding | ~7k⭐, **низкая активность 2025** | Weaviate снизил приоритет |
| 10 | **LibreChat** | MIT | Node + отдельный Python RAG API / React | Code-first ChatGPT-like | RAG в отдельный сервис; UI форк | В roadmap (#4615) | **40+ языков, RU native** | ~35k⭐+, очень активен | Inline-цитаты не как в Perplexity |
| 11 | **Open WebUI** | BSD-3 (+brand clause) | FastAPI / Svelte | No-code/code UI-платформа | Встроенный RAG, Pipelines/Functions, event-emitter citations | Есть, но для кастомного RAG нестабильно (#10456, #7333) | Полноценная i18n | ~125k⭐, самый активный UI 2025 | Inline для custom-pipeline = боль |
| 12 | **Cheshire Cat** | **GPL-3.0** | FastAPI / виджет Vue/React | Code-first framework | Hooks/tools/forms — полная | Руками через hooks | От фронта | ~3k⭐ | GPL + нишевое сообщество |

Headless-вспомогательные (упомянуты кратко):
- **Chainlit** (Apache 2.0, Python) — прототип/playground.
- **LangServe** — официально на поддержке, LangChain рекомендует LangGraph Platform вместо.
- **LangGraph Platform** (GA окт. 2025 с LangGraph 1.0) — managed runtime для агентных графов, free до 100k nodes/month.
- **Hayhooks** (deepset) — обёртка Haystack в REST/MCP/OpenAI-compat.
- **assistant-ui** — composable React-primitives (Radix-style) под AI-chat.

### Топ-3 кандидата под Dharma-RAG

1. **create-llama / LlamaIndex + `@llamaindex/chat-ui` + assistant-ui** — code-first, `CitationQueryEngine` даёт inline `[n]`, Python-совместимость с санскритской/палийской/тибетской NLP-экосистемой (indic-nlp, pyewts, botok), полная свобода UI.
2. **RAGFlow** (опционально для ветки PDF/сканов) — deep-doc parsing и traceable-citations с превью чанков. Полезен, если будете OCR-ить тибетские pecha/деванагари-издания. Требует тестов OCR-качества на сложных скриптах.
3. **LibreChat** как готовая оболочка + подмена RAG-API на свой LlamaIndex-сервис — мгновенный RU/EN/JA/ZH UI + multi-user + plugins. Быстрейший путь к production.

### Не брать

- **Khoj** — AGPL-3.0 токсична для закрытых надстроек.
- **Cheshire Cat** — GPL-3 + маленькое сообщество + слабый RAG-UX.
- **Verba** — проект в полу-заморозке у Weaviate (2025).
- **Flowise** — Node-стек не дружит с индологическим NLP.

### Headless-сценарий

Если хотите строить **свой UI**, но не переизобретать оркестрацию — берите backend из одного из: `LlamaIndex server`, `Hayhooks`, `LangGraph Platform`, `RAGFlow API`, `Dify API` (BaaS), `Onyx CE API`. UI — Next.js + assistant-ui / chat-ui.

---

## 5. Современный стек (2025–2026) — конкретные рекомендации

### Backend

| Вариант | Когда брать |
|---|---|
| **FastAPI + LangGraph 1.0** | Default для production Dharma-RAG. Явный state-graph ложится на RAG: `detect_lang → rewrite → hybrid_retrieve → rerank → guardrails → generate → extract_citations → validate`. Durable execution, HITL, `astream_events` для гранулярного streaming UX. |
| **LangServe** | Только legacy. Для новых проектов депрекейтно. |
| **LlamaIndex Workflows** | Альтернатива, если корпус уже индексируется в LlamaIndex. |

**Streaming**: FastAPI + `sse-starlette` + LangGraph `astream_events` → на клиент Vercel AI SDK UI message-parts protocol (`text-delta`, `source-url`, `tool-call`, `reasoning`). Python ≥ 3.11 обязателен из-за ContextVar propagation.

### Оркестрация агентов

| Фреймворк | Модель | Для Dharma-RAG |
|---|---|---|
| **LangGraph 1.0** | Stateful graph | ⭐ Production default |
| **LlamaIndex AgentWorkflow** | Workflow + events | Альтернатива, RAG-native |
| **CrewAI** | Role-based | MVP/демо, недетерминирован |
| **Pydantic AI** | Type-safe | Восходит, тонкий и быстрый; разумный выбор если не нужен tooling LangSmith |
| **AutoGen v0.4** | Event-driven actors | Research-only, ушёл из prod |
| **OpenAI Agents SDK** | Handoffs | Узкий usecase, OpenAI lock-in |
| **Google ADK** | Multi-agent | Только GCP/Gemini |

### Frontend

| Стек | Когда |
|---|---|
| **Next.js 15 App Router + TS + Tailwind + shadcn/ui + assistant-ui + Vercel AI SDK v6** | ⭐ Default |
| **SvelteKit 2** | Если команда уже Svelte (плюс: Open WebUI на Svelte) |
| **Nuxt 3** | Если Vue-команда |
| **Remix / React Router 7** | OK, но меньше готовых AI-компонентов |
| **Chainlit/Gradio/Streamlit** | Только internal tools/demo, не prod |

Готовые AI-UI примитивы: **assistant-ui** (Radix-style), **shadcn AI blocks** (`AIInlineCitation`, `AISources`, `AIReasoning`, `AIBranch`), **@llamaindex/chat-ui**.

### Streaming

| Протокол | Для чего |
|---|---|
| **SSE** | ⭐ Chat-ответ, стандарт LLM API, proxy-friendly, auto-reconnect |
| **WebSocket** | Только если нужен realtime-collab / voice |
| **HTTP chunked** | Для export/download |

### i18n

| Библиотека | Решение |
|---|---|
| **next-intl** | ⭐ Next.js App Router, ICU, native middleware-routing `/ru/…`, `/bo/…` |
| **react-i18next** | Если не-Next, лучшая TMS-экосистема |
| **Lingui** | Если критичен бандл |
| **Paraglide** | Только с Next, typed, маленький |

### Рендеринг скриптов (критично)

```css
:lang(bo) { font-family: "Noto Serif Tibetan", "Jomolhari", serif; line-height: 2; }
:lang(sa), :lang(pi) { font-family: "Noto Serif Devanagari", serif; }
:lang(zh-Hant) { font-family: "Noto Serif TC", "Source Han Serif TC", serif; }
```

Subset через `unicode-range` в `@font-face` обязателен (Noto Sans CJK full = ~20 MB). Tibetan Uchen в Safari исторически регрессирует (W3C `tibt-gap` analysis) — тестировать на живых macOS + iOS. Tibetan уже сегментирован через tsheg `་` — не трогать `word-break`. Devanagari: `letter-spacing` ломает conjuncts, `text-transform` не работает.

### Транслитерация

- **Санскрит/Пали**: `sanscript.js` (IAST ↔ Harvard-Kyoto ↔ ITRANS ↔ Velthuis ↔ Devanagari).
- **Тибетский**: `pyewts` на backend (EWTS ↔ Unicode Tibetan), JS-пакеты менее поддержаны.
- **Китайский**: `pinyin-pro`.
- **UX**: toggle "Script / Transliteration / Both"; поиск нормализует к IAST, ищет по всем формам.

### Glossary / hover

**Floating UI** + свой компонент с `useHover` + `useFocus` + `useDismiss`. Native HTML Popover API = Baseline Widely Available (апр. 2025), но CSS Anchor Positioning ещё partial — Floating UI остаётся дефолтом до 2027.

### Длинные документы

`@tanstack/react-virtual` для virtual scroll. Sticky TOC. Anchored scroll-restore с highlight-fade. Lazy-load колонки перевода через IntersectionObserver.

### Sync-scroll параллельных текстов

Не по pixel-position (разная длина убивает sync), а по **ближайшему видимому `data-segment-id`**. Хранить alignment как TMX/JSON `{src_id, tgt_ids[]}`. Для Kangyur/Tengyur alignments уже есть у 84000.co, для Pali — в SuttaCentral bilara-data.

### Deployment

| Платформа | GPU | Long-running | Для Dharma-RAG |
|---|---|---|---|
| **Vercel** | ❌ | 800s max (Fluid) | ⭐ Frontend only |
| **Railway** | ❌ | ✅ | ⭐ Backend + Qdrant + Postgres + Redis |
| **Fly.io** | Limited (beta) | ✅ | Альтернатива Railway |
| **Render** | ❌ | ✅ | Предсказуемая альтернатива |
| **Docker Compose / Hetzner** | ✅ | ✅ | Self-host вариант, дёшево |
| **Kubernetes** | ✅ | ✅ | Overkill до 10k MAU |
| **Modal / Runpod / Replicate** | ✅ | serverless GPU | ⭐ Embedding-reindex, finetuned LLM inference |
| **LangGraph Platform** | managed | ✅ | Free до 100k nodes/month |

Рекомендуемая связка: **Vercel (web) + Railway/Fly (api + qdrant + pg + redis) + Modal (GPU batch reindex)**. LLM — API (Anthropic/OpenAI/DeepSeek). Локальная Qwen/Llama через vLLM на Modal — опционально для privacy-инстансов.

---

## 6. Архитектурные развилки

### Monorepo vs polyrepo

**Monorepo на Turborepo + pnpm workspaces + uv workspaces** (для Python). Структура:
```
apps/web        — Next.js
apps/api        — FastAPI + LangGraph
apps/indexer    — batch ingestion
packages/shared-types   — zod-схемы из pydantic (datamodel-code-generator)
packages/ui     — shadcn-компоненты
packages/i18n   — ICU каталоги
data/           — bilara-стиль JSON сегментов, версионируется
```

Polyrepo оправдан только если команды Python и TS работают полностью независимо — для Dharma-RAG маловероятно.

### BFF vs единый API

**Лёгкий BFF в Next.js** (только auth-проксирование, per-user rate-limits), основная логика — в FastAPI. Frontend стримит напрямую с FastAPI через Next.js rewrites или с `api.dharma-rag.example` с CORS. Не строить полноценный второй сервис — это overengineering для одиночного проекта.

### SSR vs SPA

**SSR/RSC (Next.js App Router)** + static-first для страниц корпуса. Причины: SEO для публичных сутр → приток из Google/Perplexity; i18n через middleware; критичный LCP на медленных сетях (Индия/Непал/Бутан); RSC streaming хорошо ложится на LLM-ответ. SPA — только если всё за auth-wall (приватная библиотека конкретной линии передачи).

Важно: **ISR/SSG для страниц сутр** — десятки тысяч URL, revalidate on-demand при обновлении перевода.

### Аутентификация

| Сценарий | Рекомендация |
|---|---|
| Single-user / личный | Auth.js + magic-link, или вообще без auth (tailnet/localhost) |
| Multi-user публичный SaaS | **Clerk** (free до 10k MAU, Organizations для sangha/учебных центров) |
| Postgres-centric | **Supabase Auth** (экономит стек, если pgvector там же) |
| On-prem / университет / монастырь | **Keycloak** (SAML с институтом, LDAP) |

Типовая ошибка — брать Clerk для single-user beta. Начать без auth вообще — потом добавить.

### Offline / local-first

Для Dharma-RAG это **реальный usecase** (ретриты, плохой интернет в Гималаях):

- **PWA** через `next-pwa` / Workbox.
- **Dexie.js** поверх IndexedDB — кэш прочитанных сутр, closed chats, glossary.
- **RxDB** — если нужен sync между девайсами (CouchDB/Supabase adapters), поддержка E2E-шифрования.
- **Local LLM вариант**: `transformers.js` v3 + WebGPU + BGE-small для client-side embedding; корпус в IDB (quantized Parquet/SQLite ~ несколько GB, грузить по частям); ответы — облачный LLM при наличии сети.
- **CRDT для collab-аннотаций**: **Yjs** + Liveblocks/y-websocket если sangha'и с совместными комментариями.

### Обработка длинных документов

Правило: **один документ ≠ одна страница**. Бить по естественной структуре (chapter/section/verse), URL = `/read/toh231/c3#v12`, deep-link на stable segment-ID. Virtual scroll обязателен. TOC как sticky sidebar. Mini-map для ориентации в Аштасахасрике или Йогачарабхуми (10k+ параграфов).

---

## 7. UX-паттерны для цитируемого RAG — что воровать у лидеров

Анализ: Perplexity, NotebookLM, ChatGPT web-search, Claude Projects, Glean, Elicit, SciSpace.

| Паттерн | Источник | Для Dharma-RAG |
|---|---|---|
| **Numbered inline `[n]`** | Perplexity, ChatGPT | Must. Минимальное вторжение. |
| **Hover-card c превью chunk + метаданными** | Perplexity, Elicit | Must. Показать сутру, главу, переводчика, folio. |
| **Click → jump-to-source с подсветкой** | NotebookLM, SciSpace | Must — открыть документ в reader-pane с highlight'ом чанка. |
| **Side-by-side: ответ слева / reader справа** | NotebookLM, SciSpace Copilot | Desktop default для Dharma-RAG. |
| **Pull-quote рядом с ответом** | Elicit, SciSpace | Обязательно для религиозных текстов (антигаллюцинационный щит). |
| **Source transparency list** "Использовано N, не использовано M" | Glean | Да. Статус confidence опционально. |
| **Streaming citations как `source-part` первыми** | Perplexity | Показать источники сверху как плейсхолдеры, потом стримить текст с резолвом `[n]`. |
| **Явный "broken citation"** | редко, но нужно | Да — когда источник недоступен, показать явно. |
| **Query reformulation chips** | Perplexity, You.com | Для Dharma-RAG — "refine by canon", "exclude commentaries", "include Tibetan parallels". |
| **Dharmamitra "Explanation" button** | Dharmamitra MITRA | ⭐ **Search-first, AI as optional helper**, не chat-first. Кнопка `Explain this passage` под каждым поисковым результатом — on-demand AI-summary. |
| **Dharmamitra "Expand context"** | MITRA | ±N сегментов вокруг найденного. |
| **84000 pop-up trilingual glossary** | 84000.co | Hover на термине → EN/Tib/Skt карточка + "contexts in current text: N". |
| **Stable citation ID в URL** (`/translation/toh231`) | 84000 | Must. |
| **Versioned print** ("generated at X from online version Y") | 84000 | Да — академически критично. |
| **Bilara segment IDs** (`mn1:1.1`) | SuttaCentral | ⭐ Фундамент data-model. Git как source of truth, JSON по сегментам. |
| **CTS URN** (`urn:dharma:tib:toh231.degé:4.12`) | Perseus/Scaife | Абстракция над версиями — отделяет логическую ссылку от физического файла. Рекомендую. |
| **Versification conversion** (Derge↔Narthang↔Lhasa folio) | BibleEngine | Критично для Kangyur изданий. |

---

## 8. Что именно воровать у проектов-соседей (сводка)

Короткие формулы (детальные карточки проектов — в пункте 6 исходной задачи; из-за пространства привожу сжато):

- **84000.co**: bilingual toggle + synchronized segment alignment; pop-up trilingual glossary; stable Tohoku IDs (`toh231`); versioned print с timestamp + link to latest.
- **SuttaCentral + Bilara**: git-based JSON-сегменты как source of truth; Bilara-CAT для переводчиков; advanced search с sutta-ID + romanized ignore-diacritics; segment-level parallel display; Pali/Chinese lookup-tool (клик → словарь в sidebar).
- **BuddhaNexus → DharmaNexus**: ArangoDB для intertextuality-графа; heat-map параллелей в тексте; Table/Graph/Numbers views; фильтры limit/exclude коллекций.
- **Dharmamitra MITRA**: **"Explanation" и "Expand context" кнопки под результатами поиска** — search-first UX, AI опциональна. Cross-lingual query (EN → тибетские пассажи). Grammar-popup с sandhi candidates. Deep Research mode как отдельный режим ответа с цитатами из DharmaNexus + secondary literature. Browser extension, Emacs-клиент, StarDict-словари — много клиентов на один бэк.
- **BDRC / BUDA**: **IIIF viewer** для сканов (Mirador / Universal Viewer — не велосипедить). LOD/RDF метаданные (авторы, lineages). Stable PURL-URI.
- **Perseus / Scaife**: CTS URN citation scheme, widget-ecosystem (модульный reader — отдельно morpho-lookup, AI-summary, alignment viewer). Vue + GraphQL + Django + ES — разумная эталонная архитектура.
- **STEPBible / BibleEngine**: versification conversion — переносимый layer для множества изданий одного текста.
- **bible-rag (`calebyhan/bible-rag`)**: FastAPI + SQLAlchemy async + pgvector + FTS + RRF + cross-encoder rerank; multilingual-e5-large + bge-reranker-v2-m3; Gemini primary + Groq fallback; streaming NDJSON; Redis cache. **Самый близкий готовый blueprint по стеку** — форкабельная reference-implementation.
- **FoJin (`xr843/fojin`)**: 9,200+ текстов, 8 UI-языков, 420K vectors (BGE-M3 + HNSW), multi-provider LLM, knowledge graph 31K+ entities. «Ask XiaoJin» кнопка при select-text в reader'е. IIIF integration. Sidebar с cross-textual parallels через pgvector cosine. **Оценить как direct competitor и опорный пример** — один из лучших open-source референсов ровно для того, что строит Dharma-RAG.
- **DharmaSutra.org (Kumar Gauraw, 2026)**: semantic chunking по стихам + комментариям (не по character count); multilingual embedding для санскрит/хинди/english mix. Подтверждает, что наивный 1000/200 chunking — смерть для канонических текстов.

Избегать: TITUS-style frames и proprietary fonts; закрытые коммерческие стеки (Logos/Accordance — только идеи); велосипедный image viewer (IIIF закроет); chat-first AI как primary UX в отрыве от текста; псевдо-RAG без цитат (уровень случайных biblegpt).

---

## 9. Три архитектурных варианта для Dharma-RAG

### Вариант A — Minimal Viable (1–2 месяца одному разработчику)

**Цель**: персональный/узко-пользовательский инструмент с хорошим ретривалом и честными цитатами.

- **Backend**: FastAPI + LlamaIndex (`CitationQueryEngine`) + Qdrant + Postgres + BGE-M3 + BGE-reranker-v2-m3.
- **Frontend**: Next.js 15 + `@llamaindex/chat-ui` (или Chainlit для ещё более быстрого старта) + next-intl.
- **Citations**: inline `[n]` с hover-card; pull-quote.
- **Reader**: простой SSG для каждой сутры, segment-IDs в URL.
- **Deployment**: Docker Compose на одной Hetzner-VPS + Vercel для web.
- **Auth**: нет или Auth.js magic-link.
- **Без**: reader-workbench, knowledge graph, PWA, collab.

**Риски**: без kogda-yet-проверенных alignments корпуса — слабая поддержка ориг↔перевод; ограниченная аналитика.

### Вариант B — Sweet Spot (4–6 месяцев, 2–3 разработчика)

**Цель**: серьёзное продуктовое приложение — reader + chat Q&A с полноценным citation-UX + API.

- **Backend**: FastAPI + LangGraph 1.0 + LlamaIndex retrievers + Qdrant (named vectors per язык) + Postgres + Redis + sse-starlette.
- **Frontend**: Next.js 15 + assistant-ui + shadcn AI-blocks (AIInlineCitation/AISources/AIReasoning) + Vercel AI SDK v6 + next-intl + Floating UI + @tanstack/react-virtual.
- **Reader Room**: bilingual sync-scroll по `data-segment-id`; pop-up glossary (84000-style); stable URLs (`/read/toh231/c3#v12`); IAST/Wylie/Devanagari toggle через sanscript.js / pyewts.
- **Chat Q&A**: inline [n] citations with hover-card c метаданными (сутра/глава/переводчик/folio); pull-quote; source transparency list; click→jump-to-source в reader-pane (side-by-side).
- **API**: OpenAPI + MCP server.
- **Data model**: Bilara-style JSON (git source of truth) + CTS URN layer + versification conversion.
- **Deployment**: Vercel (web) + Railway (api/qdrant/pg/redis) + Modal (GPU batch reindex).
- **Auth**: Clerk (public multi-user) или Auth.js (self-host).
- **Observability**: Langfuse + Sentry + Ragas для RAG eval.
- **Monorepo**: Turborepo + pnpm + uv.

**Риски**: требуется disciplined data pipeline (segment IDs, alignments); LangGraph 1.0 свежий — пинуйте версии; OCR-качество для тибетских pecha — отдельная задача.

### Вариант C — Ambitious (12+ месяцев, команда 4–6)

**Цель**: полноценная платформа уровня FoJin/Dharmamitra + уникальный Russian-centric слой.

Всё из варианта B плюс:

- **Research Workbench**: heat-map параллелей (BuddhaNexus-style), Table/Graph/Numbers views, экспорт BibTeX/RIS.
- **Knowledge Graph**: сущности (люди, тексты, линии передачи, термины), Apache Jena Fuseki или Neo4j/ArangoDB.
- **Study Companion**: SRS-флэшкарты, планы изучения, прогресс, аннотации, PWA + RxDB offline-sync + Yjs collab.
- **IIIF viewer** для сканов BDRC (Mirador).
- **Custom eval** с экспертами-переводчиками через HITL в LangGraph.
- **Multi-tenant** для sangha'й / учебных центров (Clerk Organizations или Keycloak).
- **Browser extension и MCP server** — как Dharmamitra.

**Риски**: огромный scope; нужны domain experts (переводчики, ламы) как part-time contributors; эксплуатационные расходы растут.

---

## 10. Сводная сравнительная таблица вариантов

| Параметр | Minimal A | Sweet Spot B | Ambitious C |
|---|---|---|---|
| Срок до prod | 1–2 мес | 4–6 мес | 12+ мес |
| Команда | 1 dev | 2–3 devs | 4–6 devs + эксперты |
| Frontend | chat-ui / Chainlit | Next.js + assistant-ui | то же + Reader Workbench + IIIF |
| Backend | FastAPI + LlamaIndex | + LangGraph, Redis, streaming | + Fuseki/Neo4j, HITL, eval |
| Reader Room | минимальный | полный bilingual sync | + glossary + scans |
| Research tools | нет | базовый facet search | heat-map + Table/Graph/Numbers |
| Study tools | нет | нет | SRS + PWA + Yjs |
| API/MCP | REST | REST + MCP | + browser extension + Emacs |
| Auth | нет/magic-link | Clerk / Auth.js | + Orgs / Keycloak |
| Deployment | Compose + Vercel | Vercel + Railway + Modal | + k8s для production scale |
| Риск провала | низкий | средний | высокий без команды |
| Стоимость ops/мес | $20–80 | $150–400 | $1k+ |

---

## 11. Открытые вопросы к пользователю

Это то, без чего дальнейший архитектурный выбор не имеет смысла:

1. **URL репозитория**: точный ли он? Если приватный — можно ли получить дамп ключевых файлов (README, docs/, pyproject.toml, docker-compose.yml)?
2. **Аудитория**: single-user (ваш личный инструмент) / узкий круг (sangha, коллеги) / публичный SaaS? От этого зависит auth, multi-tenancy, scale.
3. **Primary surface**: reader-first, chat-first или research-workbench-first? Или все три (= вариант C)?
4. **Корпус**: только тексты (plain), или также сканы (IIIF + OCR ветка)? Есть ли готовые alignments (например, 84000 Kangyur/Tengyur или SuttaCentral Bilara), или планируется строить их?
5. **Русский корпус**: собственные переводы или существующие (Берзин, Парибок, Рудой, Торчинов, Андросов…)? Какие лицензии?
6. **LLM**: только API (Anthropic/OpenAI/DeepSeek) или обязательно self-host (Qwen/Llama на локальном GPU)?
7. **Citations-требования**: достаточно ли Perplexity-style inline `[n]` с hover, или нужен академический уровень (точный folio, версия издания, URN)?
8. **Offline/ретрит-сценарий**: важен или нет? Определяет PWA + local embeddings ветку.
9. **Open-source или закрытое?** Влияет на выбор лицензий зависимостей (Khoj AGPL, Cheshire Cat GPL отпадают при закрытой модели).
10. **Сроки и команда**: какой из вариантов A/B/C реалистичен по ресурсам?

---

## Заключение

Без доступа к репозиторию нельзя критиковать конкретные решения, но можно сказать следующее: **для RAG над дхармическим корпусом существует узкий «правильный коридор» архитектурных решений, за пределами которого проекты ломаются**. Этот коридор:

- **Search/reader-first, AI-optional** (Dharmamitra-паттерн), а не chat-first.
- **Stable segment-IDs + Bilara-style JSON в git** как единственный надёжный источник правды; всё остальное — проекции.
- **Hybrid retrieval** (BM25 + dense BGE-M3 + cross-encoder rerank); никогда только dense-only.
- **Citation-first UX**: inline `[n]` + hover-card + click→jump, а не «список чипов внизу».
- **Next.js 15 + assistant-ui + FastAPI + LangGraph 1.0 + Qdrant** — на сегодня самый зрелый стек для такого класса систем.
- **IIIF + CTS URN + versification conversion** — стандарты, без которых религиозно-текстовый проект не станет академически достойным.
- **Никакого Khoj/Cheshire Cat** (лицензии), **никакого Verba** (замороженность), **Open WebUI только для быстрого MVP**, но не как финальный UX.

Сравнительный анализ с FoJin, Dharmamitra, bible-rag, DharmaSutra.org показывает, что уровень продвинутых аналогов в 2025–2026 уже высок — Dharma-RAG имеет смысл строить как вариант B с осознанным заимствованием UX-идей из 84000 (reading-room) + Dharmamitra (search+AI toggle) + SuttaCentral/Bilara (data-model) + Perseus/Scaife (widget ecosystem + CTS). Это даст конкурентоспособный продукт в узкой русско-ориентированной нише при разумных ресурсах. Вариант C оправдан только при наличии команды и институциональной поддержки; вариант A — разумный первый шаг, если пока один разработчик.
