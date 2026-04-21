"""FastAPI application entry point for Dharma RAG.

Exposes the `app` object referenced by `src.cli.cmd_serve` and by the
`uvicorn` command line. Only the liveness endpoint is implemented at
this stage (Day 1); retrieval and generation endpoints are added in
later phases.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from pydantic import BaseModel

from src import __version__
from src.config import get_settings
from src.logging_config import get_logger, setup_logging


class HealthResponse(BaseModel):
    """Schema for the /health endpoint."""

    status: str
    service: str
    version: str
    environment: str
    timestamp: str


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    We use a factory so tests can create isolated app instances and so
    the CLI and uvicorn both get a fully configured logger before the
    first request.
    """
    setup_logging()
    settings = get_settings()
    log = get_logger("api")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        log.info(
            "api.startup",
            version=__version__,
            env=settings.app_env.value,
            host=settings.app_host,
            port=settings.app_port,
        )
        yield
        log.info("api.shutdown")

    app = FastAPI(
        title="Dharma RAG",
        description=(
            "Open, citation-first RAG system for Buddhist teachings. "
            "Phase 1 MVP: health endpoint only."
        ),
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["system"],
        summary="Liveness probe",
    )
    async def health() -> HealthResponse:
        """Return a static OK payload.

        This endpoint deliberately does NOT check downstream services so
        it can be used by orchestrators as a cheap liveness signal. A
        deeper readiness probe will be added in a later phase.
        """
        return HealthResponse(
            status="ok",
            service="dharma-rag",
            version=__version__,
            environment=settings.app_env.value,
            timestamp=datetime.now(UTC).isoformat(),
        )

    return app


# The module-level `app` is what uvicorn and src.cli.cmd_serve import.
app = create_app()
