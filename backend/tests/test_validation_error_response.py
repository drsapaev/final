"""
Regression (Sentry PYTHON-FASTAPI-M breadcrumbs): validation_exception_handler
embedded raw ``exc.errors()`` in a JSONResponse. Pydantic v2 error entries can
carry non-JSON-serializable objects in ``ctx`` (the ValueError raised by a
custom field validator), so JSONResponse itself raised
"Object of type ValueError is not JSON serializable" — the client got a 500
"Internal server error" from the security-middleware catch-all instead of a
proper 422.
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, field_validator

from app.core.exception_handlers import register_exception_handlers


class ProbePayload(BaseModel):
    email: str
    code: str

    @field_validator("code")
    @classmethod
    def _code_must_be_ok(cls, v: str) -> str:
        if v != "ok":
            # Pydantic v2 keeps this ValueError object inside errors()[i]["ctx"]
            raise ValueError("code is invalid")
        return v


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/probe")
    async def probe(payload: ProbePayload) -> dict:
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


def test_validator_value_error_returns_422_with_serializable_detail(client):
    resp = client.post("/probe", json={"email": "a@b.c", "code": "bad"})
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["error"] == "validation_error"
    # The response body must be plain JSON (would raise pre-fix)
    json.dumps(body)


def test_type_mismatch_returns_422(client):
    resp = client.post("/probe", json={"email": "a@b.c", "code": {"target": {"value": "x"}}})
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["error"] == "validation_error"
    json.dumps(body)
