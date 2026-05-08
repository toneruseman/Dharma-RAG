"""End-to-end check: in ``RAG_BACKEND=stub`` mode the app boots and
``POST /api/query`` works without Qdrant / Postgres / GPU.

This is the real value-prop of app-day-02 for a frontend developer:
clone the repo, run uvicorn, hit /api/query, see fixture data in <2 ms.
The test stands in for that workflow."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def force_stub_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin ``RAG_BACKEND=stub`` for these tests regardless of the
    developer's local .env, and clear the lru_cache on get_settings so
    the override actually lands."""
    monkeypatch.setenv("RAG_BACKEND", "stub")
    # Settings() is constructed fresh by create_app() and the factory,
    # not via get_settings cache, so no cache-clearing dance needed —
    # but if that changes, this fixture is the place to add it.


def test_query_endpoint_returns_fixture_response() -> None:
    """Stub-mode FastAPI must serve POST /api/query end-to-end."""
    from src.api.app import create_app

    app = create_app()
    client = TestClient(app)

    with client:
        response = client.post(
            "/api/query",
            json={"query": "what is dukkha?", "top_k": 3},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "what is dukkha?"
    assert isinstance(payload["sources"], list)
    assert len(payload["sources"]) <= 3
    assert payload["metadata"]["collection"] == "stub"
    # Latency from the API includes FastAPI overhead, but should be
    # nowhere near a real-backend query (~80 ms). Generous bound.
    assert payload["latency_ms"] < 100


def test_health_still_works_in_stub_mode() -> None:
    """Sanity check that /health doesn't break when we skip the
    retrieval router setup."""
    from src.api.app import create_app

    app = create_app()
    client = TestClient(app)

    with client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_retrieve_endpoint_absent_in_stub_mode() -> None:
    """In stub mode the diagnostic /api/retrieve endpoint isn't
    mounted — only /api/query is the public surface."""
    from src.api.app import create_app

    app = create_app()
    client = TestClient(app)

    with client:
        response = client.post("/api/retrieve", json={"query": "x"})

    # FastAPI returns 404 for unknown routes
    assert response.status_code == 404


def test_sources_endpoint_returns_fixture_document() -> None:
    """Reading Room: GET /api/sources/mn10 returns the stub document."""
    from src.api.app import create_app

    app = create_app()
    client = TestClient(app)

    with client:
        response = client.get("/api/sources/mn10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["canonical_id"] == "mn10"
    assert payload["title_pali"] == "Satipaṭṭhāna Sutta"
    assert payload["tradition_code"] == "theravada"
    assert isinstance(payload["paragraphs"], list)
    assert len(payload["paragraphs"]) >= 1
    # Document order is the contract — frontend renders sequentially.
    sequences = [p["sequence"] for p in payload["paragraphs"]]
    assert sequences == sorted(sequences)
    assert payload["translation"]["author"] == "Bhikkhu Sujato"
    assert payload["translation"]["license"] == "CC0"


def test_sources_endpoint_unknown_returns_404() -> None:
    """Unknown canonical_id maps to a clean 404 with a descriptive detail."""
    from src.api.app import create_app

    app = create_app()
    client = TestClient(app)

    with client:
        response = client.get("/api/sources/does_not_exist")

    assert response.status_code == 404
    assert "does_not_exist" in response.json()["detail"]
