"""Tests for src.config module."""

from __future__ import annotations

from src.config import AppEnv, Settings


def test_settings_defaults() -> None:
    """Settings should load with sensible defaults even without .env."""
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
    )
    assert s.qdrant_url == "http://localhost:6333"
    assert s.app_env == AppEnv.DEVELOPMENT
    assert s.app_port == 8000
    assert s.embedding_model == "BAAI/bge-m3"
    assert s.retrieval_top_k == 100
    assert s.hybrid_dense_weight == 0.6


def test_is_production() -> None:
    s = Settings(_env_file=None, app_env=AppEnv.PRODUCTION)  # type: ignore[call-arg]
    assert s.is_production is True
    assert s.is_development is False


def test_is_development() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.is_development is True
    assert s.is_production is False
