# Changelog

Все значимые изменения этого проекта документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
проект следует [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **rag-day-07:** Parent/child structural chunker in `src/processing/chunker.py`. Pure, dependency-free: produces parents (target 1536 / max 2048 tokens, broken at paragraph boundaries) and children (target 384 / max 512, broken at segment boundaries). `TokenCounter` injected via DI for future BGE-M3 tokenizer swap. SuttaCentral loader rewired to emit parent+child instead of flat per-segment rows. `scripts/rechunk.py` rebuilds existing Instances in-place (ran on live DB: 124,532 flat → 10,227 structured chunks = 3,749 parents + 6,478 children, 48 s, 0 orphan children). 18 unit + 1 rechunk-idempotency integration test added (79 total passing).

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

## [0.1.0] — TBD (после Phase 1 Foundation, день 14)

Планируется:
- Qdrant collection с 56K chunks (dense BGE-M3)
- Базовый retrieval
- Golden eval test set (150+ queries)
- Langfuse observability
- Baseline metrics: ref_hit@5, topic_hit@5

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
