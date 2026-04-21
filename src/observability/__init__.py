"""OpenTelemetry + OpenInference wiring for Dharma-RAG.

Public surface is the ``setup_tracing`` function. Call it once on app
start (FastAPI lifespan or CLI entry) and every subsequent span —
HTTP handler, SQL query, LLM call — is recorded by Phoenix.
"""

from __future__ import annotations

from src.observability.tracing import (
    SERVICE_NAME,
    get_tracer,
    setup_tracing,
    shutdown_tracing,
)

__all__ = [
    "SERVICE_NAME",
    "get_tracer",
    "setup_tracing",
    "shutdown_tracing",
]
