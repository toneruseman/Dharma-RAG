# v0.1.0 — Phase 1 Foundation

End of the 21-day Phase 1 plan. Three previous releases (`v0.0.1`, `v0.0.2`, `v0.0.3`) shipped the corpus, chunker, embedder, and observability scaffold. **`v0.1.0` is the first release with a usable retrieval surface**: a stable `POST /api/query` endpoint that returns ranked Buddhist-canon passages with normalised scores, and an internal `POST /api/retrieve` for evaluation and tuning.

LLM generation, citation verification, and the front-end are deliberately out of scope here — they're Phase 2+ (rag-day-22 onward) and the App-track that starts in parallel from app-day-01.

---

## Highlights

- 🔍 **`POST /api/query` — stable production retrieval contract** (day 19). Accepts only semantic params (`query`, `top_k≤20`, `language`, `forbidden_works`); pipeline knobs are **server-side defaults** so we can keep tuning RRF weights, swap rerankers, and re-encode collections without breaking downstream consumers (LLM service, future Telegram bot, frontend). Response strips internal diagnostics and exposes only `Source(work_canonical_id, segment_id, text, snippet, score ∈ [0, 1])` + `PipelineMetadata(version, collection, rerank, expand_parents, n_candidates)`. Concept: [`13 — RAG-service contract`](concepts/13-rag-service-contract.md).
- 🧭 **Hybrid retrieval — RRF over 3 channels** (day 12). Dense BGE-M3 + sparse BGE-M3 + Postgres BM25 (`tsvector` GIN, ASCII-folded for Pāli diacritic-insensitive matching), fused via Reciprocal Rank Fusion (k=60). One async pipeline; ~80 ms end-to-end on GPU.
- 🪜 **Contextual Retrieval (Anthropic pattern), `dharma_v2`** (days 15-17). Each child chunk gets a 50-100 token LLM-generated *context prefix* (sutta name, section, immediate context) prepended before BGE-M3 encoding. Industrial run via OpenRouter (Anthropic Haiku 3.5) on 6,478 children, ~$8 total. Synthetic-golden A/B: `ref_hit@5` rose **0.400 → 0.567** (+16.7 pp); `MRR` rose 0.244 → 0.368. Concept: [`11 — Contextual Retrieval`](concepts/11-contextual-retrieval.md).
- 🪟 **Small-to-big retrieval** (day 18). Search children (~384 tokens, precise), return parents (~1024-2048 tokens, rich context). One self-JOIN in Postgres; LLM gets a semantically-complete passage, UI gets the precise child fragment for highlighting (`snippet` field). Concept: [`12 — Parent/child retrieval`](concepts/12-parent-child-retrieval.md).
- ⚡ **Production-default flipped** (day 18 cutover, after the day-17 A/B). `dharma_v2` + `rerank=False` + `expand_parents=True`. The cross-encoder reranker **degrades** quality on context-prefixed embeddings (v2+rerank 0.467 < v2 alone 0.567) — likely because BGE-reranker-v2-m3 was trained on raw chunk text. The reranker stays optional via `rerank: bool | None` in `/api/retrieve` for A/B; production never pays its 7-20 s/query cost.
- 📊 **Eval framework** (day 14, extended day 17). `src/eval/` with typed YAML golden loader, pure-function metrics (`ref_hit@K`, MRR), and a runner that A/B's any two configurations. Synthetic v0.0 (30 QA, generated against the live corpus) is the iteration set; B-001 (authoritative buddhologist v0.1) is still open. Reports in [`docs/EVAL_BASELINE.md`](EVAL_BASELINE.md) and [`docs/EVAL_CONTEXTUAL_AB.md`](EVAL_CONTEXTUAL_AB.md).
- 📚 **Integration-level documentation** (day 20). [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — module map, ingest + query data flow, storage, deps, dependency rules. [`docs/RAG_PIPELINE.md`](RAG_PIPELINE.md) — runtime trace of one `POST /api/query`: mermaid sequence + component diagrams, per-stage Phoenix spans, latency breakdown, failure modes. Sits above the 13 per-concept docs in [`docs/concepts/`](concepts/INDEX.md).
- 🔭 **Phoenix per-stage spans**. Every retrieval request emits `hybrid.encode`, `hybrid.channels`, `hybrid.rrf`, `hybrid.enrich`, and (when active) `hybrid.rerank` under the FastAPI request span — visible end-to-end at `localhost:6006`.

## Numbers (synthetic golden v0.0, n=30)

| Configuration | `ref_hit@5` | `ref_hit@20` | `MRR` | Latency/query |
|---|---:|---:|---:|---:|
| `dharma_v1` + rerank (day-13 baseline) | 0.400 | 0.600 | 0.244 | ~7.5 s |
| `dharma_v1` + no rerank | 0.367 | 0.533 | 0.246 | ~95 ms |
| `dharma_v2` + rerank | 0.467 | 0.733 | 0.319 | ~7.5 s |
| **`dharma_v2` + no rerank (production)** | **0.567** | **0.767** | **0.368** | **~80 ms** |

Synthetic v0.0 is **directional**, not authoritative. It was bootstrapped from the live corpus to unblock iteration while waiting for the buddhologist-built v0.1 (blocker B-001). Quality verdicts at v1.0 and beyond will require human-annotated ground truth.

## What's not in this release

- **No LLM generation.** `POST /api/query` returns ranked sources only — citation-aware generation, prompt caching, hallucination guards live in Phase 2 (rag-day-22+).
- **No frontend.** App-track (Next.js + Telegram bot + audit log) starts in parallel from app-day-01 and consumes the v0.1.0 `POST /api/query` contract.
- **No CI.** Pre-commit hooks (ruff + ruff-format + mypy strict + detect-secrets + line-ending) keep the local safety net intact. CI re-introduction tracked as **B-004** with `uv` (Astral) before broader release.
- **No buddhologist golden set.** Iteration runs on synthetic v0.0 (30 QA). Full quality claims wait for B-001.

## Stats

- **285 unit tests passing** (~3 s, hermetic, no GPU/Qdrant/Postgres needed). Pre-commit gating on ruff, mypy, detect-secrets.
- **6,478 child chunks** in `dharma_v2` (with Contextual Retrieval prefix), encoded by BGE-M3 fp16 on GTX 1080 Ti.
- **~80 ms** end-to-end per query on warm GPU.
- **4 Alembic migrations** (FRBR + author seeds + `chunk.fts_vector` + `chunk.context_text/version/model`).
- **13 concept docs** + 2 integration docs + 1 ADR — all in [`docs/`](.).

## Quickstart

```bash
git clone https://github.com/toneruseman/Dharma-RAG.git
cd Dharma-RAG
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp .env.example .env

# Bring up Postgres + Qdrant + Phoenix
docker compose up -d
alembic upgrade head

# Load corpus (one-time, ~10 min)
git clone --depth 1 --branch published \
  https://github.com/suttacentral/bilara-data.git data/raw/suttacentral
python scripts/ingest_sc.py --nikayas mn,dn,sn,an
python scripts/rechunk.py

# Index dharma_v2 (Contextual Retrieval). Needs OPENROUTER_API_KEY.
# ~110 min wallclock @ concurrency=5, ~$8 via Anthropic Haiku 3.5.
python scripts/contextualize_corpus.py
python scripts/reindex_qdrant_v2.py

# Run the API
uvicorn src.api.app:app --reload

# Try it
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "what is dukkha?", "top_k": 5}'
```

Phoenix UI at `http://localhost:6006` — full request span tree on every call.

## Migration from v0.0.3

1. Pull `dev`, run `alembic upgrade head` (migrations 003 + 004 introduce FTS + contextual columns).
2. **Reindex Qdrant** to populate `dharma_v2`:
   ```bash
   python scripts/contextualize_corpus.py
   python scripts/reindex_qdrant_v2.py
   ```
   `dharma_v1` (raw text) stays in place — the day-17 A/B and any rollback path still need it.
3. **Replace any prior client of `POST /api/retrieve`** (if you wired one before this release) with `POST /api/query`. The old endpoint stays available for evaluation, but its surface will keep evolving with retrieval-engine changes.
4. Set `OPENROUTER_API_KEY` in `.env` if you want to re-run Contextual Retrieval (otherwise `dharma_v2` Postgres columns are read-only and Qdrant collection is enough).

## Open blockers

- **B-001:** authoritative golden v0.1 from a buddhologist. Synthetic v0.0 unblocks iteration but is not authoritative for quality claims at v1.0.
- **B-004:** CI re-introduction with `uv` before broader release.

Both tracked in [`docs/STATUS.md`](STATUS.md).

## What ships next

- **Phase 2 (rag-day-22+):** LLM generation on top of `POST /api/query`. Citation verification, hallucination guards, prompt caching. Quality loop: golden set expansion, fine-tuning evals, Pāli glossary integration.
- **App-track (app-day-01+):** Next.js + Tailwind UI, Docker Compose dev stack, audit logging, refused-query log. Integration through the frozen `src/rag/schemas.py`.
- **Phase 3+:** Whisper transcription of dharmaseed talks (corpus expansion), voice interface (LiveKit + Deepgram + ElevenLabs).

Authoritative roadmap: [`docs/RAG_DEVELOPMENT_PLAN.md`](RAG_DEVELOPMENT_PLAN.md), [`docs/APP_DEVELOPMENT_PLAN.md`](APP_DEVELOPMENT_PLAN.md). Day-by-day status: [`docs/STATUS.md`](STATUS.md).

---

Tag this release after merging the bump PR:

```bash
git tag -a v0.1.0 -m "v0.1.0 — Phase 1 Foundation"
git push origin v0.1.0
```
