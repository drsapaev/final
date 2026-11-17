"""Reset credentials stay out of URLs and observable errors for new clients."""

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


def test_cors_preflight_allows_reset_header(client):
    response = client.options("/api/v1/password-reset/validate-token", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "x-reset-token",
    })
    assert response.status_code == 200
    assert "x-reset-token" in response.headers["access-control-allow-headers"].lower()
    assert response.headers["cache-control"] == "no-store"
