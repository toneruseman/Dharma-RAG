# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dharma RAG is a multilingual Buddhist teaching RAG (Retrieval-Augmented Generation) platform. It ingests texts from Buddhist sources (SuttaCentral, DhammaTalks, Access to Insight, etc.), embeds them with BGE-M3 hybrid (dense+sparse+ColBERT), stores in Qdrant, and generates answers via Claude API with citations. Documentation and user-facing text are in Russian.

## Commands

```bash
# Install (dev)
pip install -e ".[dev]"

# Lint
ruff check src/ tests/
ruff format src/ tests/

# Type check
mypy src/

# Tests
pytest                          # all tests (includes coverage by default)
pytest tests/unit/              # unit tests only
pytest -k "test_config"        # single test by name

# Local services (Qdrant + Langfuse + Postgres)
docker compose up -d

# CLI entry point
dharma-rag
```

## Architecture

**Pipeline flow:** Query → Pali glossary expansion → Hybrid retrieval (dense+sparse+BM25) → BGE reranking → Context assembly → Claude generation → Citation verification → SSE streaming response

**Key modules under `src/`:**
- `config.py` — Pydantic Settings singleton from `.env`, accessed via `get_settings()`
- `logging_config.py` — Structlog setup (JSON in prod, colored console in dev)
- `cli.py` — Entry point registered as `dharma-rag` console script
- `ingest/` — Source-specific scrapers with abstract base
- `processing/` — Text cleaning, NFC normalization, parent-child chunking (150/600 words)
- `embeddings/` — BGE-M3 hybrid encoder with abstract base
- `rag/` — Pipeline orchestrator: retrieval → reranking → generation
- `cache/` — Semantic cache layer (0.92 similarity threshold)
- `language/` — Language detection, Pali diacritics normalization
- `api/` — FastAPI app with HTMX/SSE streaming (Phase 4)
- `bot/` — Telegram bot via aiogram (Phase 1.5)
- `voice/` — Pipecat + LiveKit voice pipeline (Phase 3)
- `eval/` — RAGAS evaluation framework

**LLM routing:** Haiku for simple/routing tasks, Sonnet as default, Opus for complex queries. Multi-provider fallback via LiteLLM.

**Observability:** Langfuse for LLM tracing, Structlog for app logs.

## Code Conventions

- Python 3.11+, Ruff line length 100
- Ruff rules: E, F, W, I (isort), B (bugbear), UP (pyupgrade), N (naming), S (security). E501 and S101 are ignored.
- MyPy strict mode with pydantic plugin
- Async-first (pytest asyncio_mode = "auto")
- All config via environment variables / `.env` — no YAML/JSON config files
- Data sources require consent ledger entries in `consent-ledger/` (YAML, organized by license type)

## Data & Storage

- `data/` — gitignored; raw sources, processed chunks, audio, transcripts
- `qdrant_storage/` — gitignored; local Qdrant persistence
- `consent-ledger/` — tracked; YAML permission records per source (public-domain, open-license, explicit-permission)
- Qdrant runs on port 6333 (REST) / 6334 (gRPC)

## Phased Development

The project follows a 4-phase roadmap. Only Phase 1 (text RAG MVP) code exists currently. Modules for later phases (voice, bot, advanced RAG) have placeholder structure but no implementation yet.

## Pre-commit Hooks

This project uses pre-commit hooks. Before every commit:
- ruff auto-fixes linting issues
- ruff-format applies code style
- mypy checks types in src/
- detect-secrets prevents committing API keys

If a commit fails due to hook modifications:
1. Run `git diff` to see what was changed
2. Run `git add .` to stage the fixes
3. Retry `git commit`

If a commit fails due to mypy/test errors:
1. Fix the code issues
2. Retry commit

NEVER use `--no-verify` to bypass hooks unless explicitly instructed.
