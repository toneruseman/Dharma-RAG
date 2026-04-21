# Changelog

Все значимые изменения этого проекта документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
проект следует [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Initial repository structure
- Complete documentation (ARCHITECTURE_REVIEW, DAY_BY_DAY_PLAN, etc.)
- docker-compose.yml for local development
- Consent Ledger framework
- **rag-day-01:** FastAPI `/health` endpoint, Pydantic Settings, structlog, tests, ADR-0001.
- **rag-day-02:** Postgres corpus database (`dharma-db` in docker-compose), SQLAlchemy 2.x async models for FRBR (Work → Expression → Instance → Chunk) plus lookup tables (`tradition_t`, `language_t`, `author_t`), Alembic migration `001_initial_frbr` with seed data (7 traditions, 15 ISO 639-3 languages), integration tests for schema/models/migration-idempotency.
- **rag-day-03:** SuttaCentral bilara-data ingest skeleton: typed `BilaraFile`/`Segment` dataclasses, streaming `iter_bilara_files`/`iter_segments` parser with filename and nikaya derivation, `scripts/sc_dryrun.py` CLI that emits 10 segments from sujato's MN translation, 13 unit tests using an in-memory bilara fixture. No DB writes yet — persistence comes in rag-day-04.
- **rag-day-04:** Full SuttaCentral ingest into Postgres for sujato's English MN/DN/SN/AN (3,413 Works / 124,532 Chunks). Alembic migration `002_author_slug_sc_seeds` adds `author_t.slug` (unique partial index) and seeds `sujato` + `ms`. New `src/ingest/suttacentral/loader.py` with `load_file` / `load_directory` performs idempotent upserts keyed by `content_hash`, inserts one `Chunk` per bilara segment (cleaning and parent/child chunking come later), and enforces license/consent-ledger stamping at the Expression level. `scripts/ingest_sc.py` wraps the loader as an async CLI. 4 integration tests cover the full FRBR roundtrip, idempotency, unknown-author rejection, and multi-file directory loads.
- **docs:** `docs/APP_DEVELOPMENT_PLAN.md` (60-day plan for app layer) and `docs/STATUS.md` (unified progress tracker). Strategy B adopted: RAG-first through `v0.1.0` (rag-day-21), then interleave with app-track.

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
