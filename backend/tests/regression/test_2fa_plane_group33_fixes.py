"""Fail-first regression tests for audit group-33 2FA-plane findings.

Covers (remediation registry, issue #4063):
- TWOFACTOR-BE-003: DELETE /2fa/devices/{device_id} called
  ``two_factor_device.get(device_id)`` without the ``db`` session —
  TypeError on every call, converted to a generic 500 by the blanket
  handler, so single-device untrust was permanently broken.
- TWOFACTOR-BE-004: ``POST /2fa/verify-code`` read the 6-digit code and the
  destination contact from URL Query parameters (the half-applied
  AUTH-REAUDIT-28 remediation — the same file pins totp_code-in-body two
  endpoints over). Codes live in intermediary/server logs for their full
  300-second validity.
- TWOFACTOR-BE-005 (partial): ``POST /2fa/devices/{device_id}/trust`` accepted
  an unbounded client-chosen ``trust_duration_days`` Query value (365000
  accepted = a 1000-year trust grant, 2FA-exempting).

Out of scope here (separate waves, documented on #4063): TWOFACTOR-BE-001
(service-side attempt cap needs a schema change), TWOFACTOR-BE-002
(backup-code step-up needs a coordinated FE change), and the newly documented
dead-endpoint fact that POST /2fa/devices (add) and POST /2fa/devices/{id}/trust
call TwoFactorService methods that do not exist (AttributeError -> 500).
"""

from __future__ import annotations


class TestTwoFactorBE003DeviceGetMissingDb:
    def test_delete_device_no_longer_500s(
        self, client, auth_headers, admin_user, db_session
    ):
        """RED: blanket 500 (TypeError inside). GREEN: 404 for unknown id."""
        response = client.delete("/api/v1/2fa/devices/999", headers=auth_headers)

        assert response.status_code == 404, response.text
        assert response.json()["detail"] == "Device not found"


class TestTwoFactorBE004VerifyCodeBodyContract:
    def test_code_in_query_is_rejected(self, client, auth_headers, admin_user):
        """RED: query-transported code accepted (reached the service layer).
        GREEN: FastAPI 422 — body is now the only contract."""
        response = client.post(
            "/api/v1/2fa/verify-code",
            params={"method": "sms", "code": "123456"},
            headers=auth_headers,
        )

        assert response.status_code == 422, response.text

    def test_code_in_body_passes_validation_reaches_service(
        self, client, auth_headers, admin_user, monkeypatch
    ):
        """Body contract accepted: wrong code reaches the service check and
        gets the wrong-code 400 (not a schema 422). The service is stubbed —
        TwoFactorService.verify_code does not exist on main (dead endpoint,
        documented separately), and this test pins the transport contract."""
        from app.api.v1.endpoints import two_factor_sms_email as sms_module

        class _StubService:
            def verify_code(self, db, user_id, method, code):
                return False

        monkeypatch.setattr(
            sms_module, "get_two_factor_service", lambda: _StubService()
        )

        response = client.post(
            "/api/v1/2fa/verify-code",
            json={"method": "sms", "code": "123456"},
            headers=auth_headers,
        )

        assert response.status_code != 422, response.text
        assert response.status_code == 400
        assert "Неверный" in response.json()["detail"]


class TestTwoFactorBE005TrustDurationCap:
    def test_trust_duration_over_30_days_is_rejected(
        self, client, auth_headers, admin_user
    ):
        """RED: unbounded duration reached the (dead) service call (500).
        GREEN: 422 validation before any state change."""
        response = client.post(
            "/api/v1/2fa/devices/dev-1/trust",
            params={"trust_duration_days": 365000},
            headers=auth_headers,
        )

        assert response.status_code == 422, response.text
