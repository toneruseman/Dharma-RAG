# Project Status

> Единый индекс прогресса по обоим трекам разработки (RAG-ядро и App-слой).
> Обновляется вручную при закрытии каждого `*-day-NN`.
>
> **Source of truth:** git log + этот файл. Чаты не являются source of truth.

- **Версия:** 2026-04-28
- **Активная ветка:** `feat/app-day-02-stub-rag` (rag-day-22 + app-day-01 уже в `dev`)
- **Последний релиз:** `v0.1.0` — Phase 1 Foundation (2026-04-28)
- **Следующий milestone:** v0.2.0 (Phase 2 — Quality Loop, ablation/glossary/FT)
- **MVP-ready:** ✅ Готов показать буддологу для разблокировки B-001 (golden v0.1)
- **Стратегия:** **B** — RAG-first до `v0.1.0` (`rag-day-21`), затем интерливинг RAG+APP

---

## Как читать этот файл

Два параллельных плана, один репо, один чат:

- [`docs/RAG_DEVELOPMENT_PLAN.md`](RAG_DEVELOPMENT_PLAN.md) — RAG-ядро (120 дней, 4 фазы)
- [`docs/APP_DEVELOPMENT_PLAN.md`](APP_DEVELOPMENT_PLAN.md) — App-слой (60 дней + Phase 7+)

Дни нумеруются раздельно: `rag-day-NN` и `app-day-NN`. Commits помечаются соответствующим префиксом.

---

## Текущий прогресс

### RAG-трек

