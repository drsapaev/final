from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.v1.endpoints import (
    two_factor_auth as two_factor_auth_endpoints,
)
from app.api.v1.endpoints import (
    two_factor_devices as two_factor_devices_endpoints,
)


class _FakeTwoFactorDevicesService:
    def __init__(self, expected_user_id: int):
        self.expected_user_id = expected_user_id
        self.revoke_all_calls = 0

    def add_trusted_device(
        self,
        *,
        db,
        user_id: int,
        name: str | None,
        device_fingerprint: str,
        user_agent: str,
        ip_address: str,
    ):
        assert user_id == self.expected_user_id
        assert name == "Work iPad"
        assert device_fingerprint == "fingerprint-123"
        assert user_agent == "Mozilla/5.0"
        assert ip_address == "10.0.0.5"
        return {
            "id": "device-1",
            "name": name,
            "device_type": "tablet",
            "browser": "Safari",
            "os": "iPadOS",
            "location": "Tashkent",
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime(2026, 3, 13, 12, 0, 0),
            "last_used": datetime(2026, 3, 13, 12, 5, 0),
            "is_current": True,
        }

    def update_device_name(
        self,
        *,
        db,
        user_id: int,
        device_id: str,
        name: str,
    ) -> bool:
        assert user_id == self.expected_user_id
        assert device_id == "device-1"
        assert name == "Updated iPad"
        return True

    def get_device_sessions(
        self,
        *,
        db,
        user_id: int,
        device_id: str,
        limit: int,
        offset: int,
    ):
        assert user_id == self.expected_user_id
        assert device_id == "device-1"
        assert limit == 10
        assert offset == 5
        return [
            {
                "id": "session-1",
                "ip_address": "10.0.0.5",
                "user_agent": "Mozilla/5.0",
                "last_activity": "2026-03-13T12:06:00",
            }
        ]

    def get_device_statistics(self, *, db, user_id: int):
        assert user_id == self.expected_user_id
        return {
            "total_devices": 2,
            "trusted_devices": 1,
            "recent_sessions": 1,
        }

    def trust_device(
        self,
        *,
        db,
        user_id: int,
        device_id: str,
        trust_until: datetime,
    ) -> bool:
        assert user_id == self.expected_user_id
        assert device_id == "device-1"
        assert isinstance(trust_until, datetime)
        return True

    def check_device_security(
        self,
        *,
        db,
        user_id: int,
        device_id: str,
    ):
        assert user_id == self.expected_user_id
        assert device_id == "device-1"
        return {
            "device_id": device_id,
            "is_secure": True,
            "risk_level": "low",
            "issues": [],
        }

    def verify_password(self, current_user, password: str) -> bool:
        assert current_user.id == self.expected_user_id
        return password == "admin123"

    def revoke_all_devices(self, *, db, user_id: int) -> bool:
        assert user_id == self.expected_user_id
        self.revoke_all_calls += 1
        return True


@pytest.mark.integration
def test_two_factor_devices_frontend_runtime_contract_stays_on_current_owner(
    client,
    auth_headers,
    admin_user,
    monkeypatch,
):
    device_record = {
        "id": 101,
        "user_id": admin_user.id,
        "device_name": "Clinic MacBook",
        "device_type": "desktop",
        "device_fingerprint": "fingerprint-abc-123456789012345678901234",
        "trusted": True,
        "active": True,
        "created_at": datetime(2026, 3, 13, 11, 0, 0),
        "last_used": datetime(2026, 3, 13, 11, 30, 0),
        "ip_address": "10.0.0.10",
        "user_agent": "Mozilla/5.0",
    }

    monkeypatch.setattr(
        two_factor_auth_endpoints.two_factor_device,
        "get_trusted_devices",
        lambda db, user_id: [device_record],
    )
    monkeypatch.setattr(
        two_factor_auth_endpoints.two_factor_device,
        "get",
        lambda device_id: SimpleNamespace(id=device_id, user_id=admin_user.id),
    )
    monkeypatch.setattr(
        two_factor_auth_endpoints.two_factor_device,
        "untrust_device",
        lambda db, device_id: True,
    )

    list_response = client.get("/api/v1/2fa/devices", headers=auth_headers)
    assert list_response.status_code == 200
    assert list_response.json() == {
        "devices": [
            {
                "id": 101,
                "user_id": admin_user.id,
                "device_name": "Clinic MacBook",
                "device_type": "desktop",
                "device_fingerprint": "fingerprint-abc-123456789012345678901234",
                "trusted": True,
                "active": True,
                "created_at": "2026-03-13T11:00:00",
                "last_used": "2026-03-13T11:30:00",
                "ip_address": "10.0.0.10",
                "user_agent": "Mozilla/5.0",
            }
        ],
        "total": 1,
    }

    delete_response = client.delete("/api/v1/2fa/devices/101", headers=auth_headers)
    assert delete_response.status_code == 200
    assert delete_response.json() == {
        "success": True,
        "message": "Device untrusted successfully",
        "data": None,
    }


