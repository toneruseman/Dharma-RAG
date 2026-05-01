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
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src import __version__
from src.api.answer import install_router as install_answer_router
from src.api.answer import shutdown_service as shutdown_answer_service
from src.api.query import install_router as install_query_router
from src.api.query import shutdown_service as shutdown_query_service
from src.api.retrieve import install_router as install_retrieve_router
from src.api.retrieve import shutdown_resources as shutdown_retrieve_resources
from src.api.sources import install_router as install_sources_router
from src.api.sources import shutdown_service as shutdown_sources_service
from src.config import get_settings
from src.logging_config import get_logger, setup_logging
from src.observability import setup_tracing, shutdown_tracing


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
            rag_backend=settings.rag_backend,
        )
        try:
            yield
        finally:
            shutdown_answer_service()
            shutdown_sources_service()
            shutdown_query_service()
            # Only call retrieval shutdown if we actually started it.
            # In stub mode no resources were allocated.
            if settings.rag_backend == "real":
                await shutdown_retrieve_resources()
            shutdown_tracing()
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

    # CORS — Next.js dev runs on :3001, FastAPI on :8000, so the browser
    # treats them as cross-origin and blocks POSTs without explicit
    # allowance. In dev we whitelist localhost/127.0.0.1 explicitly;
    # production tightens this in app-day-07 (strict middleware stack).
    if settings.app_env.value == "development":
        cors_origins: list[str] = ["http://localhost:3001", "http://127.0.0.1:3001"]
    else:
        cors_origins = []  # filled in by app-day-07 with real prod origins

    # Tracing wiring must happen BEFORE the ASGI server starts accepting
    # requests — FastAPIInstrumentor adds middleware to the app, and
    # FastAPI/Starlette lock the middleware stack once the first request
    # is processed. Attaching from inside ``lifespan`` is too late: the
    # middleware never runs and every request is invisible to Phoenix.
    setup_tracing(fastapi_app=app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # In ``real`` mode we mount the diagnostic /api/retrieve endpoint,
    # which also owns the heavy RetrievalResources (BGE-M3, Qdrant,
    # reranker, DB pool). The /api/query router reuses those resources
    # via ``src.api.retrieve.get_resources``.
    #
    # In ``stub`` mode (default for fresh clones / frontend dev) we
    # skip the retrieval router entirely and the query router builds
    # a StubRAGService that needs no infrastructure. The /api/query
    # contract is identical, just with hardcoded fixture sources.
    if settings.rag_backend == "real":
        install_retrieve_router(app)
    install_query_router(app)
    install_sources_router(app)
    install_answer_router(app)

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
