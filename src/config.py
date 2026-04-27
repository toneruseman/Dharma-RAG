"""Application settings loaded from environment variables and .env file."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Central configuration for the Dharma RAG application.

    Values are loaded from environment variables and the .env file at the
    project root.  Every field corresponds to a variable in .env.example.
    """

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM Provider (primary: OpenRouter) ---
    # OpenRouter is the unified gateway used for Contextual Retrieval
    # (rag-day-16+) and future generation. Routing is OpenAI-compatible.
    openrouter_api_key: str = Field(default="")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1")

    # Direct Anthropic (legacy/fallback). Most code paths route via OpenRouter.
    anthropic_api_key: str = Field(default="")

    # --- Optional LLM fallbacks ---
    openai_api_key: str = Field(default="")
    google_api_key: str = Field(default="")

    # --- Contextual Retrieval (rag-day-16+) ---
    # Default model passed to OpenRouter for context generation. Anything that
    # OpenRouter routes to is acceptable; ``anthropic/claude-3.5-haiku`` is the
    # validated default per Anthropic's Contextual Retrieval paper.
    context_model: str = Field(default="anthropic/claude-3.5-haiku")

    # --- Embedding & evaluation APIs ---
    voyage_api_key: str = Field(default="")
    cohere_api_key: str = Field(default="")

    # --- Transcription (Phase 2) ---
    groq_api_key: str = Field(default="")

    # --- Voice (Phase 3) ---
    deepgram_api_key: str = Field(default="")
    elevenlabs_api_key: str = Field(default="")
    livekit_api_key: str = Field(default="")
    livekit_api_secret: str = Field(default="")
    livekit_url: str = Field(default="")

    # --- Vector DB ---
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: str = Field(default="")

    # --- Application Database (Postgres: FRBR corpus + app tables) ---
    # Default is the local dev compose password; prod overrides via env.
    database_url: str = Field(
        default="postgresql+asyncpg://dharma:dharma_dev@localhost:5432/dharma"  # pragma: allowlist secret
    )

    # --- Observability ---
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="http://localhost:3000")

    # Phoenix replaces Langfuse per ADR-0001. OTLP/gRPC endpoint — set to
    # "" to disable tracing entirely (useful for unit tests / CLIs).
    phoenix_otlp_endpoint: str = Field(default="http://localhost:4317")
    phoenix_ui_url: str = Field(default="http://localhost:6006")

    # --- App configuration ---
    app_env: AppEnv = Field(default=AppEnv.DEVELOPMENT)
    app_host: str = Field(default="0.0.0.0")  # noqa: S104
    app_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")
    debug: bool = Field(default=False)

    # --- Models ---
    embedding_model: str = Field(default="BAAI/bge-m3")
    reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3")
    router_llm: str = Field(default="claude-haiku-4-5-20251001")
    default_llm: str = Field(default="claude-sonnet-4-6")
    complex_llm: str = Field(default="claude-opus-4-6")

    # --- Retrieval tuning ---
    retrieval_top_k: int = Field(default=100)
    rerank_top_k: int = Field(default=10)
    hybrid_dense_weight: float = Field(default=0.6)
    hybrid_sparse_weight: float = Field(default=0.4)
    semantic_cache_threshold: float = Field(default=0.92)

    # --- Telegram Bot (Phase 1.5) ---
    telegram_bot_token: str = Field(default="")
    telegram_allowed_users: str = Field(default="")

    # --- Storage paths ---
    data_dir: Path = Field(default=PROJECT_ROOT / "data")
    qdrant_storage: Path = Field(default=PROJECT_ROOT / "qdrant_storage")
    logs_dir: Path = Field(default=PROJECT_ROOT / "logs")

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.app_env == AppEnv.DEVELOPMENT

    @property
    def database_url_sync(self) -> str:
        """Sync-driver URL derived from ``database_url`` for Alembic DDL ops.

        SQLAlchemy Alembic migrations run synchronously; we swap the
        asyncpg driver for psycopg 3 so the same connection string works
        in both contexts without maintaining two env vars.
        """
        return self.database_url.replace("+asyncpg", "+psycopg")


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
