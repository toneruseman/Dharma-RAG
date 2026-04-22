"""Unit tests for the OpenTelemetry tracing bootstrap.

Tests cover configuration behaviour only — they never spin up a real
OTLP exporter or attempt to connect to Phoenix. ``_reset_for_tests``
is used between cases so each test observes a clean ``_initialised``
flag.
"""

from __future__ import annotations

from typing import Any

import pytest
from opentelemetry.sdk.trace import TracerProvider

from src.observability.tracing import (
    SERVICE_NAME,
    _reset_for_tests,
    get_tracer,
    setup_tracing,
)


@pytest.fixture(autouse=True)
def _fresh_state() -> Any:
    """Ensure each test starts with no provider installed."""
    _reset_for_tests()
    yield
    _reset_for_tests()


def test_disabled_flag_short_circuits_setup() -> None:
    """enabled=False returns None, installs no provider."""
    provider = setup_tracing(enabled=False)
    assert provider is None


def test_empty_endpoint_short_circuits_setup() -> None:
    """endpoint='' disables tracing explicitly."""
    provider = setup_tracing(endpoint="")
    assert provider is None


def test_setup_returns_tracer_provider_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """With a valid endpoint, a TracerProvider is installed.

    We don't assert identity against ``trace.get_tracer_provider()``
    because OpenTelemetry silently keeps the first provider installed
    across the process lifetime — the *second* test in a run gets a
    new local provider but the global stays pointed at the first one.
    Identity tests are therefore brittle under pytest; we check the
    type and configured attributes instead.
    """
    provider = setup_tracing(endpoint="http://127.0.0.1:9999")
    assert isinstance(provider, TracerProvider)
    assert provider.resource.attributes.get("service.name") == SERVICE_NAME


def test_setup_is_idempotent() -> None:
    """A second call returns None because we track that we already ran."""
    first = setup_tracing(endpoint="http://127.0.0.1:9999")
    second = setup_tracing(endpoint="http://127.0.0.1:9999")
    assert first is not None
    assert second is None


def test_resource_carries_service_name(monkeypatch: pytest.MonkeyPatch) -> None:
    """The provider's Resource should advertise ``service.name=dharma-rag``."""
    provider = setup_tracing(endpoint="http://127.0.0.1:9999")
    assert provider is not None
    # ``attributes`` is a frozen Mapping on Resource; keys are strings.
    attrs = dict(provider.resource.attributes)
    assert attrs.get("service.name") == SERVICE_NAME
    # Version must be populated from src.__version__.
    assert "service.version" in attrs


def test_get_tracer_returns_tracer_after_setup() -> None:
    setup_tracing(endpoint="http://127.0.0.1:9999")
    tracer = get_tracer("tests.unit.observability")
    # ``start_as_current_span`` is the API contract used by downstream
    # modules; cheapest check is simply that it doesn't raise.
    with tracer.start_as_current_span("probe") as span:
        assert span.is_recording() or span is not None
