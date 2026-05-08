"""Unit tests for :mod:`src.rag.factory`."""

from __future__ import annotations

import pytest

from src.api._rag_stub import StubRAGService
from src.config import Settings
from src.rag.factory import get_rag_service


def test_factory_returns_stub_for_stub_backend() -> None:
    settings = Settings(rag_backend="stub")
    service = get_rag_service(settings=settings)
    assert isinstance(service, StubRAGService)


def test_factory_real_backend_requires_resources() -> None:
    settings = Settings(rag_backend="real")
    with pytest.raises(RuntimeError) as exc_info:
        get_rag_service(settings=settings)
    # Error message should name what's missing — saves debugging
    # someone else's deployment.
    msg = str(exc_info.value)
    assert "encoder" in msg
    assert "qdrant_client" in msg
    assert "reranker" in msg
    assert "session_maker" in msg


def test_factory_real_backend_partial_resources_still_errors() -> None:
    settings = Settings(rag_backend="real")
    # Pass one resource, leave the other three None — must still fail.
    with pytest.raises(RuntimeError) as exc_info:
        get_rag_service(settings=settings, encoder=object())  # type: ignore[arg-type]
    msg = str(exc_info.value)
    assert "encoder" not in msg  # the one we did pass
    assert "qdrant_client" in msg
    assert "reranker" in msg
    assert "session_maker" in msg


def test_factory_uses_cached_settings_when_omitted() -> None:
    """Calling without ``settings`` must not crash — the factory
    falls back to ``get_settings()`` (which is cached)."""
    service = get_rag_service()
    # The cached default in tests is whatever .env / Settings()
    # produces. We don't assert on the type — just on the contract.
    assert hasattr(service, "query")
