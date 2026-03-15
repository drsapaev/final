from __future__ import annotations

import pytest

from app.api.v1.endpoints import phone_verification as phone_verification_endpoints


class _FakePhoneVerificationService:
    def __init__(self, expected_user_id: int):
        self.expected_user_id = expected_user_id
        self.sent_calls: list[dict[str, object]] = []

    async def send_verification_code(
        self,
        phone: str,
        purpose: str = "verification",
        provider_type=None,
        custom_message: str | None = None,
    ):
        provider = getattr(provider_type, "value", None)
        self.sent_calls.append(
            {
                "phone": phone,
                "purpose": purpose,
                "provider": provider,
                "custom_message": custom_message,
            }
        )
        return {
            "success": True,
            "message": "Код верификации отправлен",
            "expires_in_minutes": 5,
            "provider": provider,
        }

    def verify_code(
        self,
        phone: str,
        code: str,
        purpose: str = "verification",
    ):
        assert phone == "+998901234567"
        assert code == "123456"
        assert purpose == "verification"
        return {
            "success": True,
            "message": "Номер телефона успешно подтвержден",
            "phone": phone,
            "verified_at": "2026-03-13T12:00:00",
        }

    def get_verification_status(
        self,
        phone: str,
        purpose: str = "verification",
    ):
        assert phone == "+998901234567"
        assert purpose == "verification"
        return {
            "exists": True,
            "verified": False,
            "phone": phone,
            "purpose": purpose,
            "created_at": "2026-03-13T11:55:00",
            "expires_at": "2026-03-13T12:00:00",
            "attempts": 1,
            "max_attempts": 3,
            "time_left_minutes": 4,
        }

    def cancel_verification(
        self,
        phone: str,
        purpose: str = "verification",
    ):
        assert phone == "+998901234567"
        assert purpose == "verification"
        return True

    async def verify_and_update_user_phone(
        self,
        *,
        db,
        user_id: int,
        phone: str,
        code: str,
        purpose: str = "phone_change",
    ):
        assert user_id == self.expected_user_id
        assert phone == "+998901234568"
        assert code == "654321"
        assert purpose == "phone_change"
        return {
            "success": True,
            "message": "Номер телефона успешно обновлен и подтвержден",
            "phone": phone,
            "verified_at": "2026-03-13T12:05:00",
        }

    def get_statistics(self):
        return {
            "total_active_codes": 4,
            "verified_codes": 1,
            "pending_codes": 3,
            "expiring_soon": 1,
            "by_purpose": {"verification": 2, "registration": 2},
            "by_provider": {"mock": 4},
            "settings": {
                "code_length": 6,
                "ttl_minutes": 5,
                "max_attempts": 3,
                "rate_limit_minutes": 1,
            },
        }


@pytest.mark.integration
def test_phone_verification_endpoints_preserve_user_contract(
    client,
    auth_headers,
    admin_user,
    monkeypatch,
):
    fake_service = _FakePhoneVerificationService(expected_user_id=admin_user.id)
    monkeypatch.setattr(
        phone_verification_endpoints,
        "get_phone_verification_service",
        lambda: fake_service,
    )

    send_response = client.post(
        "/api/v1/phone-verification/send-code",
        headers=auth_headers,
        json={"phone": "+998901234567", "purpose": "verification"},
    )
    assert send_response.status_code == 200
    assert send_response.json() == {
        "success": True,
        "message": "Код верификации отправлен",
        "expires_in_minutes": 5,
        "provider": None,
    }

    verify_response = client.post(
        "/api/v1/phone-verification/verify-code",
        headers=auth_headers,
        json={
            "phone": "+998901234567",
            "code": "123456",
            "purpose": "verification",
        },
    )
    assert verify_response.status_code == 200
    assert verify_response.json() == {
        "success": True,
        "message": "Номер телефона успешно подтвержден",
        "phone": "+998901234567",
        "verified_at": "2026-03-13T12:00:00",
    }

    status_response = client.get(
        "/api/v1/phone-verification/status",
        headers=auth_headers,
        params={"phone": "+998901234567", "purpose": "verification"},
    )
    assert status_response.status_code == 200
    assert status_response.json() == {
        "exists": True,
        "verified": False,
        "phone": "+998901234567",
        "purpose": "verification",
        "created_at": "2026-03-13T11:55:00",
        "expires_at": "2026-03-13T12:00:00",
        "attempts": 1,
        "max_attempts": 3,
        "time_left_minutes": 4,
    }

    cancel_response = client.delete(
        "/api/v1/phone-verification/cancel",
        headers=auth_headers,
        params={"phone": "+998901234567", "purpose": "verification"},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json() == {
        "success": True,
        "message": "Верификация отменена",
    }

    update_response = client.put(
        "/api/v1/phone-verification/update-phone",
        headers=auth_headers,
        json={
            "new_phone": "+998901234568",
            "verification_code": "654321",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json() == {
        "success": True,
        "message": "Номер телефона успешно обновлен и подтвержден",
        "phone": "+998901234568",
        "verified_at": "2026-03-13T12:05:00",
    }


@pytest.mark.integration
def test_phone_verification_admin_endpoints_preserve_rbac_contract(
    client,
    auth_headers,
    cardio_auth_headers,
    admin_user,
    monkeypatch,
):
    fake_service = _FakePhoneVerificationService(expected_user_id=admin_user.id)
    monkeypatch.setattr(
        phone_verification_endpoints,
        "get_phone_verification_service",
        lambda: fake_service,
    )

    admin_statistics = client.get(
        "/api/v1/phone-verification/statistics",
        headers=auth_headers,
    )
    assert admin_statistics.status_code == 200
    statistics_payload = admin_statistics.json()
    assert statistics_payload["statistics"] == {
        "total_active_codes": 4,
        "verified_codes": 1,
        "pending_codes": 3,
        "expiring_soon": 1,
        "by_purpose": {"verification": 2, "registration": 2},
        "by_provider": {"mock": 4},
        "settings": {
            "code_length": 6,
            "ttl_minutes": 5,
            "max_attempts": 3,
            "rate_limit_minutes": 1,
        },
    }
    assert "timestamp" in statistics_payload

    forbidden_statistics = client.get(
        "/api/v1/phone-verification/statistics",
        headers=cardio_auth_headers,
    )
    assert forbidden_statistics.status_code == 403

    admin_send = client.post(
        "/api/v1/phone-verification/admin/send-code",
        headers=auth_headers,
        params={
            "phone": "+998901234567",
            "purpose": "registration",
            "provider": "mock",
            "message": "Ваш код: {code}",
        },
    )
    assert admin_send.status_code == 200
    assert admin_send.json() == {
        "success": True,
        "message": "Код верификации отправлен",
        "phone": "+998901234567",
        "purpose": "registration",
        "expires_in_minutes": 5,
        "provider": "mock",
        "sent_by_admin": admin_user.username,
    }

    assert fake_service.sent_calls[-1] == {
        "phone": "+998901234567",
        "purpose": "registration",
        "provider": "mock",
        "custom_message": "Ваш код: {code}",
    }

    forbidden_admin_send = client.post(
        "/api/v1/phone-verification/admin/send-code",
        headers=cardio_auth_headers,
        params={"phone": "+998901234567", "purpose": "registration"},
    )
    assert forbidden_admin_send.status_code == 403
