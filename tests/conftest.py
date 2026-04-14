"""Shared pytest fixtures for Dharma RAG tests."""

from __future__ import annotations

import pytest

from src.config import AppEnv, Settings


@pytest.fixture()
def settings() -> Settings:
    """Return a Settings instance that ignores the .env file."""
    return Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.fixture()
def dev_settings() -> Settings:
    return Settings(_env_file=None, app_env=AppEnv.DEVELOPMENT)  # type: ignore[call-arg]


@pytest.fixture()
def prod_settings() -> Settings:
    return Settings(_env_file=None, app_env=AppEnv.PRODUCTION)  # type: ignore[call-arg]
