from __future__ import annotations

import pytest

from app.api.v1.endpoints import password_reset as password_reset_endpoints


class _FakePasswordResetService:
    async def initiate_phone_reset(self, *, db, phone: str):
        assert phone == "+998901234567"
        return {
            "success": True,
            "message": "phone reset initiated",
            "expires_in_minutes": 5,
        }

    async def initiate_email_reset(self, *, db, email: str | None):
        assert email == "reset@example.com"
        return {
            "success": True,
            "message": "email reset initiated",
            "expires_in_hours": 1,
        }

    async def verify_phone_and_get_token(
        self,
        *,
        db,
        phone: str,
        verification_code: str,
    ):
        assert phone == "+998901234567"
        assert verification_code == "123456"
        return {
            "success": True,
            "message": "phone verified",
            "reset_token": "reset-token-123",
            "expires_in_hours": 1,
        }

    def reset_password_with_token(self, *, db, token: str, new_password: str):
        assert token == "reset-token-123"
        assert new_password == "new-secret"
        return {
            "success": True,
            "message": "password changed",
        }

    def validate_reset_token(self, token: str):
        assert token == "reset-token-123"
        return {
            "valid": True,
            "expires_at": "2026-03-13T12:00:00",
            "time_left_minutes": 42,
        }

    def get_statistics(self):
        return {
            "total_tokens": 3,
            "active_tokens": 2,
            "used_tokens": 1,
            "by_method": {"phone": 1, "email": 2},
        }


@pytest.mark.integration
def test_password_reset_endpoints_preserve_frontend_recovery_contract(
    client,
    monkeypatch,
):
    fake_service = _FakePasswordResetService()
    monkeypatch.setattr(
        password_reset_endpoints,
        "get_password_reset_service",
        lambda: fake_service,
    )

    phone_initiate = client.post(
        "/api/v1/password-reset/initiate",
        json={"phone": "+998901234567"},
    )
    assert phone_initiate.status_code == 200
    assert phone_initiate.json() == {
        "success": True,
        "message": "phone reset initiated",
        "expires_in_minutes": 5,
    }

    email_initiate = client.post(
        "/api/v1/password-reset/initiate",
        json={"email": "reset@example.com"},
    )
    assert email_initiate.status_code == 200
    assert email_initiate.json() == {
        "success": True,
        "message": "email reset initiated",
        "expires_in_hours": 1,
    }

    verify_phone = client.post(
        "/api/v1/password-reset/verify-phone",
        json={"phone": "+998901234567", "verification_code": "123456"},
    )
    assert verify_phone.status_code == 200
    assert verify_phone.json() == {
        "success": True,
        "message": "phone verified",
        "reset_token": "reset-token-123",
        "expires_in_hours": 1,
    }

    confirm = client.post(
        "/api/v1/password-reset/confirm",
        json={"token": "reset-token-123", "new_password": "new-secret"},
    )
    assert confirm.status_code == 200
    assert confirm.json() == {
        "success": True,
        "message": "password changed",
    }

    validate = client.get(
        "/api/v1/password-reset/validate-token",
        params={"token": "reset-token-123"},
    )
    assert validate.status_code == 200
    assert validate.json() == {
        "valid": True,
        "expires_at": "2026-03-13T12:00:00",
        "time_left_minutes": 42,
    }


@pytest.mark.integration
def test_password_reset_statistics_endpoint_keeps_admin_contract(
    client,
    auth_headers,
    cardio_auth_headers,
    monkeypatch,
):
    fake_service = _FakePasswordResetService()
    monkeypatch.setattr(
        password_reset_endpoints,
        "get_password_reset_service",
        lambda: fake_service,
    )

    admin_response = client.get(
        "/api/v1/password-reset/statistics",
        headers=auth_headers,
    )
    assert admin_response.status_code == 200
    payload = admin_response.json()
    assert payload["statistics"] == {
        "total_tokens": 3,
        "active_tokens": 2,
        "used_tokens": 1,
        "by_method": {"phone": 1, "email": 2},
    }
    assert "timestamp" in payload

    forbidden_response = client.get(
        "/api/v1/password-reset/statistics",
        headers=cardio_auth_headers,
    )
    assert forbidden_response.status_code == 403
