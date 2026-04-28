"""Unit tests for :mod:`src.answer.factory`."""

from __future__ import annotations

import pytest

from src.answer.factory import get_answer_service
from src.api._answer_stub import StubAnswerService
from src.config import Settings


def test_factory_returns_stub_for_stub_backend() -> None:
    settings = Settings(rag_backend="stub")
    service = get_answer_service(settings=settings)
    assert isinstance(service, StubAnswerService)


def test_factory_real_backend_requires_rag_service() -> None:
    settings = Settings(rag_backend="real", openrouter_api_key="sk-test")
    with pytest.raises(RuntimeError, match="requires a rag_service"):
        get_answer_service(settings=settings, rag_service=None)


def test_factory_real_backend_requires_openrouter_key() -> None:
    settings = Settings(rag_backend="real", openrouter_api_key="")
    rag_service = StubAnswerService()  # any object satisfying the protocol
    with pytest.raises(RuntimeError, match="OPENROUTER_API_KEY"):
        # type: ignore[arg-type] — RAGServiceProtocol vs AnswerServiceProtocol
        # is fine here; the test cares about the API-key check, not its type.
        get_answer_service(settings=settings, rag_service=rag_service)  # type: ignore[arg-type]
