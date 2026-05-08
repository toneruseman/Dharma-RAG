# Dharma-RAG

🇬🇧 **English** · [🇷🇺 Русский](README.ru.md)

> **Dharma-RAG** is an open-source study companion for Buddhist practice and canon.
>
> Ask about a meditation technique, a sutta passage, or a Pāli term — the system finds precise passages in a curated corpus, cites every source, and answers in your language.
>
> MIT-licensed. No accounts, no subscriptions, no ads.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Pre-Alpha](https://img.shields.io/badge/Status-Pre--Alpha-orange)]()
[![Phase: 1 Foundation](https://img.shields.io/badge/Phase-1%20Foundation-blue)]()
[![Release: v0.0.2](https://img.shields.io/badge/Release-v0.0.2-green)](https://github.com/toneruseman/Dharma-RAG/releases/tag/v0.0.2)

---

## Mission

Make the wisdom of contemplative traditions accessible to every practitioner, in every language, with faithfulness to the original teachings.

## Principles

1. **Grounded RAG, not chatbot** — every answer cites its sources.
2. **Free and open-source (MIT)** — no ads, sign-ups, or subscriptions.
3. **Dual-track development** — the public codebase only ships content we are allowed to ship.
4. **Consent Ledger** — every source in the corpus has a matching YAML record explaining how we got permission.
5. **Tool, not teacher** — Dharma-RAG helps you find teachings; it does not replace a living teacher or a qualified clinician.
6. **Privacy by default** — no user-data collection on our servers.

---

## Status (Phase 1 — day 7 of 21)

### Shipped

- ✅ Local dev stack via Docker Compose: Postgres 16 (`dharma-db`) + Qdrant + Langfuse.
- ✅ Postgres FRBR schema (Work → Expression → Instance → Chunk) with Alembic migrations.
- ✅ SuttaCentral ingest pipeline: **3,413 suttas / 10,227 chunks** (3,749 parents + 6,478 children) from Bhikkhu Sujato's English translations of MN/DN/SN/AN. Idempotent re-runs via `content_hash`.
- ✅ Text cleaner: Unicode NFC, Pāli IAST canonicalisation (`ṁ → ṃ`), ASCII-fold shadow column (`satipaṭṭhāna → satipatthana`) for BM25 matching.
- ✅ Parent/child structural chunker (parent ~1,536 tokens, child ~384 tokens) — the Parent Document Retrieval pattern.
- ✅ FastAPI `/health` endpoint, structured logging via structlog.
- ✅ 79 tests (65 unit + 14 integration), pre-commit gating on ruff / mypy / detect-secrets.

### In flight (days 8-21)

- ⏳ BGE-M3 embeddings (dense 1024d + sparse) with Qdrant named vectors (days 8-10).
- ⏳ BM25 over Postgres FTS with Pāli-aware tokenisation (day 11).
- ⏳ Hybrid retrieval via Reciprocal Rank Fusion (day 12).
- ⏳ Reranking with BGE-reranker-v2-m3 on GPU (day 13).
- ⏳ Baseline eval through Ragas — faithfulness, ref_hit@5, citation_validity (day 14).
- ⏳ Contextual Retrieval (Claude Haiku context prefixes) — days 15-17.
- ⏳ `POST /api/query` endpoint (day 19).
- ⏳ **v0.1.0 release** (day 21).

### Longer horizon

- **Phase 2** (months 3-6) — expanded corpus (DhammaTalks.org, Access to Insight, PTS, academic papers), fine-tuned BGE-M3, Pāli glossary, regression CI, 100-question golden set.
- **Phase 3** (months 6-12) — mobile apps (Capacitor + SvelteKit), voice MVP (Pipecat + Deepgram + ElevenLabs), Dharmaseed audio corpus (~46,000 talks), live voice chat via LiveKit Agents, on-device STT/TTS (Sherpa-ONNX) for privacy.

---

## Quick start

### Requirements

- **Python 3.12+** (tested on 3.12.10).
- Docker + Docker Compose (for the local Postgres / Qdrant / Langfuse stack).
- ~10 GB free disk (bilara-data clone + future vector index).
- Optional: NVIDIA GPU with ≥12 GB VRAM for the reranker (arrives on day 13).

### Install

```bash
git clone https://github.com/toneruseman/Dharma-RAG.git
cd Dharma-RAG

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cp .env.example .env                # fill in ANTHROPIC_API_KEY when needed

docker compose up -d                # Postgres + Qdrant + Langfuse
alembic upgrade head

# Smoke test — /health is the only endpoint live today.
python -m uvicorn src.api.app:app --reload &
curl http://localhost:8000/health
```

### Optional: load the SuttaCentral corpus

```bash
git clone --depth 1 --branch published \
  https://github.com/suttacentral/bilara-data.git data/raw/suttacentral

python scripts/ingest_sc.py --nikayas mn,dn,sn,an
# → 3,413 suttas / 10,227 chunks ingested in ~90 s
```

`POST /api/query` lands on day 19.

---

## Documentation

**Active plans & decisions**

- [docs/STATUS.md](docs/STATUS.md) — unified day-by-day progress tracker (RAG + app), updated on every merge.
- [docs/decisions/0001-phase1-architecture.md](docs/decisions/0001-phase1-architecture.md) — **ADR-0001**, the authoritative record of Phase 1 architecture choices.
- [docs/RAG_DEVELOPMENT_PLAN.md](docs/RAG_DEVELOPMENT_PLAN.md) — 120-day RAG-core plan.
- [docs/APP_DEVELOPMENT_PLAN.md](docs/APP_DEVELOPMENT_PLAN.md) — 60-day application plan (backend + frontend + mobile).
- [CHANGELOG.md](CHANGELOG.md) — day-by-day changelog.
- [ROADMAP.md](ROADMAP.md) — long-horizon phase outline.

**Research & reference**

- [docs/Dharma-RAG-Research-EN.md](docs/Dharma-RAG-Research-EN.md) — full English project study (3,432 lines).
- [docs/Dharma-RAG.md](docs/Dharma-RAG.md) — working architecture & sources document.

---

## Repository layout

```
Dharma-RAG/
├── README.md / README.ru.md        ← you are here (EN / RU)
├── LICENSE                         ← MIT
├── CHANGELOG.md / ROADMAP.md
├── docker-compose.yml              ← Postgres + Qdrant + Langfuse
├── pyproject.toml                  ← Python 3.12+, dependencies
├── alembic.ini + alembic/          ← DB migrations (asyncpg + psycopg)
├── .claude/agents/                 ← project-shared Claude Code subagents
├── docs/                           ← see "Documentation" above
├── consent-ledger/                 ← YAML license records per source
│   ├── public-domain/              ← CC0, public domain
│   ├── open-license/               ← CC-BY, CC-BY-NC, etc.
│   └── explicit-permission/        ← content used with explicit author permission
├── src/                            ← Python RAG (managed by pyproject.toml)
│   ├── api/                        ← FastAPI app: /health, /api/retrieve, /api/query
│   ├── rag/                        ← stable production retrieval contract
│   ├── retrieval/                  ← hybrid search (dense + sparse + BM25 + RRF + rerank)
│   ├── embeddings/                 ← BGE-M3 encoder + Qdrant indexer
│   ├── contextual/                 ← Anthropic Contextual Retrieval (dharma_v2)
│   ├── eval/                       ← golden set loader, ref_hit / MRR metrics, runner
│   ├── observability/              ← Phoenix tracing wiring
│   ├── config.py                   ← Pydantic Settings
│   ├── db/                         ← SQLAlchemy 2.x FRBR models + async sessions
│   ├── ingest/suttacentral/        ← bilara parser + Postgres loader
│   ├── processing/                 ← cleaner (NFC, IAST, ASCII fold), chunker
│   ├── logging_config.py           ← structlog
│   └── cli.py                      ← command-line utilities
├── web/                            ← Next.js 16 app, App Router + Tailwind 4 + shadcn/ui
│   ├── app/                        ← routes (URL = folder structure)
│   ├── components/ui/              ← shadcn-installed components
│   ├── lib/utils.ts                ← shadcn `cn()` helper
│   └── package.json                ← scripts: dev (port 3001), build, lint
├── scripts/
│   ├── ingest_sc.py                ← CLI for SuttaCentral ingest
│   ├── contextualize_corpus.py     ← Contextual Retrieval batch (OpenRouter / Haiku)
│   ├── reindex_qdrant_v2.py        ← re-encode contextualized chunks into dharma_v2
│   ├── eval_retrieval.py           ← baseline eval (rerank A/B)
│   ├── eval_contextual_ab.py       ← day-17 v1 vs v2 A/B
│   ├── eval_ablation_v0.0e.py      ← day-22 8-cell ablation matrix
│   └── …                           ← rechunk, smoke_*, etc.
├── tests/
│   ├── unit/                       ← fast tests, no DB (286 total)
│   └── integration/                ← Postgres-backed tests
├── package.json + pnpm-workspace.yaml  ← root JS monorepo (pnpm workspace = `web/`)
└── data/                           ← gitignored: raw/, processed/, qdrant_storage/
```

### Running both stacks

From the repo root:

```bash
# Python RAG (FastAPI on :8000)
pnpm dev:api

# Web UI (Next.js on :3001)
pnpm dev:web

# Both at once (uses concurrently)
pnpm dev
```

`pnpm install` once in the root pulls Node deps for `web/`. No global pnpm install needed long-term — `package.json` declares `packageManager: pnpm@…` so [Corepack](https://nodejs.org/api/corepack.html) (built into Node 20+) can resolve it; if Corepack isn't available, `npm install -g pnpm` works too.

---

## License

- **Code:** MIT (see [LICENSE](LICENSE)).
- **Documentation:** CC-BY-SA 4.0.
- **Data:** see [consent-ledger/](consent-ledger/) — each source carries its own license record.

---

## Contact

- GitHub: [@toneruseman](https://github.com/toneruseman)
- Issues: [github.com/toneruseman/Dharma-RAG/issues](https://github.com/toneruseman/Dharma-RAG/issues)

---

🚀 Development started **14 April 2026**.
📍 Current phase: **Phase 1 Foundation** — week 1 (day **7** of 21).
🎯 Next milestone: **v0.1.0 — Foundation** (day 21, roughly end of May 2026).

Day-by-day tracker: [docs/STATUS.md](docs/STATUS.md).

> *"Sabbe sattā sukhitā hontu"* — May all beings be happy.
