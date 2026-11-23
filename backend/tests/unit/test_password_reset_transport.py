"""Reset credentials stay out of URLs and observable errors for new clients."""

import os
import subprocess
import sys
from unittest.mock import Mock

import pytest

from app.core.pii_masker import mask_pii
from app.services.password_reset_service import get_password_reset_service


@pytest.mark.parametrize("transport", ["header", "legacy_query"])
def test_validation_accepts_one_token_and_disables_caching(client, monkeypatch, transport):
    svc = get_password_reset_service()
    fake = Mock(return_value={"valid": True, "expires_at": "synthetic", "time_left_minutes": 5})
    monkeypatch.setattr(svc, "validate_reset_token", fake)
    options = ({"headers": {"X-Reset-Token": "synthetic-proof"}}
               if transport == "header" else {"params": {"token": "synthetic-proof"}})
    response = client.get("/api/v1/password-reset/validate-token", **options)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["valid"] is True
    fake.assert_called_once()
    assert fake.call_args.args[1] == "synthetic-proof"


@pytest.mark.parametrize("params,headers", [
    ([], []),
    ([("token", "first"), ("token", "second")], []),
    ([("token", "first")], [("X-Reset-Token", "second")]),
    ([], [("X-Reset-Token", "first"), ("X-Reset-Token", "second")]),
    ([], [("X-Reset-Token", "")]),
])
def test_ambiguous_or_empty_token_is_rejected_without_echo(client, params, headers):
    response = client.get("/api/v1/password-reset/validate-token", params=params, headers=headers)
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert "first" not in response.text and "second" not in response.text


def test_validation_failure_does_not_expose_exception(client, monkeypatch, caplog):
    svc = get_password_reset_service()
    def fail(*args):
        raise RuntimeError("RESET_SECRET_CANARY")
    monkeypatch.setattr(svc, "_find_token_row", fail)
    response = client.get("/api/v1/password-reset/validate-token", headers={"X-Reset-Token": "synthetic"})
    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert "RESET_SECRET_CANARY" not in response.text
    assert "RESET_SECRET_CANARY" not in caplog.text


def test_weak_password_response_is_private_and_uncacheable(client, caplog):
    response = client.post("/api/v1/password-reset/confirm", json={"token": "synthetic-proof", "new_password": "SYNTH7!"})
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert "SYNTH7!" not in response.text
    assert "SYNTH7!" not in caplog.text


def test_malformed_form_does_not_disclose_password(client, caplog):
    response = client.post(
        "/api/v1/password-reset/confirm",
        data={"token": "SYNTHETIC_TOKEN", "new_password": "SYNTHETIC_PASSWORD"},
    )
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    for secret in ("SYNTHETIC_TOKEN", "SYNTHETIC_PASSWORD"):
        assert secret not in response.text
        assert secret not in caplog.text


def test_reset_header_and_body_token_are_scrubbed():
    assert mask_pii({"X-Reset-Token": "synthetic", "reset_token": "synthetic"}) == {
        "X-Reset-Token": "[REDACTED]", "reset_token": "[REDACTED]"
    }


@pytest.mark.parametrize("value", [
    'new_password=SYNTHETIC_SECRET',
    '{"new_password":"SYNTHETIC_SECRET"}',
    "PasswordResetConfirmRequest(new_password='SYNTHETIC_SECRET')",
    '{"X-Reset-Token":"SYNTHETIC_SECRET"}',
    'reset_token=SYNTHETIC_SECRET',
])
def test_raw_credentials_are_scrubbed_in_string_representations(value):
    assert "SYNTHETIC_SECRET" not in mask_pii(value)


def test_cors_preflight_allows_reset_header():
    # CORS configuration is fixed when app.main is imported. The full CI suite
    # intentionally sets CORS_DISABLE=1, so use a fresh interpreter configured
    # with the real application's CORS middleware enabled instead of relying on
    # the already-imported session app or duplicating its middleware settings.
    script = """
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
path = '/api/v1/password-reset/validate-token'
preflight = {
    'Origin': 'http://localhost:5173',
    'Access-Control-Request-Method': 'GET',
    'Access-Control-Request-Headers': 'x-reset-token',
}
response = client.options(path, headers=preflight)
assert response.status_code == 200, response.text
assert 'x-reset-token' in response.headers['access-control-allow-headers'].lower()
assert response.headers['access-control-allow-origin'] == preflight['Origin']
assert response.headers['cache-control'] == 'no-store'

denied = client.options(path, headers={**preflight, 'Origin': 'https://not-allowed.example'})
assert denied.status_code == 400
assert 'access-control-allow-origin' not in denied.headers
assert denied.headers['cache-control'] == 'no-store'
"""
    env = {
        **os.environ,
        "CORS_DISABLE": "0",
        "CORS_ALLOW_ALL": "0",
        "BACKEND_CORS_ORIGINS": '["http://localhost:5173"]',
        "API_V1_STR": "/api/v1",
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
