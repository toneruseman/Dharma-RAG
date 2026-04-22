"""OpenTelemetry tracer setup for Phoenix.

What this module does
---------------------
1. Configures an OTLP-gRPC exporter pointing at the local Phoenix
   container (``localhost:4317`` by default). Phoenix accepts any
   OpenTelemetry-spec-compliant OTLP traffic, so in principle we
   could also export to Jaeger or Grafana Tempo without changing
   this module — only the endpoint URL.
2. Sets a Resource with ``service.name=dharma-rag`` and app version
   so traces are grouped under one logical service in the UI.
3. Wires the FastAPI and HTTPX OpenTelemetry instrumentations so
   every incoming HTTP request and every outgoing HTTP call is a
   span by default.
4. Exposes ``get_tracer(name)`` for modules that want to emit their
   own custom spans (retrieval, rerank, LLM generation). Pair with
   OpenInference semantic conventions when the span represents an
   AI operation — Phoenix's UI renders those specially.

Design
------
* **Idempotent setup.** Calling ``setup_tracing`` twice is safe: the
  second call is a no-op. That lets unit tests create an app and
  bring up tracing independently without cross-test pollution.
* **Soft failure.** If the Phoenix endpoint is unreachable (dev
  machine without docker compose running), tracing silently emits
  to a no-op exporter instead of crashing the request path.
  Observability is support, not a hard dependency.
* **Explicit shutdown.** ``shutdown_tracing`` flushes buffered spans
  — important at the end of short-lived CLI runs where the process
  exits before the default 30 s batch interval fires.
"""

from __future__ import annotations

import logging
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer

from src import __version__
from src.config import get_settings

logger = logging.getLogger(__name__)

SERVICE_NAME: str = "dharma-rag"

# Tracks whether setup has already run in this process. Simpler than a
# lock because setup is called from exactly one place (FastAPI lifespan);
# the flag just makes duplicate calls safe for tests.
_initialised: bool = False


def setup_tracing(
    *,
    endpoint: str | None = None,
    enabled: bool | None = None,
    fastapi_app: Any = None,
) -> TracerProvider | None:
    """Configure the global OpenTelemetry tracer provider.

    Parameters
    ----------
    endpoint:
        Override the OTLP endpoint. Defaults to ``settings.phoenix_otlp_endpoint``
        (``http://localhost:4317``). Pass ``""`` to disable tracing
        explicitly.
    enabled:
        Short-circuit the whole setup when ``False`` — used by unit
        tests that do not want a provider installed.
    fastapi_app:
        The FastAPI application instance. If provided, the FastAPI
        instrumentation is attached so every request becomes a span.
        Omit for non-HTTP entry points (scripts, CLIs).

    Returns
    -------
    The installed ``TracerProvider`` (or ``None`` when disabled /
    already initialised). Returning the provider gives callers a
    handle for ``shutdown_tracing``.
    """
    global _initialised
    if _initialised:
        return None
    if enabled is False:
        logger.info("Tracing disabled by caller.")
        _initialised = True
        return None

    settings = get_settings()
    resolved_endpoint = endpoint if endpoint is not None else settings.phoenix_otlp_endpoint
    if not resolved_endpoint:
        logger.info("Tracing endpoint empty; tracing disabled.")
        _initialised = True
        return None

    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": __version__,
            "deployment.environment": settings.app_env.value,
        }
    )
    provider = TracerProvider(resource=resource)

    try:
        exporter = OTLPSpanExporter(endpoint=resolved_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except Exception as exc:  # noqa: BLE001 — failure here must not kill app startup
        # We still install the provider so get_tracer() calls are valid
        # (they become no-ops). The user sees a warning, not a crash.
        logger.warning(
            "OTLP exporter setup failed (%s). Tracing will be a no-op. "
            "If this is unexpected, check that Phoenix is running: "
            "`docker compose up -d phoenix`.",
            exc,
        )

    trace.set_tracer_provider(provider)

    if fastapi_app is not None:
        _instrument_fastapi(fastapi_app, provider)
        _instrument_httpx(provider)

    _initialised = True
    logger.info(
        "Tracing configured: service=%s version=%s endpoint=%s",
        SERVICE_NAME,
        __version__,
        resolved_endpoint,
    )
    return provider


def shutdown_tracing() -> None:
    """Flush pending spans and release resources.

    Call this before process exit when tracing was enabled. The
    BatchSpanProcessor buffers up to ~30 s of spans by default — if
    the process dies without a flush, recent traces are lost.
    """
    global _initialised
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        current.shutdown()
    _initialised = False


def get_tracer(name: str) -> Tracer:
    """Return a Tracer for a specific module.

    Follows the OTel naming convention: pass your module's
    ``__name__`` (e.g. ``"src.api.retrieval"``) so spans are
    attributed to that code path.
    """
    return trace.get_tracer(name)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _instrument_fastapi(app: Any, provider: TracerProvider) -> None:
    """Attach OpenTelemetry's FastAPI instrumentation to ``app``.

    Kept as a helper so tests can bypass the import cost of
    ``opentelemetry.instrumentation.fastapi`` when they don't need
    HTTP tracing.
    """
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: PLC0415

    # Phase 1: instrument every route so smoke-tests can verify traces
    # flow end-to-end. Once Phoenix is known-working we'll re-enable
    # ``excluded_urls`` to keep noisy health-check probes out of the
    # dashboard (they fire every 30 s from docker-compose healthchecks).
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)


def _instrument_httpx(provider: TracerProvider) -> None:
    """Wire up automatic spans for outbound HTTP calls made with httpx."""
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor  # noqa: PLC0415

    HTTPXClientInstrumentor().instrument(tracer_provider=provider)


def _reset_for_tests() -> None:
    """Test-only helper that undoes setup so a new provider can install."""
    global _initialised
    _initialised = False