@pytest.mark.integration
def test_two_factor_devices_unique_runtime_routes_preserve_contract(
    client,
    auth_headers,
    admin_user,
    monkeypatch,
):
    fake_service = _FakeTwoFactorDevicesService(expected_user_id=admin_user.id)
    monkeypatch.setattr(
        two_factor_devices_endpoints,
        "get_two_factor_service",
        lambda: fake_service,
    )

    create_response = client.post(
        "/api/v1/2fa/devices",
        headers=auth_headers,
        json={
            "name": "Work iPad",
            "device_fingerprint": "fingerprint-123",
            "user_agent": "Mozilla/5.0",
            "ip_address": "10.0.0.5",
        },
    )
    assert create_response.status_code == 200
    assert create_response.json() == {
        "id": "device-1",
        "name": "Work iPad",
        "device_type": "tablet",
        "browser": "Safari",
        "os": "iPadOS",
        "location": "Tashkent",
        "ip_address": "10.0.0.5",
        "user_agent": "Mozilla/5.0",
        "created_at": "2026-03-13T12:00:00",
        "last_used": "2026-03-13T12:05:00",
        "is_current": True,
    }

    rename_response = client.put(
        "/api/v1/2fa/devices/device-1/name",
        headers=auth_headers,
        params={"name": "Updated iPad"},
    )
    assert rename_response.status_code == 200
    assert rename_response.json() == {
        "success": True,
        "message": "Название устройства обновлено",
    }

    sessions_response = client.get(
        "/api/v1/2fa/devices/device-1/sessions",
        headers=auth_headers,
        params={"limit": 10, "offset": 5},
    )
    assert sessions_response.status_code == 200
    assert sessions_response.json() == {
        "sessions": [
            {
                "id": "session-1",
                "ip_address": "10.0.0.5",
                "user_agent": "Mozilla/5.0",
                "last_activity": "2026-03-13T12:06:00",
            }
        ],
        "total": 1,
        "limit": 10,
        "offset": 5,
    }

    statistics_response = client.get(
        "/api/v1/2fa/devices/statistics",
        headers=auth_headers,
    )
    assert statistics_response.status_code == 200
    assert statistics_response.json() == {
        "total_devices": 2,
        "trusted_devices": 1,
        "recent_sessions": 1,
    }

    trust_response = client.post(
        "/api/v1/2fa/devices/device-1/trust",
        headers=auth_headers,
        params={"trust_duration_days": 7},
    )
    assert trust_response.status_code == 200
    assert trust_response.json() == {
        "success": True,
        "message": "Устройство доверено на 7 дней",
    }

    security_response = client.get(
        "/api/v1/2fa/devices/device-1/security-check",
        headers=auth_headers,
    )
    assert security_response.status_code == 200
    assert security_response.json() == {
        "device_id": "device-1",
        "is_secure": True,
        "risk_level": "low",
        "issues": [],
    }


@pytest.mark.integration
def test_two_factor_devices_revoke_all_preserves_password_gate(
    client,
    auth_headers,
    admin_user,
    monkeypatch,
):
    fake_service = _FakeTwoFactorDevicesService(expected_user_id=admin_user.id)
    monkeypatch.setattr(
        two_factor_devices_endpoints,
        "get_two_factor_service",
        lambda: fake_service,
    )

    success_response = client.post(
        "/api/v1/2fa/devices/revoke-all",
        headers=auth_headers,
        params={"password": "admin123"},
    )
    assert success_response.status_code == 200
    assert success_response.json() == {
        "success": True,
        "message": "Доступ всех устройств отозван",
    }
    assert fake_service.revoke_all_calls == 1

    wrong_password_response = client.post(
        "/api/v1/2fa/devices/revoke-all",
        headers=auth_headers,
        params={"password": "wrong-password"},
    )
    assert wrong_password_response.status_code == 401
    assert wrong_password_response.json() == {"detail": "Неверный пароль"}
    assert fake_service.revoke_all_calls == 1
