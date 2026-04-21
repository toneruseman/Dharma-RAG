"""Tests for the /health endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.app import create_app


def test_health_returns_200_and_expected_payload() -> None:
    """Health endpoint should return 200 with a well-formed status payload."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "ok"
    assert payload["service"] == "dharma-rag"
    assert isinstance(payload["version"], str) and payload["version"]
    assert payload["environment"] in {"development", "staging", "production"}
    assert "timestamp" in payload and "T" in payload["timestamp"]


def test_health_does_not_require_downstream_services() -> None:
    """Health must be cheap — no Qdrant or LLM calls.

    We ensure this by simply calling it without any services running.
    If somebody adds a deep check later, this test will fail if there is
    no test-time stub and network is unavailable.
    """
    app = create_app()
    client = TestClient(app)

    # Call twice in quick succession — both must succeed without external I/O.
    r1 = client.get("/health")
    r2 = client.get("/health")

    assert r1.status_code == 200
    assert r2.status_code == 200
