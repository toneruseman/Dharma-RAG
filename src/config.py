"""Application settings loaded from environment variables and .env file."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AppEnv(str, Enum):
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

    # --- LLM Provider (required) ---
    anthropic_api_key: str = Field(default="")

    # --- Optional LLM fallbacks ---
    openai_api_key: str = Field(default="")
    google_api_key: str = Field(default="")

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

    # --- Observability ---
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="http://localhost:3000")

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


def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
