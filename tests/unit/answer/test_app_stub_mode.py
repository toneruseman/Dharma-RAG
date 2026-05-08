"""End-to-end check: in ``RAG_BACKEND=stub`` mode the app boots and
``POST /api/answer`` works without OpenRouter / Qdrant / Postgres /
GPU. Frontend developer's smoke test."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def force_stub_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin ``RAG_BACKEND=stub`` regardless of the developer's local .env."""
    monkeypatch.setenv("RAG_BACKEND", "stub")


def test_answer_endpoint_returns_fixture_response() -> None:
    from src.api.app import create_app

    app = create_app()
    client = TestClient(app)

    with client:
        response = client.post(
            "/api/answer",
            json={"query": "what is mindfulness?", "top_k": 3},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "what is mindfulness?"
    # Stub answer is non-empty and references the fixture work_ids.
    assert payload["answer"]
    assert "mn10" in payload["answer"]
    assert isinstance(payload["sources"], list)
    assert len(payload["sources"]) <= 3
    assert payload["metadata"]["pipeline_version"] == "stub-v1"
    assert payload["metadata"]["llm_model"] == "stub/static"
    # Latency includes FastAPI overhead — generous bound.
    assert payload["latency_ms"] < 200


def test_answer_empty_when_all_works_forbidden() -> None:
    """Stub mirrors real behaviour: forbid everything → empty answer."""
    from src.api.app import create_app

    app = create_app()
    client = TestClient(app)

    with client:
        response = client.post(
            "/api/answer",
            json={
                "query": "x",
                "forbidden_works": ["mn10", "sn56.11", "dn22"],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == ""
    assert payload["sources"] == []
    assert payload["citations"] == []


def test_query_endpoint_still_works_in_stub_mode() -> None:
    """Sanity check that adding the answer router didn't break the
    existing /api/query endpoint."""
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
    assert payload["metadata"]["collection"] == "stub"
