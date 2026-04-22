# v0.0.2 — Ingest Foundation

First code-bearing release. Postgres FRBR corpus, SuttaCentral ingest pipeline, and a Pali-aware text cleaner are all running end-to-end. Days **1-6** of the 21-day Phase 1 plan — retrieval, reranking, and LLM generation ship progressively through days 7-21 as `v0.1.0`.

## Highlights

- 🗄️ **Postgres 16 corpus DB** — dedicated `dharma-db` service in docker-compose with a FRBR schema (**Work → Expression → Instance → Chunk**) plus lookup tables for traditions, languages, and authors. Alembic migrations create the schema from scratch and seed 7 traditions + 15 ISO 639-3 languages + 2 SuttaCentral authors.
- 📚 **SuttaCentral ingest** — parser for bilara-data JSON + idempotent loader (content-hash keyed). Local run produces **3,413 Works / 124,532 Chunks** from Bhikkhu Sujato's English Majjhima/Dīgha/Saṃyutta/Aṅguttara in ~90 seconds. Re-runs are a no-op.
- 🧹 **Text cleaner** — Unicode NFC, HTML tag strip, IAST anusvāra normalisation (`ṁ → ṃ`), whitespace collapse, and a diacritic-free ASCII shadow column so BM25 can match `satipatthana` queries against `satipaṭṭhāna` text.
- 🧪 **60 tests passing** — 47 unit + 13 integration. Pre-commit gating on ruff, mypy, and detect-secrets.

## What's not in this release

- No retrieval, no reranking, no LLM calls. `/health` is the only responsive endpoint.
- Only one source (SuttaCentral, sujato, English). DhammaTalks, Access to Insight, PTS, etc. arrive in Phase 2+.
- Golden evaluation set (30 buddhologist-curated QA) blocked pending collaboration — see `docs/STATUS.md` blocker B-001.

## Quickstart

```bash
git clone https://github.com/toneruseman/Dharma-RAG.git
cd Dharma-RAG
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
docker compose up -d
alembic upgrade head

# Optional: load the full SuttaCentral corpus
git clone --depth 1 --branch published \
  https://github.com/suttacentral/bilara-data.git data/raw/suttacentral
python scripts/ingest_sc.py --nikayas mn,dn,sn,an
```

Full instructions: [README.md](../README.md).

## Links

- 📋 [docs/STATUS.md](STATUS.md) — live per-day progress tracker
- 🏛 [docs/decisions/0001-phase1-architecture.md](decisions/0001-phase1-architecture.md) — authoritative Phase 1 architecture (ADR-0001)
- 🗓 [docs/RAG_DEVELOPMENT_PLAN.md](RAG_DEVELOPMENT_PLAN.md) — 120-day RAG roadmap
- 🗓 [docs/APP_DEVELOPMENT_PLAN.md](APP_DEVELOPMENT_PLAN.md) — 60-day app-track roadmap
- 📜 Full diff: [v0.0.1...v0.0.2](https://github.com/toneruseman/Dharma-RAG/compare/v0.0.1...v0.0.2)

## Next milestone

**v0.1.0 — Foundation** (day 21, ~late May 2026): BGE-M3 hybrid retrieval + BGE-reranker + Contextual Retrieval + `POST /api/query` + Ragas baseline eval (target: `ref_hit@5 ≥ 60%`, `faithfulness ≥ 0.80`).

---

> _"Sabbe sattā sukhitā hontu"_ — Пусть все существа будут счастливы.
