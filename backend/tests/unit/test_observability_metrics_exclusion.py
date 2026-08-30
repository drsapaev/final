"""Health probes must not pollute SLA metrics.

Regression: a single slow cold-start /api/v1/health request in a quiet
window dragged the window p95 over threshold and stamped fatal SLA
issues into Sentry (#2775). Health paths are now excluded from
record_request.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.middleware.observability_middleware as mod
from app.middleware.observability_middleware import ObservabilityMiddleware


@pytest.fixture
def metrics_calls(monkeypatch):
    """Перехватываем глобальный observability_state модуля."""
    calls: list[str] = []
    original = mod.observability_state
    stub = object.__new__(type(original))
    type(stub).record_request = staticmethod(  # type: ignore[attr-defined]
        lambda **kwargs: calls.append(kwargs["path"])
    )
    type(stub).evaluate_sla_alerts = staticmethod(lambda: {})  # type: ignore[attr-defined]
    monkeypatch.setattr(mod, "observability_state", stub)
    return calls


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/api/v1/health")
    async def health():
        return {"ok": True}

    @app.get("/api/v1/patients")
    async def patients():
        return {"items": []}

    return app


def test_health_excluded_real_route_still_tracked(metrics_calls):
    client = TestClient(_make_app())
    client.get("/api/v1/health")
    client.get("/api/v1/patients")

    assert "/api/v1/health" not in metrics_calls
    assert "/api/v1/patients" in metrics_calls


def test_bare_health_alias_also_excluded(metrics_calls):
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/health")
    async def health():
        return {"ok": True}

    client = TestClient(app)
    client.get("/health")

    assert "/health" not in metrics_calls
