"""HTTP serialization and OpenAPI must require the medical safety boundary."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.v1.endpoints import ai_gateway
from app.services.ai.ai_interfaces import AIResponse
from app.services.ai.medical_safety import MedicalAISafetyMeta


@pytest.fixture
def gateway_app(monkeypatch):
    app = FastAPI()
    app.include_router(ai_gateway.router, prefix="/ai/v2")
    route = next(route for route in ai_gateway.router.routes if isinstance(route, APIRoute)
                 and route.path == "/analyze-complaints")
    # Stub dependencies rather than protected data or providers. The test is
    # about the actual FastAPI response validation/serialization boundary.
    for dependency in route.dependant.dependencies:
        app.dependency_overrides[dependency.call] = lambda: SimpleNamespace(id=1)
    gateway = SimpleNamespace(execute=AsyncMock())
    monkeypatch.setattr(ai_gateway, "get_ai_gateway", lambda: gateway)
    return app, gateway


def _payload(**updates):
    value = {
        "status": "success", "data": {"content": "SYNTHETIC suggestion"},
        "provider": "mock", "model": "synthetic", "latency_ms": 1,
        "requires_doctor_confirmation": True, "decision_boundary": "suggestion_only",
        "ai_notice": "A doctor must confirm this suggestion.",
        "ai_safety_meta": {"requires_doctor_confirmation": True},
    }
    value.update(updates)
    return value


def test_http_returns_nested_marker_and_legacy_fields(gateway_app):
    app, gateway = gateway_app
    gateway.execute.return_value = _payload()
    with TestClient(app) as client:
        response = client.post("/ai/v2/analyze-complaints", json={"complaint": "SYNTHETIC"})
    assert response.status_code == 200
    body = response.json()
    assert body["ai_safety_meta"]["requires_doctor_confirmation"] is True
    assert body["requires_doctor_confirmation"] is True
    assert body["data"]["content"] == "SYNTHETIC suggestion"


@pytest.mark.parametrize("bad", [None, {}, {"requires_doctor_confirmation": False},
                                 {"requires_doctor_confirmation": 1},
                                 {"requires_doctor_confirmation": "true"}])
def test_http_rejects_invalid_gateway_metadata_before_exposing_result(gateway_app, bad):
    app, gateway = gateway_app
    gateway.execute.return_value = _payload(ai_safety_meta=bad)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/ai/v2/analyze-complaints", json={"complaint": "SYNTHETIC"})
    assert response.status_code == 500
    assert "SYNTHETIC suggestion" not in response.text


def test_http_revalidates_model_constructed_instances(gateway_app):
    app, gateway = gateway_app
    bad_meta = MedicalAISafetyMeta.model_construct(requires_doctor_confirmation=False)
    gateway.execute.return_value = AIResponse.model_construct(**_payload(ai_safety_meta=bad_meta))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/ai/v2/analyze-complaints", json={"complaint": "SYNTHETIC"})
    assert response.status_code == 500
    assert "SYNTHETIC suggestion" not in response.text


def test_openapi_requires_nested_marker_on_each_medical_v2_response(gateway_app):
    app, _ = gateway_app
    spec = app.openapi()
    response = spec["components"]["schemas"]["AIResponse"]
    safety = spec["components"]["schemas"]["MedicalAISafetyMeta"]
    assert "ai_safety_meta" in response["required"]
    assert response["properties"]["ai_safety_meta"]["$ref"].endswith("/MedicalAISafetyMeta")
    assert "requires_doctor_confirmation" in safety["required"]
    assert safety["properties"]["requires_doctor_confirmation"]["const"] is True
    paths = [p for p, methods in spec["paths"].items() if "post" in methods
             and methods["post"].get("responses", {}).get("200", {}).get("content", {})
             .get("application/json", {}).get("schema", {}).get("$ref", "")
             .endswith("/AIResponse")]
    assert len(paths) == 10