| Day | Задача | Статус | Коммит |
|---|---|---|---|
| rag-day-01 | Docker Compose + FastAPI `/health` + config + logging | ✅ Done | `36f5846` |
| rag-day-02 | Postgres schema FRBR + Alembic миграции | ✅ Done | `d5eac80` |
| rag-day-03 | Скачать SuttaCentral bilara-data + parser dry-run | ✅ Done | `4618a5d` |
| rag-day-04 | Full ingest SuttaCentral (Sujato EN для MN/DN/SN/AN) | ✅ Done | `8ef9519` |
| rag-day-05 | **Gate:** Golden v0.1 от буддолога (30 QA) | 🚧 Blocked | Нужен буддолог на связи |
| rag-day-06 | Cleaner: Unicode NFC, Pali диакритика (IAST + ASCII-fold) | ✅ Done | `ce186c5` |
| rag-day-07 | Структурный chunker (384 child / 1024-2048 parent) | ✅ Done | `6c8ff98` |
| rag-day-08 | FlagEmbedding + BGE-M3 (dense + sparse на 100 чанках) | ✅ Done | `9f7e092` |
| rag-day-09 | Phoenix observability + OpenInference | ✅ Done | `c2defe2` |
| rag-day-10 | Qdrant collection `dharma_v1` + named vectors + full ingest (6478 child chunks, 4:40 min on 1080 Ti) | ✅ Done | `330ff30` |
| rag-day-11 | BM25 via Postgres FTS (`simple` config on `text_ascii_fold`, GIN index, generated column) | ✅ Done | `3627685` |
| rag-day-12 | Hybrid RRF (dense + sparse + BM25) + `POST /api/retrieve`, 62-96 ms/query on GPU | ✅ Done | `37df139` |
| docs/concepts | Учебная библиотека: 10 концептов на русском (RAG, FRBR, chunking, BGE-M3, Qdrant, BM25, RRF, Phoenix, eval) | ✅ Done | (this branch) |
| docs/eval/golden_v0.0 | Synthetic golden set, 30 QA, разблокирует day-14 eval без буддолога | ✅ Done | `e6d024f` |
| rag-day-13 | BGE-reranker-v2-m3 cross-encoder + Phoenix per-stage spans + `rerank` API flag | ✅ Done | `d7de5a0` |
| rag-day-14 | Eval framework + baseline numbers on synthetic golden v0.0 (`docs/EVAL_BASELINE.md`): ref_hit@5 = 0.40 with rerank, MRR 0.244 — **below planned ≥0.60**, gap to be closed by Contextual Retrieval (day 16-17) | ✅ Done | `91f0ae2` |
| rag-day-15 | Contextual Retrieval — prompt template v1 + DI plumbing. `PROMPT_TEMPLATE_V1` validated in-chat against 50 stratified sample chunks (`docs/contextual/validation_output_opus_v1.md`); `src/contextual/contextualizer.py` ships protocol + dataclass + helpers; 22 unit tests. Industrial run + provider choice (Haiku vs cloud.ru) deferred to day 16. | ✅ Done | `008a1af` |
| rag-day-16 | Contextual Retrieval industrial run. OpenRouter provider (one gateway, many models — Anthropic Haiku 3.5 default). Migration 004 adds `chunk.context_text/version/model` columns. Prompt v2 (fix Pāli title hallucinations after smoke). Concurrency=5 + sort by parent. 6,478 chunks contextualized (~$8 via OpenRouter). Re-encoded into Qdrant collection `dharma_v2` (existing `dharma_v1` untouched). 47 unit tests. | ✅ Done | `6478174` |
| rag-day-17 | A/B `dharma_v1` vs `dharma_v2` on synthetic golden v0.0. **Headline win**: `ref_hit@5` 0.400 → 0.567 (+16.7 pp), `ref_hit@20` 0.600 → 0.767 (+16.7 pp), MRR 0.244 → 0.368 (+12.4 pp). **Surprise**: cross-encoder reranker **degrades** quality on contextualized embeddings (v2+rerank 0.467 < v2 alone 0.567). New production-default candidate: **`dharma_v2` + `rerank=False`** (~115× faster per query). Day-14 headline miss (qa_002 sn56.11) FIXED — sutta now at top-5. `docs/EVAL_CONTEXTUAL_AB.md` published. 269 unit tests. | ✅ Done | `7fd3a7e` |
| rag-day-18 | Parent/child small-to-big retrieval + production cutover. New `HybridHit.child_text/expanded` fields; `_enrich` does a self-JOIN to substitute parent text when present. `hybrid_search(expand_parents=True)` default; reranker still scores `child_text` (independent of expansion). Production cutover: `RetrievalResources` now reads `settings.retrieval_collection` (`dharma_v2`), `retrieval_rerank_default` (False), `retrieval_expand_parents_default` (True). Concept doc 12. 267 unit tests. | ✅ Done | `de85fea` |
| rag-day-19 | `POST /api/query` — stable production retrieval endpoint with frozen contract. New `src/rag/{schemas,service}.py`: `QueryRequest` (semantic params only — no `rerank`/`expand_parents` knobs), `QueryResponse` with stripped `Source` shape (no internal scores/IDs), `PipelineMetadata` (`version`, `collection`, `rerank`, `expand_parents`, `n_candidates`). `RAGService` reuses `RetrievalResources` singleton via `get_resources()` — no second BGE-M3 load. Score normalisation: sigmoid on rerank, RRF/top-RRF otherwise. `forbidden_works` post-filter. Concept doc 13. 285 unit tests. | ✅ Done | `72d4dba` |
| rag-day-20 | Integration-level docs: `docs/ARCHITECTURE.md` (module map, data flow ingest→query, storage, external deps, dependency rules) + `docs/RAG_PIPELINE.md` (per-stage runtime trace, mermaid sequence + component diagrams, Phoenix span tree, latency breakdown ~78 ms, failure modes table). Sits above per-concept docs in `docs/concepts/` as the "single page that explains the whole system". No code changes; 285 unit tests still green. | ✅ Done | `8406793` |
| **rag-day-21** | **`v0.1.0` release — Phase 1 Foundation closed.** Version bumped 0.0.3 → 0.1.0 in `src/__init__.py` + `pyproject.toml`. CHANGELOG `[Unreleased]` consolidated under `[0.1.0] — 2026-04-28`. `docs/RELEASE_v0.1.0.md` published (highlights, numbers, what's not in scope, quickstart, migration from v0.0.3, blockers, what ships next). 285 unit tests green; mypy strict + ruff clean. Tag `v0.1.0` to be created after PR merge. | ✅ Done | `9ccd7b6` |
| rag-day-22 | Phase 2 starts — synthetic golden expanded 30 → **100 QA** (`docs/eval/golden_v0.0_extended.yaml`); `src/eval/runner.py::run_eval` accepts `expand_parents`; new `scripts/eval_ablation_v0.0e.py` runs an **8-cell matrix** `{v1,v2}×{rerank=F,T}×{expand=F,T}` and writes `docs/EVAL_ABLATION_v0.0e.md`. **Headline (n=100)**: production `v2_norerank_expand` ref_hit@5 = **0.450** vs day-13 baseline 0.410 (Δ **+4 pp**, was +16.7 pp on n=30 — direction confirmed, magnitude smaller, regression-to-mean expected on bigger n). Reranker paradox on v2 reproduced (−1 pp). Parent expansion = 0 effect on `ref_hit` (expected — only changes returned text). Adversarial / Pāli probes still weak. 286 unit tests green. **MVP-ready**: numbers on directional eval are stable enough to demo to a buddhologist for unblocking B-001. | ✅ Done | (this branch) |
| rag-day-23 | Pāli глоссарий и query expansion (concept 14) — cyrillic.yaml + romanized→IAST mapping, query rewrite перед encode, optional `expand_pali` flag в `/api/query`. | ✅ Done | (merged) |
| rag-day-24 | `/api/answer` — LLM-grounded answer endpoint (concept 15). System prompt + style modes (auto/concise/detailed), inline `[work_id]` citations, OpenRouter provider, `AsyncOpenRouterLLM`. 16-model comparison `docs/EVAL_ANSWER_MODELS.md`; default `deepseek/deepseek-v4-flash` ($0.003/req). | ✅ Done | (merged) |
| rag-day-25 | SSE streaming для chat-ответа (concept 22) — backend `POST /api/answer/stream`, `AsyncOpenRouterLLM.stream()`, `AnswerService.stream_answer()` async generator с retrieval_done / token / citation / done / error events; `IncrementalCitationScanner` для split-bracket detection. 14 новых unit-тестов. | ✅ Done | (merged) |
| **rag-day-26** | **Retrieval failure analysis** (concept 26). Скрипт `scripts/eval_failure_analysis.py` прогнал prod-config (`dharma_v2 + rerank=False + expand_parents=True`, top_k=100) на golden v0.0_extended (n=100). 24/100 fully missed (ref_rank=∞). Топ-15 worst разобраны вручную в `docs/FAILURE_PATTERNS.md`, категоризованы (golden-narrow / abstract topical / verse-mismatch / English-title / Russian lexical / definitional anomaly). **Critical insight:** ~9–10 из 15 — артефакт synthetic-разметки, не реальный quality gap; на v0.1 от буддолога ref_hit@5 может вырасти до 0.55–0.65 без ML-улучшений. Roadmap пересмотрен: cheap wins (chunking-audit / glossary expansion) до multi-source ingest. | ✅ Done | (this branch) |
| **rag-day-27** | **qa_040 anomaly investigation** (concept 27). Скрипт `scripts/investigate_qa040.py` (3 фазы, 13 retrieval calls, top-200 per-channel pool): A — 5 phrasings satipaṭṭhāna × 2 collections, B — 3 generalisation probes (dukkha/anatta/Right View), C — chunk-level inspection. **Root cause:** multi-causal (H4 per-channel dense∞ + H5 query specificity + H3 foundational-vs-derivative bias). H1 (Contextual prefix drift) **опровергнута**. Generalisation подтверждена на sn56.11/sn22.59. mn117 — exception (термин в title → BM25 ловит). Bonus finding: BM25 не нормализует диакритику. **Recommendations** в `docs/QA040_INVESTIGATION.md`: definitional query expansion → curated foundational mapping → BM25 unaccent → RRF foundational-boost. Roadmap обновлён: rag-day-28 = definitional expansion + foundational mapping. | ✅ Done | (this branch) |
| **rag-day-28** | **Definitional expansion + foundational mapping** (concept 28). Закрывает recommendations 1+2 из `QA040_INVESTIGATION`. Новый `src/expand/` (definitional regex + FoundationalMatcher), `data/glossary/foundational.yaml` (18 seed-пар из Sahaya 12 essentials + 6 наших добавок). Wire-up: definitional → Pāli → encode (порядок матери); BM25 видит raw query; foundational boost — post-RRF callable передаваемый в `hybrid_search`, расширяет pool до 100 когда активен. Live-проверка на real-стеке: **mn10 #1, dn22 #2** на «What is satipaṭṭhāna?» (без day-28 их в top-20 нет); 4/6 английских foundational-кейсов попали в #1 (`satipaṭṭhāna / dependent origination / anapanasati / noble eightfold path / right view`). Промахи (`dukkha/sn56.11`, `anatta/sn22.59`, `metta/snp1.8`) — те же что в QA040 отсутствовали в top-200 на v2; нужны rag-day-29 (BM25 unaccent) и rag-day-31 (verse chunking). 441 unit-тест green. | ✅ Done | (this branch) |
| … | (всего 120 дней в плане) | | |

### App-трек

| Day | Задача | Статус | Коммит |
|---|---|---|---|
| app-day-01 | pnpm monorepo + `web/` Next.js 16 (Turbopack) + Tailwind 4 + shadcn/ui (`base-nova` style, `neutral` palette). Root `package.json` with `dev:web` / `dev:api` / `dev` (concurrently). `web/` runs on `:3001`, FastAPI stays on `:8000`. `next.config.ts` pins Turbopack workspace root to repo. `.gitignore` covers node_modules / .next / .pnpm-store. | ✅ Done | `bd2b1bf` |
| app-day-02 | Mock RAG-сервис + factory. Новый `RAGServiceProtocol`, `StubRAGService` (3 фиксированных source'а, ~1 ms, без Qdrant/Postgres/GPU), `get_rag_service()` factory, env `RAG_BACKEND=stub\|real` (default **`stub`** — fresh clone сразу работает). В stub-режиме `/api/retrieve` не монтируется (нет смысла без real data); `/api/query` отдаёт фиктивные source'ы с тем же контрактом что в проде. `pnpm dev:api` теперь не требует docker-compose. 298 unit tests green (+12 новых). | ✅ Done | (this branch) |
| app-day-03 | OpenAPI → TypeScript типы для фронта | 📋 Planned | — |
| app-day-04 | Next.js layout + темы + дизайн-токены | 📋 Planned | — |
| app-day-05 | Docker Compose dev-friendly (web + api + services) | 📋 Planned | — |
| app-day-06 | Postgres schema для app-таблиц (audit_log, refused_queries, feedback) | 📋 Planned | — |
| … | (всего 60 дней в плане) | | |

---

## Блокеры

| ID | Что | Срочность | Кто разблокирует |
|---|---|---|---|
| B-001 | Нет буддолога на связи для golden set v0.1 | Высокая (блокирует rag-day-05 и все последующие quality-метрики) | Человек, не код |
| ~~B-002~~ | ~~`docs/old/` содержит устаревшие параметры~~ | ✅ Closed | Удалено в `399bda2` |
| B-001 (re-scoped) | Buddhologist for golden eval set | Был блокером, **deferred until proof-of-concept ready** | Synthetic v0.0 покрывает iteration; v0.1 authoritative нужна перед public release |
| B-004 | Re-introduce CI using uv | Перед v0.1.0 release (day 21) | [#20](https://github.com/toneruseman/Dharma-RAG/issues/20) |

---

## Критические интеграционные точки

Моменты, когда треки встречаются и контракт должен совпасть:

1. **`src/rag/schemas.py` zafiksируется на app-day-02.** RAG-трек обязан реализовать протокол именно с этими schemas.
2. **`RAGService` имплементация появится в RAG-треке примерно на rag-day-14–21.** До этого app-трек работает на `StubRAGService`.
3. **app-day-19 (audit log) требует** Postgres schema из rag-day-02. Порядок: rag-day-02 → app-day-06 → app-day-19.
4. **Phoenix в prod (app-day-58)** использует ту же инстанцию, что RAG-трек ставит на rag-day-09.

---

## Последовательность выполнения (стратегия B)

**Фаза A (дни 1–21): строго RAG.** Phase 1 Foundation из RAG-плана без отвлечения на APP. Цель — рабочий `RAGService` на реальном корпусе SuttaCentral с baseline-метриками.

```
rag-day-02  Postgres FRBR schema + Alembic
rag-day-03  SuttaCentral bilara parser (dry-run)
rag-day-04  Full ingest SuttaCentral EN (Sujato)
rag-day-05  Golden v0.1 от буддолога (blocked)
rag-day-06  Cleaner: NFC + Pali diacritic normalization
rag-day-07  Structural chunker (384 child / 1024-2048 parent)
rag-day-08  BGE-M3 embedding inference
rag-day-09  Phoenix observability
rag-day-10  Qdrant dharma_v1 named vectors + ingest
rag-day-11  BM25 через Postgres FTS
rag-day-12  Hybrid retrieval (RRF)
rag-day-13  BGE-reranker-v2-m3
rag-day-14  Первый eval (baseline)
rag-day-15  Contextual prompt-template
rag-day-16  Full re-ingest dharma_v2
rag-day-17  A/B v1 vs v2
rag-day-18  Parent-child expansion
rag-day-19  /api/query endpoint (RAG-ядро)
rag-day-20  docs update
rag-day-21  v0.1.0 release
```

**Фаза B (дни 22+): интерливинг.** RAG Phase 2 (quality loop) идёт фоном, APP-трек стартует параллельно от `app-day-01`. Промежуточные дни смешиваются по принципу «тяжёлый RAG → лёгкий APP» или наоборот.

**Блокер B-001 (буддолог)** не останавливает всю Фазу A — `rag-day-05` выполняется в фоне, пока идут технические дни. Если к дню 14 буддолога нет, используем временный synthetic golden v0.0 для baseline, а человеческий v0.1 приходит позже.

---

## Policy

1. **Каждый закрытый day** → обновление этой таблицы + короткая запись в `CHANGELOG.md`.
2. **Каждые 5 дней** → ревью блокеров, перепланирование если нужно.
3. **Расхождение с ADR** → новый ADR (0002, 0003…).
4. **Feature branches:** `feat/rag-day-NN-slug` или `feat/app-day-NN-slug`.
5. **Коммиты:** conventional commits с префиксом трека: `feat(rag): rag-day-02 Postgres FRBR schema`.
