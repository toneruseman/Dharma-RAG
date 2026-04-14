"""Tests for src.logging_config module."""

from __future__ import annotations

import structlog

from src.logging_config import get_logger, setup_logging


def test_setup_logging_does_not_raise() -> None:
    """setup_logging() should complete without errors."""
    setup_logging()


def test_get_logger_returns_bound_logger() -> None:
    setup_logging()
    log = get_logger("test")
    # structlog.get_logger() returns a lazy proxy that wraps BoundLogger
    assert hasattr(log, "info")
    assert hasattr(log, "warning")
    assert hasattr(log, "error")
