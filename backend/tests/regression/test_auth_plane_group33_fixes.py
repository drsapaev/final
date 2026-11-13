"""Fail-first regression tests for audit group-33 auth-plane findings.

Covers (remediation registry, issue #4063):
- AUTH-BE-001: GET /sessions and GET /status compared a timezone-aware
  ``expires_at`` (DateTime(timezone=True) on PostgreSQL) against naive
  ``datetime.utcnow()`` — TypeError swallowed by the blanket handler and
  returned as a generic 500. The in-file logout-path docstring records the
  same class breaking revocation in production (Sentry 3E, #3122).
- AUTH-BE-002: POST /authentication/password-reset was an email-existence
  oracle (400 + "Пользователь с таким email не найден" vs 200 + expires_at).
- AUTH-BE-005: CSRF cookie ``Secure`` flag was keyed to an ad-hoc
  ``os.getenv("ENV", "dev")`` instead of the app settings.

The SQLite test DB returns naive datetimes, which is exactly why the
production break (aware column) stayed invisible locally: these tests inject
aware ``expires_at`` values through the CRUD boundary instead of relying on
the driver.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.api.v1.endpoints import authentication as auth_module


def _fake_session(expires_at: datetime) -> SimpleNamespace:
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=101,
        user_id=1,
        created_at=now - timedelta(hours=1),
        expires_at=expires_at,
        revoked=False,
        revoked_at=None,
        ip="127.0.0.1",
        user_agent="pytest",
    )


class TestAuthBE001TimezoneAwareExpiry:
    def test_sessions_list_survives_timezone_aware_expiry(
        self, client, auth_headers, admin_user, db_session, monkeypatch
    ):
        aware = datetime.now(UTC) + timedelta(days=1)
        monkeypatch.setattr(
            auth_module.user_session,
            "get_by_user_id",
            lambda db, user_id: [_fake_session(aware)],
        )

        response = client.get("/api/v1/authentication/sessions", headers=auth_headers)

        assert response.status_code == 200, response.text
        sessions = response.json()["sessions"]
        assert sessions, "stubbed session row must be returned"
        assert sessions[0]["is_active"] is True
        assert sessions[0]["revoked"] is False

    def test_status_survives_timezone_aware_expiry(
        self, client, auth_headers, admin_user, db_session, monkeypatch
    ):
        aware = datetime.now(UTC) + timedelta(days=1)
        monkeypatch.setattr(
            auth_module.user_session,
            "get_active_sessions",
            lambda db, user_id: [_fake_session(aware)],
        )

        response = client.get("/api/v1/authentication/status", headers=auth_headers)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["authenticated"] is True
        assert body["session"]["is_active"] is True

    def test_expired_aware_session_is_reported_inactive(
        self, client, auth_headers, admin_user, db_session, monkeypatch
    ):
        """Negative case: an aware expiry in the past must read inactive."""
        expired_aware = datetime.now(UTC) - timedelta(days=1)
        monkeypatch.setattr(
            auth_module.user_session,
            "get_by_user_id",
            lambda db, user_id: [_fake_session(expired_aware)],
        )

        response = client.get("/api/v1/authentication/sessions", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["sessions"][0]["is_active"] is False


class TestAuthBE002PasswordResetUniformResponse:
    def test_unknown_email_gets_uniform_success_response(self, client, db_session):
        response = client.post(
            "/api/v1/authentication/password-reset",
            json={"email": "no-such-user-404@example.com"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        # No machine-readable discriminator for unknown emails.
        assert not body.get("data")

    def test_known_email_response_is_identical_in_shape(
        self, client, db_session, admin_user
    ):
        """Negative case: registered emails must not carry extra fields."""
        unknown = client.post(
            "/api/v1/authentication/password-reset",
            json={"email": "no-such-user-404@example.com"},
        )
        known = client.post(
            "/api/v1/authentication/password-reset",
            json={"email": admin_user.email},
        )

        assert known.status_code == unknown.status_code
        known_body = known.json()
        unknown_body = unknown.json()
        assert set(known_body.keys()) == set(unknown_body.keys())
        # The old success shape leaked expires_at only for known emails.
        assert not (known_body.get("data") or {}).get("expires_at")


class TestAuthBE005CsrfSecureFlag:
    def _set_cookie_headers(self, client):
        return client.get("/api/v1/auth/csrf-token").headers.get_list("set-cookie")

    def test_csrf_cookie_secure_when_settings_env_is_prod(self, client, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "ENV", "prod")
        cookies = "; ".join(self._set_cookie_headers(client)).lower()
        assert "csrf_token=" in cookies
        assert (
            "secure" in cookies
        ), "csrf cookie must carry Secure when settings.ENV declares production"

    def test_csrf_cookie_stays_insecure_in_dev(self, client, monkeypatch):
        """Regression guard: dev keeps Secure off (plain-HTTP local run)."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "ENV", "dev")
        cookies = "; ".join(self._set_cookie_headers(client)).lower()
        assert "csrf_token=" in cookies
        assert "secure" not in cookies
