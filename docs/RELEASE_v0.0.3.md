# v0.0.3 — Retrieval Foundation

Second code-bearing release. Adds the three components that have to land before Qdrant can be populated — a structural parent/child chunker, the BGE-M3 embedding encoder, and Phoenix-based distributed tracing — plus the bilingual README and project-scoped Claude Code subagents. Days **7-9** of the 21-day Phase 1 plan.

No retrieval endpoint yet. Day-10 (full corpus ingest into Qdrant) is the next step; the actual `POST /api/query` surface ships in `v0.1.0` around day 21.

## Highlights

- 🧱 **Parent/child chunker** (`src/processing/chunker.py`) — pure and dependency-free, `TokenCounter` injected via DI. Parents target 1536 tokens on paragraph boundaries; children target 384 on segment boundaries. The live DB went from **124,532 flat chunks → 10,227 structured** (3,749 parents + 6,478 children) via the idempotent `scripts/rechunk.py` backfill. Retrieval will serve children; generation reads parents.
- 🧠 **BGE-M3 encoder** (`src/embeddings/bge_m3.py`) — multilingual (100+ langs) dual-head model: 1024-dim dense + sparse lexical weights in a single forward pass. Lazy-loaded, thread-safe, structural `BGEM3ModelProtocol` for DI-friendly tests (22 unit tests, zero model downloads). fp16 auto-selection mirrors FlagEmbedding's CPU-forces-fp32 behaviour. Smoke-tested end-to-end: self-similarity 1.000, cross-similarity ~0.48, Pāli tokens show up in the top sparse weights.
- 🔭 **Phoenix observability** (`src/observability/tracing.py`) — OpenTelemetry OTLP/gRPC → Phoenix container (`:4317`), FastAPI + HTTPX auto-instrumentation, web UI on `:6006`. Single-container SQLite backend instead of Langfuse's 3-container stack; OTel-native, so traces would port to Jaeger/Grafana without code changes. Verified: 5 `/health` requests produce 5 visible traces. Langfuse stays co-running until `v0.1.0` for comparison.
- 🚀 **CUDA torch on 1080 Ti** — `torch 2.5.1+cu121`, `torch.cuda.is_available() == True`. Drops the day-10 full-corpus embedding pass from ~10 h (CPU) to ~25 min (GPU).
- 🌐 **Bilingual README** (EN primary, RU translation) with language selector. Overclaims about jhāna, pragmatic dharma, and contemporary-masters corpora removed — they'll return when backed by shipped content.
- 🤖 **Three project-scoped Claude Code subagents** in `.claude/agents/` — `dharma-code-reviewer`, `buddhist-scholar-proxy`, `eval-analyst`. Invoked on demand from the VS Code extension.

## What's not in this release

- Still no retrieval, reranking, or LLM calls. `/health` is the only responsive endpoint.
- Qdrant collection `dharma_v1` not yet populated (that's day-10, arriving in the next push to `dev`).
- Langfuse still running alongside Phoenix — removed in `v0.1.0`.
- CI pipeline (ruff + mypy + pytest + alembic) not yet in place — see blocker B-003.

## Stats

- **107 tests passing** (94 unit + 13 integration). Pre-commit gating on ruff, mypy, detect-secrets.
- **10,227 structured chunks** live in Postgres (down from 124,532 flat).
- **Device:** 1080 Ti, 11 GB VRAM, CUDA 12.1 wheel of torch.

## Quickstart

```bash
git clone https://github.com/toneruseman/Dharma-RAG.git
cd Dharma-RAG
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
docker compose up -d
alembic upgrade head

# Optional: load the full SuttaCentral corpus + restructure
git clone --depth 1 --branch published \
  https://github.com/suttacentral/bilara-data.git data/raw/suttacentral
python scripts/ingest_sc.py --nikayas mn,dn,sn,an
python scripts/rechunk.py

# Smoke-test the BGE-M3 encoder on N chunks
python scripts/test_bge_m3.py --n 32

# Run the API; open Phoenix at http://localhost:6006
uvicorn src.api.app:app --reload
```

Full instructions: [README.md](../README.md).

## Links

- 📋 [docs/STATUS.md](STATUS.md) — live per-day progress tracker
- 🏛 [docs/decisions/0001-phase1-architecture.md](decisions/0001-phase1-architecture.md) — authoritative Phase 1 architecture (ADR-0001)
- 🗓 [docs/RAG_DEVELOPMENT_PLAN.md](RAG_DEVELOPMENT_PLAN.md) — 120-day RAG roadmap
- 📜 Full diff: [v0.0.2...v0.0.3](https://github.com/toneruseman/Dharma-RAG/compare/v0.0.2...v0.0.3)

## Next milestone

**v0.1.0 — Foundation** (day 21, ~late May 2026): Qdrant indexing + hybrid retrieval + BGE-reranker + Contextual Retrieval + `POST /api/query` + Ragas baseline eval (target: `ref_hit@5 ≥ 60%`, `faithfulness ≥ 0.80`), with Langfuse fully removed.

---

> _"Sabbe sattā sukhitā hontu"_ — Пусть все существа будут счастливы.
