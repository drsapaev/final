from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.config import settings
from app.middleware.tenant_scope_middleware import TenantScopeMiddleware


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.post("/api/v1/billing/invoices")
    async def create_invoice(request: Request):
        branch_id = getattr(request.state, "branch_id", None)
        return {"ok": True, "branch_id": branch_id}

    @app.get("/api/v1/billing/invoices")
    async def get_invoices():
        return {"ok": True}

    @app.post("/api/v1/other/write")
    async def other_write():
        return {"ok": True}

    app.add_middleware(TenantScopeMiddleware)
    return app


def test_middleware_skips_when_feature_flag_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "TENANT_SCOPE_ENFORCE_WRITES", False)
    monkeypatch.setattr(settings, "TENANT_SCOPE_WRITE_PREFIXES", "/api/v1/billing,/api/v1/queue,/api/v1/emr,/api/v1/v2/emr")
    client = TestClient(_build_app())

    response = client.post("/api/v1/billing/invoices")

    assert response.status_code == 200
    assert response.json()["branch_id"] is None


def test_middleware_rejects_protected_write_without_scope(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "TENANT_SCOPE_ENFORCE_WRITES", True)
    monkeypatch.setattr(settings, "TENANT_SCOPE_WRITE_PREFIXES", "/api/v1/billing,/api/v1/queue,/api/v1/emr,/api/v1/v2/emr")
    client = TestClient(_build_app())

    response = client.post("/api/v1/billing/invoices")

    assert response.status_code == 400
    assert "Branch scope is required" in response.json()["detail"]


def test_middleware_accepts_header_branch_scope(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "TENANT_SCOPE_ENFORCE_WRITES", True)
    monkeypatch.setattr(settings, "TENANT_SCOPE_WRITE_PREFIXES", "/api/v1/billing,/api/v1/queue,/api/v1/emr,/api/v1/v2/emr")
    client = TestClient(_build_app())

    response = client.post(
        "/api/v1/billing/invoices",
        headers={"X-Branch-ID": "15"},
    )

    assert response.status_code == 200
    assert response.json()["branch_id"] == 15


def test_middleware_accepts_query_branch_scope(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "TENANT_SCOPE_ENFORCE_WRITES", True)
    monkeypatch.setattr(settings, "TENANT_SCOPE_WRITE_PREFIXES", "/api/v1/billing,/api/v1/queue,/api/v1/emr,/api/v1/v2/emr")
    client = TestClient(_build_app())

    response = client.post("/api/v1/billing/invoices?branch_id=22")

    assert response.status_code == 200
    assert response.json()["branch_id"] == 22


def test_middleware_rejects_invalid_query_branch_scope(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "TENANT_SCOPE_ENFORCE_WRITES", True)
    monkeypatch.setattr(settings, "TENANT_SCOPE_WRITE_PREFIXES", "/api/v1/billing,/api/v1/queue,/api/v1/emr,/api/v1/v2/emr")
    client = TestClient(_build_app())

    response = client.post("/api/v1/billing/invoices?branch_id=abc")

    assert response.status_code == 400
    assert "Query branch_id must be a positive integer" in response.json()["detail"]


def test_middleware_skips_non_protected_write_even_when_enabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "TENANT_SCOPE_ENFORCE_WRITES", True)
    monkeypatch.setattr(settings, "TENANT_SCOPE_WRITE_PREFIXES", "/api/v1/billing,/api/v1/queue,/api/v1/emr,/api/v1/v2/emr")
    client = TestClient(_build_app())

    response = client.post("/api/v1/other/write")

    assert response.status_code == 200
