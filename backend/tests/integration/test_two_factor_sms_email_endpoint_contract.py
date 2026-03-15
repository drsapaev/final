from __future__ import annotations

from datetime import datetime

import pytest

from app.api.v1.endpoints import (
    two_factor_sms_email as two_factor_sms_email_endpoints,
)


class _FakeTwoFactorSmsEmailService:
    def __init__(self, expected_user_id: int, expected_username: str):
        self.expected_user_id = expected_user_id
        self.expected_username = expected_username
        self.saved_codes: list[dict[str, object]] = []

    async def send_verification_code(
        self,
        *,
        method: str,
        contact: str,
        user_name: str,
        provider_type=None,
    ):
        assert method == "sms"
        assert contact == "+998901234567"
        assert user_name == self.expected_username
        assert provider_type is None
        return {"success": True}

    def verify_code(
        self,
        *,
        db,
        user_id: int,
        method: str,
        code: str,
    ) -> bool:
        assert user_id == self.expected_user_id
        assert method == "sms"
        assert code == "123456"
        return True

    def create_session_token(
        self,
        *,
        db,
        user_id: int,
        method: str,
    ) -> str:
        assert user_id == self.expected_user_id
        assert method == "sms"
        return "session-token-123"

    def get_verification_status(
        self,
        *,
        db,
        user_id: int,
        method: str,
    ):
        assert user_id == self.expected_user_id
        assert method == "sms"
        return {
            "method": "sms",
            "verified": False,
            "expires_at": "2026-03-13T12:05:00",
            "can_resend": True,
        }

    def can_resend_code(
        self,
        *,
        db,
        user_id: int,
        method: str,
    ) -> bool:
        assert user_id == self.expected_user_id
        assert method == "sms"
        return True

    def save_verification_code(
        self,
        *,
        db,
        user_id: int,
        method: str,
        code: str,
        expires_at: datetime,
    ) -> None:
        assert user_id == self.expected_user_id
        assert method == "sms"
        assert isinstance(expires_at, datetime)
        self.saved_codes.append(
            {
                "user_id": user_id,
                "method": method,
                "code": code,
            }
        )

    def get_security_logs(
        self,
        *,
        db,
        user_id: int,
        limit: int,
        offset: int,
    ):
        assert user_id == self.expected_user_id
        assert limit == 10
        assert offset == 5
        return [
            {
                "type": "success",
                "action": "send_code",
                "description": "SMS code sent",
                "timestamp": "2026-03-13T12:00:00",
                "ip_address": "127.0.0.1",
                "user_agent": "pytest",
            }
        ]

    def get_recovery_methods(self, *, db, user_id: int):
        assert user_id == self.expected_user_id
        return [
            {
                "type": "email",
                "label": "Work Email",
                "value": "ad***@example.com",
                "verified": True,
            }
        ]


@pytest.mark.integration
def test_two_factor_sms_email_endpoints_preserve_live_contract(
    client,
    auth_headers,
    admin_user,
    monkeypatch,
):
    fake_service = _FakeTwoFactorSmsEmailService(
        expected_user_id=admin_user.id,
        expected_username=admin_user.username,
    )
    monkeypatch.setattr(
        two_factor_sms_email_endpoints,
        "get_two_factor_service",
        lambda: fake_service,
    )

    send_response = client.post(
        "/api/v1/2fa/send-code",
        headers=auth_headers,
        params={"method": "sms", "phone_number": "+998901234567"},
    )
    assert send_response.status_code == 200
    assert send_response.json() == {
        "success": True,
        "message": "Код отправлен на +998901234567",
        "method": "sms",
        "expires_in": 300,
    }

    verify_response = client.post(
        "/api/v1/2fa/verify-code",
        headers=auth_headers,
        params={
            "method": "sms",
            "code": "123456",
            "phone_number": "+998901234567",
        },
    )
    assert verify_response.status_code == 200
    assert verify_response.json() == {
        "success": True,
        "message": "Код подтвержден успешно",
        "session_token": "session-token-123",
        "method": "sms",
    }

    status_response = client.get(
        "/api/v1/2fa/verification-status",
        headers=auth_headers,
        params={"method": "sms"},
    )
    assert status_response.status_code == 200
    assert status_response.json() == {
        "method": "sms",
        "verified": False,
        "expires_at": "2026-03-13T12:05:00",
        "can_resend": True,
    }

    supported_response = client.get(
        "/api/v1/2fa/supported-methods",
        headers=auth_headers,
    )
    assert supported_response.status_code == 200
    assert supported_response.json() == {
        "methods": [
            {
                "id": "totp",
                "name": "Приложение-аутентификатор",
                "description": "Google Authenticator, Authy, Microsoft Authenticator",
                "icon": "smartphone",
                "recommended": True,
            },
            {
                "id": "sms",
                "name": "SMS коды",
                "description": "Коды по SMS на номер телефона",
                "icon": "phone",
                "recommended": False,
            },
            {
                "id": "email",
                "name": "Email коды",
                "description": "Коды на email адрес",
                "icon": "mail",
                "recommended": False,
            },
        ]
    }

    logs_response = client.get(
        "/api/v1/2fa/security-logs",
        headers=auth_headers,
        params={"limit": 10, "offset": 5},
    )
    assert logs_response.status_code == 200
    assert logs_response.json() == {
        "logs": [
            {
                "type": "success",
                "action": "send_code",
                "description": "SMS code sent",
                "timestamp": "2026-03-13T12:00:00",
                "ip_address": "127.0.0.1",
                "user_agent": "pytest",
            }
        ],
        "total": 1,
        "limit": 10,
        "offset": 5,
    }

    recovery_response = client.get(
        "/api/v1/2fa/recovery-methods",
        headers=auth_headers,
    )
    assert recovery_response.status_code == 200
    assert recovery_response.json() == {
        "methods": [
            {
                "type": "email",
                "label": "Work Email",
                "value": "ad***@example.com",
                "verified": True,
            }
        ]
    }


@pytest.mark.integration
def test_two_factor_sms_email_resend_code_preserves_contract(
    client,
    auth_headers,
    admin_user,
    monkeypatch,
):
    fake_service = _FakeTwoFactorSmsEmailService(
        expected_user_id=admin_user.id,
        expected_username=admin_user.username,
    )
    monkeypatch.setattr(
        two_factor_sms_email_endpoints,
        "get_two_factor_service",
        lambda: fake_service,
    )
    monkeypatch.setattr(
        two_factor_sms_email_endpoints.random,
        "choices",
        lambda population, k: list("654321"),
    )

    async def _send_sms(*, phone: str, message: str) -> bool:
        assert phone == "+998901234567"
        assert "654321" in message
        return True

    monkeypatch.setattr(
        two_factor_sms_email_endpoints.notification_service,
        "send_sms",
        _send_sms,
    )

    resend_response = client.post(
        "/api/v1/2fa/resend-code",
        headers=auth_headers,
        params={"method": "sms", "phone_number": "+998901234567"},
    )
    assert resend_response.status_code == 200
    assert resend_response.json() == {
        "success": True,
        "message": "Код повторно отправлен на +998901234567",
        "method": "sms",
        "expires_in": 300,
    }
    assert fake_service.saved_codes == [
        {
            "user_id": admin_user.id,
            "method": "sms",
            "code": "654321",
        }
    ]
