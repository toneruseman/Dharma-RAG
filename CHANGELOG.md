# Changelog

Все значимые изменения этого проекта документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
проект следует [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **rag-day-11:** BM25-style lexical retrieval via Postgres FTS in `src/retrieval/bm25.py`. Alembic migration 003 adds `chunk.fts_vector` as a `GENERATED STORED` `tsvector` derived from `text_ascii_fold`, with a GIN index for O(log N) `@@` match. Uses the `simple` text-search config (no stemming) so Pāli terms retain full token identity and the client-side `normalize_query()` mirrors day-6's `to_ascii_fold` + lowercase — `satipaṭṭhāna` and `satipatthana` produce identical tsqueries. Uses `websearch_to_tsquery` for safe user-query parsing and `ts_rank_cd` for cover-density scoring (IDF-weighted, position-aware — close enough to BM25 for hybrid fusion). 9 unit tests (pure-function normaliser + dataclass contract) + 8 integration tests against live Postgres (term-density ranking, diacritic folding both directions, parent exclusion, limit respect). 100% coverage of `bm25.py`.
- **Honest corpus note:** Sujato's English translation renders most Pāli doctrinal terms into English ("Satipaṭṭhāna Sutta" → "Mindfulness Meditation"), so BM25 on the current corpus retrieves proper nouns (`Anāthapiṇḍika` → MN 143 at 0.80), place names (`Sāvatthī`), and English doctrinal terms (`four noble truths` → SN 56.*, `noble eightfold path` → SN 45.*), but returns zero hits for bare Pāli queries like `satipaṭṭhāna` / `anapanasati`. This gap is by-design for day-11's pure-lexical channel — day-12 hybrid fusion pairs it with dense BGE-M3 (which DOES handle paraphrased/cross-lingual queries), and day-16 contextual retrieval adds Pāli uid + title to each chunk's embedding input, closing the gap for all three channels.
- **rag-day-10:** Qdrant indexer in `src/embeddings/indexer.py`. Named-vector collection `dharma_v1` (1024-d dense BGE-M3 cosine + learned sparse). Pure DI via `QdrantClientProtocol` + `EncoderProtocol` so unit tests run without Qdrant or CUDA (19 unit tests, 98% coverage). Integration tests verify real qdrant-client 1.17 accepts the `PointStruct` shape, `query_points` round-trips dense/sparse, identity-vector query returns cosine 1.0, and re-upsert on the same chunk UUID is idempotent (5 integration tests). CLI `scripts/index_qdrant.py` streams from Postgres with keyset pagination on `chunk.id`, filters to child chunks by default (`--include-parents` to override), supports `--limit N` for smoke runs and `--recreate` to drop the collection. **Full corpus indexed on GPU: 6,478 child chunks in 4:40 min on the 1080 Ti with fp16 (~23 chunks/sec), 0 failed batches.** `scripts/smoke_retrieval.py` runs a curated set of canonical queries (English paraphrase, Pali with/without diacritics, Russian cross-lingual) and prints dense + sparse top-3 with scores and text — qualitative sanity gate before the numeric eval on day 14.
- **Toolchain:** torch upgraded 2.5.1+cu121 → 2.6.0+cu124 (CVE-2025-32434 + transformers 4.57 pickle-loader gate). huggingface-hub pinned back to `<1.0` to match transformers 4.x. Both were latent conflicts from day-8; day-10 forced the resolution.

### Qualitative retrieval results (day-10 baseline, pre-reranker)
- 🟢 English paraphrase → canonical sutta: `mindfulness of breathing` → **MN 118 Anāpānassati** (0.700)
- 🟢 English doctrinal term → right collection: `four noble truths` → **SN 56.27** (0.714)
- 🟢 Cross-lingual: `страдание` (Russian) → **DN 22 Mahāsatipaṭṭhāna** (0.624)
- 🔴 Bare Pali term weak without reranker: `satipaṭṭhāna` does not retrieve MN 10 (top score 0.49); motivates day-11 hybrid + day-13 reranker.

---

## [0.0.3] — 2026-04-22

Retrieval foundation release. Adds the structural chunker, the BGE-M3
encoder, and Phoenix-based tracing — the three building blocks needed for
day-10 Qdrant indexing. No retrieval endpoint yet; that lands in `v0.1.0`.

### Added
- **rag-day-07:** Parent/child structural chunker in `src/processing/chunker.py`. Pure, dependency-free: produces parents (target 1536 / max 2048 tokens, broken at paragraph boundaries) and children (target 384 / max 512, broken at segment boundaries). `TokenCounter` injected via DI for future BGE-M3 tokenizer swap. SuttaCentral loader rewired to emit parent+child instead of flat per-segment rows. `scripts/rechunk.py` rebuilds existing Instances in-place (ran on live DB: 124,532 flat → 10,227 structured chunks = 3,749 parents + 6,478 children, 48 s, 0 orphan children). 18 unit + 1 rechunk-idempotency integration test added (79 total passing).
- **rag-day-08:** BGE-M3 encoder wrapper (`src/embeddings/bge_m3.py`). Lazy model load (2.3 GB weights only fetched on first `encode` call), thread-safe via `threading.Lock`, structural-type `BGEM3ModelProtocol` for DI-friendly unit testing (22 unit tests, no real model loaded). Device detection (auto/cuda/cpu) with fp16 auto-selection that mirrors FlagEmbedding's own CPU-forces-fp32 rule. `scripts/test_bge_m3.py` — smoke test on N chunks from Postgres (cosine determinism check, shape gates, top-5 sparse weights preview). `transformers<5` pin added because FlagEmbedding 1.3.5 uses pre-5.x APIs. Verified end-to-end on CPU: dense 1024-d self-similarity = 1.0, cross-similarity ~0.48-0.50, sparse weights non-empty on rare tokens.
- **rag-day-09:** Phoenix observability via OpenTelemetry + OpenInference (`src/observability/tracing.py`). `setup_tracing(fastapi_app=...)` installs a global TracerProvider with OTLP/gRPC exporter pointing at the local Phoenix container on `:4317`, attaches `FastAPIInstrumentor` + `HTTPXClientInstrumentor` for automatic request spans. `arize-phoenix` added to docker-compose (single container, SQLite persistence, UI on `:6006`) — lighter than the Langfuse stack (3 containers), OTel-native so traces are portable to Jaeger/Grafana without code changes. 7 unit tests cover enabled/disabled/idempotent setup. Smoke test: 5 `/health` requests through FastAPI produce 5 visible traces in the Phoenix dashboard. Langfuse stays running alongside during the v0.0.x window — removed in v0.1.0.
- **Tooling:** Three project-scoped Claude Code subagents in `.claude/agents/` — `dharma-code-reviewer`, `buddhist-scholar-proxy`, `eval-analyst`. Bilingual README (EN primary + RU translation with language selector).
- **Infra:** CUDA-enabled torch (`torch 2.5.1+cu121`) installed; `torch.cuda.is_available()` is now `True` on the GTX 1080 Ti (11 GB VRAM). Day-10 full-corpus embedding will run on GPU (~25 min expected) instead of CPU (~10 h).

### Changed
- **Corpus shape:** flat 124,532 per-segment chunks → structured 10,227 (3,749 parents + 6,478 children). Retrieval will serve children, generation will read parents.
- README rewritten and trimmed: removed premature claims about jhāna traditions, pragmatic dharma, and contemporary-masters corpus (not shipped yet — will return when backed by actual content).

### Known limitations
- No retrieval, no reranking, no `/api/query` endpoint — only `/health` responds.
- Qdrant collection `dharma_v1` not yet populated (day-10 task).
- Blockers still open: B-001 (golden eval set — buddhologist needed), B-002 (GPU was the blocker for day-13 reranker; now unblocked by CUDA install), B-003 (CI pipeline).

---

## [0.0.2] — 2026-04-21

Ingest foundation release. The first actual code drop after the `v0.0.1`
scaffolding tag: Postgres corpus, SuttaCentral ingest pipeline, and the
text cleaner are all running. No retrieval / rerank / generation yet —
those land progressively through days 7-21 and ship in `v0.1.0`.

### Added
- **rag-day-01:** FastAPI `/health` endpoint, Pydantic Settings, structlog, tests, ADR-0001.
- **rag-day-02:** Postgres corpus database (`dharma-db` in docker-compose), SQLAlchemy 2.x async models for FRBR (Work → Expression → Instance → Chunk) plus lookup tables (`tradition_t`, `language_t`, `author_t`), Alembic migration `001_initial_frbr` with seed data (7 traditions, 15 ISO 639-3 languages), integration tests for schema/models/migration-idempotency.
- **rag-day-03:** SuttaCentral bilara-data ingest skeleton: typed `BilaraFile`/`Segment` dataclasses, streaming `iter_bilara_files`/`iter_segments` parser with filename and nikaya derivation, `scripts/sc_dryrun.py` CLI that emits 10 segments from sujato's MN translation, 13 unit tests using an in-memory bilara fixture. No DB writes yet — persistence comes in rag-day-04.
- **rag-day-04:** Full SuttaCentral ingest into Postgres for sujato's English MN/DN/SN/AN (3,413 Works / 124,532 Chunks). Alembic migration `002_author_slug_sc_seeds` adds `author_t.slug` (unique partial index) and seeds `sujato` + `ms`. New `src/ingest/suttacentral/loader.py` with `load_file` / `load_directory` performs idempotent upserts keyed by `content_hash`, inserts one `Chunk` per bilara segment (cleaning and parent/child chunking come later), and enforces license/consent-ledger stamping at the Expression level. `scripts/ingest_sc.py` wraps the loader as an async CLI. 4 integration tests cover the full FRBR roundtrip, idempotency, unknown-author rejection, and multi-file directory loads.
- **rag-day-06:** Text cleaner pipeline (`src/processing/cleaner.py`): `to_canonical` applies HTML entity decode, tag strip, Unicode NFC, IAST anusvāra harmonisation (`ṁ → ṃ`), and whitespace collapse; `to_ascii_fold` produces a BM25-friendly diacritic-stripped shadow (`satipaṭṭhāna → satipatthana`). 27 unit tests cover Pali-specific edge cases. SC loader now populates both `chunk.text` (canonical) and `chunk.text_ascii_fold`, plus canonicalises work/expression titles. `scripts/reclean_chunks.py` backfills the fold column on pre-day-6 rows in place (ran successfully: 124,532 chunks scanned, 111,601 updated, 100 s).
- **docs:** `docs/APP_DEVELOPMENT_PLAN.md` (60-day plan for app layer), `docs/STATUS.md` (unified progress tracker), `docs/Dharma-RAG-Research-EN.md` (3432-line English research). README rewritten to reflect real state.

### Changed
- Project version in `pyproject.toml` and `src/__init__.py` aligned from aspirational `0.1.0` down to honest `0.0.2`. `0.1.0` is reserved for the day-21 Foundation milestone.

### Strategy
- **Strategy B** adopted: RAG-first through `v0.1.0` (rag-day-21), then interleave with app-track. Captured in `docs/STATUS.md`.

### Known limitations
- No retrieval, no reranking, no `/api/query` endpoint — only `/health` responds.
- Single source (SuttaCentral sujato EN, MN/DN/SN/AN). DhammaTalks, ATI, PTS, etc. arrive in Phase 2+.
- No golden evaluation set yet — gate on rag-day-05 is blocked pending buddhologist collaboration (see `docs/STATUS.md` blocker B-001).

---

## [0.1.0] — TBD (после Phase 1 Foundation, день 21)

Планируется:
- Qdrant collection `dharma_v1` с ~10K chunks (named vectors: dense BGE-M3 + sparse)
- Hybrid retrieval (dense + sparse) + BGE-reranker-v2-m3
- Contextual Retrieval (Anthropic method)
- Golden eval test set (30+ QA, buddhologist-curated)
- `POST /api/query` endpoint
- Phoenix-only observability (Langfuse removed)
- Baseline metrics: `ref_hit@5 ≥ 60%`, `faithfulness ≥ 0.80`

---

## [0.2.0] — TBD (после Phase 2 Quality, день 28)

Планируется:
- Hybrid search (dense + sparse + BM25)
- BGE-reranker-v2-m3
- Contextual Retrieval (Anthropic method)
- Pāli glossary и query expansion
- Semantic cache

---

## [0.3.0] — TBD (после Phase 3 Generation, день 42)

Планируется:
- Claude integration (Haiku/Sonnet routing)
- Streaming generation
- Citation verification
- CLI (`dharma-rag` command)
- 70%+ test coverage

---

## [0.4.0] — TBD (после Phase 4 Web MVP, день 56)

Планируется:
- FastAPI app
- HTMX frontend с SSE streaming
- Deployment на Hetzner
- Public URL https://dharma-rag.org
- CI/CD pipeline

---

## [0.5.0] — TBD (после Phase 5, день 63)

Планируется:
- Telegram bot (@DharmaRagBot)
- FSM guided meditation flows
- Rate limiting

---

## [0.6.0] — TBD (после Phase 6 Transcription, день 90)

Планируется:
- 35K часов транскрибированы (Dharmaseed)
- Полный корпус ~900K chunks
- Pāli LoRA fine-tune (optional)

---

## [0.7.0] — [0.13.0] — Phases 7-9 (месяцы 4-9)

Mobile, Voice MVP, Voice Production.
Детали: см. [ROADMAP.md](ROADMAP.md) и [docs/DAY_BY_DAY_PLAN.md](docs/DAY_BY_DAY_PLAN.md).

---

## [1.0.0] — TBD (месяц 12)

Public launch.
Планируется:
- 1000+ DAU
- Multi-language support
- LightRAG knowledge graph
- Curriculum planner + spaced repetition
- Public community Discord
