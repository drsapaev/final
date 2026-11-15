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

Also covers the related broken trusted-device service calls and SMS/email
code lifecycle/transport findings recorded in PR #4066. Trusted devices are
user-scoped and expire; SMS/email codes are keyed, single-use, and sent only
to configured recovery contacts. TOTP login remains unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


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
        """Body contract reaches the service and returns a wrong-code 400."""
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

    def test_trust_is_user_scoped_and_persisted_with_expiry(
        self, admin_user, db_session
    ):
        from app.models.two_factor_auth import TwoFactorDevice
        from app.services.two_factor_service import TwoFactorService

        device = TwoFactorDevice(
            user_id=admin_user.id,
            device_name="Test device",
            device_type="desktop",
            device_fingerprint="a" * 64,
            trusted=False,
            active=True,
        )
        db_session.add(device)
        db_session.commit()
        service = TwoFactorService()

        assert not service.trust_device(
            db_session,
            user_id=admin_user.id + 1000,
            device_id=device.id,
            trust_until=datetime.now(UTC) + timedelta(days=1),
        )
        assert service.trust_device(
            db_session,
            user_id=admin_user.id,
            device_id=device.id,
            trust_until=datetime.now(UTC) + timedelta(days=10),
        )
        assert device.trusted is True
        assert device.trusted_until is not None
        trusted_until = device.trusted_until
        if trusted_until.tzinfo is None:
            trusted_until = trusted_until.replace(tzinfo=UTC)
        assert trusted_until <= datetime.now(UTC) + timedelta(days=10)
        assert not service.trust_device(
            db_session,
            user_id=admin_user.id,
            device_id=device.id,
            trust_until=datetime.now(UTC) + timedelta(days=31),
        )


class TestTwoFactorVerificationCodeLifecycle:
    def test_code_is_keyed_single_use_and_limited_to_five_attempts(
        self, admin_user, db_session
    ):
        from app.models.two_factor_auth import (
            TwoFactorAuth,
            TwoFactorVerificationCode,
        )
        from app.services.two_factor_service import TwoFactorService

        two_factor_auth = (
            db_session.query(TwoFactorAuth)
            .filter(TwoFactorAuth.user_id == admin_user.id)
            .first()
        )
        if not two_factor_auth:
            two_factor_auth = TwoFactorAuth(user_id=admin_user.id)
            db_session.add(two_factor_auth)
        two_factor_auth.recovery_email = "user@example.test"
        two_factor_auth.recovery_enabled = True
        db_session.commit()

        service = TwoFactorService()
        service.save_verification_code(
            db_session,
            user_id=admin_user.id,
            method="email",
            code="123456",
            contact="user@example.test",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        record = (
            db_session.query(TwoFactorVerificationCode)
            .filter_by(user_id=admin_user.id, method="email")
            .one()
        )
        assert record.code_hash != "123456"
        assert record.contact_hash != "user@example.test"
        assert not service.can_send_code(db_session, admin_user.id, "email")

        record.created_at = datetime.now(UTC) - timedelta(seconds=61)
        db_session.commit()
        assert service.can_send_code(db_session, admin_user.id, "email")

        for _ in range(5):
            assert not service.verify_code(db_session, admin_user.id, "email", "000000")
        assert record.attempts_remaining == 0
        assert not service.verify_code(db_session, admin_user.id, "email", "123456")

        service.save_verification_code(
            db_session,
            user_id=admin_user.id,
            method="email",
            code="654321",
            contact="user@example.test",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        assert service.verify_code(db_session, admin_user.id, "email", "654321")
        assert not service.verify_code(db_session, admin_user.id, "email", "654321")

    def test_contact_change_invalidates_previously_sent_code(
        self, admin_user, db_session
    ):
        from app.models.two_factor_auth import TwoFactorAuth
        from app.services.two_factor_service import TwoFactorService

        two_factor_auth = (
            db_session.query(TwoFactorAuth)
            .filter(TwoFactorAuth.user_id == admin_user.id)
            .first()
        )
        if not two_factor_auth:
            two_factor_auth = TwoFactorAuth(user_id=admin_user.id)
            db_session.add(two_factor_auth)
        two_factor_auth.recovery_email = "old@example.test"
        two_factor_auth.recovery_enabled = True
        db_session.commit()
        service = TwoFactorService()
        service.save_verification_code(
            db_session,
            user_id=admin_user.id,
            method="email",
            code="123456",
            contact="old@example.test",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

        two_factor_auth.recovery_email = "new@example.test"
        db_session.commit()
        assert not service.verify_code(db_session, admin_user.id, "email", "123456")


class TestTwoFactorSmsEmailContracts:
    def test_valid_body_code_returns_verification_without_session_token(
        self, client, auth_headers, admin_user, monkeypatch
    ):
        from app.api.v1.endpoints import two_factor_sms_email as sms_module

        class _StubService:
            def verify_code(self, db, user_id, method, code):
                return True

        monkeypatch.setattr(
            sms_module, "get_two_factor_service", lambda: _StubService()
        )
        response = client.post(
            "/api/v1/2fa/verify-code",
            json={"method": "sms", "code": "123456"},
            headers=auth_headers,
        )

        assert response.status_code == 200, response.text
        assert response.json()["verified"] is True
        assert "session_token" not in response.json()

    def test_send_uses_only_configured_contact_and_body_contract(
        self, client, auth_headers, admin_user, monkeypatch
    ):
        from app.api.v1.endpoints import two_factor_sms_email as sms_module

        class _StubService:
            saved: list[dict[str, object]] = []

            def get_recovery_contact(self, db, user_id, method):
                assert user_id == admin_user.id
                assert method == "sms"
                return "+998901234567"

            def can_send_code(self, db, user_id, method):
                return True

            async def send_verification_code(self, **kwargs):
                assert kwargs["contact"] == "+998901234567"
                return {"success": True, "code": "123456"}

            def save_verification_code(self, **kwargs):
                self.saved.append(kwargs)

        service = _StubService()
        monkeypatch.setattr(sms_module, "get_two_factor_service", lambda: service)
        response = client.post(
            "/api/v1/2fa/send-code",
            json={"method": "sms"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["destination"] == "••••4567"
        assert "+998901234567" not in response.text
        assert service.saved[0]["code"] == "123456"

        arbitrary_contact = client.post(
            "/api/v1/2fa/send-code",
            json={"method": "sms", "phone_number": "+998901234567"},
            headers=auth_headers,
        )
        assert arbitrary_contact.status_code == 422, arbitrary_contact.text

    def test_unknown_device_trust_is_not_a_dead_endpoint(
        self, client, auth_headers, admin_user
    ):
        response = client.post("/api/v1/2fa/devices/999/trust", headers=auth_headers)
        assert response.status_code == 404, response.text

    def test_device_registration_is_owner_scoped_and_time_limited(
        self, client, auth_headers, admin_user, db_session
    ):
        from app.models.two_factor_auth import TwoFactorDevice

        response = client.post(
            "/api/v1/2fa/devices",
            json={
                "name": "Test device",
                "device_fingerprint": "b" * 64,
                "user_agent": "Mozilla/5.0 desktop test",
                "ip_address": "192.0.2.1",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["id"]

        device = (
            db_session.query(TwoFactorDevice)
            .filter_by(device_fingerprint="b" * 64)
            .one()
        )
        assert device.user_id == admin_user.id
        assert device.trusted is True
        assert device.trusted_until is not None
