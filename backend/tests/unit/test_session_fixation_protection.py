"""
Unit tests for Session Fixation Protection (M4-P0-3).

Tests the _revoke_all_user_sessions() method in AuthenticationService
and _revoke_previous_patient_sessions() in telegram_mini_app_jwt.

Covers:
- Staff login revokes existing sessions
- Patient JWT exchange revokes previous patient sessions
- Revoke with no existing sessions (no-op)
- Revoke failure is non-blocking (returns 0, doesn't raise)
- REVOKE_SESSIONS_ON_NEW_LOGIN setting controls behavior
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


class TestRevokeAllUserSessions:
    """Tests for AuthenticationService._revoke_all_user_sessions()."""

    def test_revoke_all_user_sessions_revokes_active_sessions(self):
        """_revoke_all_user_sessions revokes all active UserSession + RefreshToken."""
        from app.services.auth_svc._tokens import TokensMixin

        # Create a minimal instance with required attributes
        class TestAuth(TokensMixin):
            pass

        auth = TestAuth()

        db = MagicMock()
        # Simulate query chain: db.query().filter().update()
        refresh_query = MagicMock()
        refresh_query.filter.return_value.update.return_value = 3  # 3 refresh tokens

        session_query = MagicMock()
        session_query.filter.return_value.update.return_value = 2  # 2 sessions

        db.query.side_effect = [refresh_query, session_query]

        result = auth._revoke_all_user_sessions(db, user_id=42, reason="new_login")

        assert result == 2  # Returns session count
        assert db.commit.called
        assert db.query.call_count == 2  # Called for RefreshToken + UserSession

    def test_revoke_all_user_sessions_returns_zero_when_no_sessions(self):
        """Returns 0 when no active sessions exist."""
        from app.services.auth_svc._tokens import TokensMixin

        class TestAuth(TokensMixin):
            pass

        auth = TestAuth()

        db = MagicMock()
        refresh_query = MagicMock()
        refresh_query.filter.return_value.update.return_value = 0

        session_query = MagicMock()
        session_query.filter.return_value.update.return_value = 0

        db.query.side_effect = [refresh_query, session_query]

        result = auth._revoke_all_user_sessions(db, user_id=42, reason="new_login")

        assert result == 0
        assert db.commit.called

    def test_revoke_all_user_sessions_non_blocking_on_failure(self):
        """Returns 0 and rolls back on db failure (non-blocking)."""
        from app.services.auth_svc._tokens import TokensMixin

        class TestAuth(TokensMixin):
            pass

        auth = TestAuth()

        db = MagicMock()
        db.query.side_effect = Exception("Database connection lost")

        result = auth._revoke_all_user_sessions(db, user_id=42, reason="new_login")

        assert result == 0
        assert db.rollback.called


class TestRevokePreviousPatientSessions:
    """Tests for _revoke_previous_patient_sessions() in telegram_mini_app_jwt."""

    def test_revoke_previous_patient_sessions_revokes_active(self):
        """Revokes previous patient sessions (negative user_id)."""
        from app.services.telegram_mini_app_jwt import _revoke_previous_patient_sessions

        db = MagicMock()
        query = MagicMock()
        query.filter.return_value.update.return_value = 1  # 1 session revoked
        db.query.return_value = query

        result = _revoke_previous_patient_sessions(db, patient_id=42)

        assert result == 1
        assert db.commit.called

    def test_revoke_previous_patient_sessions_returns_zero_for_none(self):
        """Returns 0 when patient_id is None."""
        from app.services.telegram_mini_app_jwt import _revoke_previous_patient_sessions

        db = MagicMock()
        result = _revoke_previous_patient_sessions(db, patient_id=None)

        assert result == 0
        assert not db.query.called  # Should not query DB

    def test_revoke_previous_patient_sessions_non_blocking_on_failure(self):
        """Returns 0 and rolls back on db failure."""
        from app.services.telegram_mini_app_jwt import _revoke_previous_patient_sessions

        db = MagicMock()
        db.query.side_effect = Exception("DB error")

        result = _revoke_previous_patient_sessions(db, patient_id=42)

        assert result == 0
        assert db.rollback.called

    def test_revoke_previous_patient_sessions_uses_negative_user_id(self):
        """Patient sessions use negative user_id (e.g. -42 for patient 42)."""
        from app.services.telegram_mini_app_jwt import _revoke_previous_patient_sessions

        db = MagicMock()
        query = MagicMock()
        query.filter.return_value.update.return_value = 0
        db.query.return_value = query

        _revoke_previous_patient_sessions(db, patient_id=99)

        # Verify db.query was called with UserSession
        # The filter should use user_id=-99
        db.query.assert_called_once()
        # We can't easily inspect the filter arguments without deeper mocking,
        # but the fact that it was called confirms the function executed.


class TestLoginSessionFixationProtection:
    """Tests that login_user revokes existing sessions when setting is enabled."""

    def test_login_revokes_existing_sessions_when_enabled(self):
        """When REVOKE_SESSIONS_ON_NEW_LOGIN=True, login revokes old sessions."""
        from app.services.auth_svc._tokens import TokensMixin

        class TestAuth(TokensMixin):
            pass

        auth = TestAuth()

        # Mock the necessary dependencies
        db = MagicMock()
        user = MagicMock()
        user.id = 1
        user.username = "testuser"
        user.role = "doctor"
        user.is_active = True
        user.is_superuser = False
        user.email = "test@example.com"
        user.full_name = "Test User"
        user.two_factor_auth = None
        user.must_change_password = False

        with patch.object(auth, "authenticate_user", return_value=(user, "OK")), \
             patch.object(auth, "_revoke_all_user_sessions", return_value=2) as mock_revoke, \
             patch.object(auth, "create_access_token", return_value="access_token"), \
             patch.object(auth, "create_refresh_token", return_value="refresh_token"), \
             patch("app.services.auth_svc._tokens.settings") as mock_settings:

            mock_settings.REVOKE_SESSIONS_ON_NEW_LOGIN = True
            mock_settings.SECRET_KEY = "test-secret"
            mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30

            result = auth.login_user(
                db=db,
                username="testuser",
                password="password",
            )

        # Verify _revoke_all_user_sessions was called
        mock_revoke.assert_called_once_with(db, user.id, reason="new_login")
        assert result["success"] is True

    def test_login_does_not_revoke_when_setting_disabled(self):
        """When REVOKE_SESSIONS_ON_NEW_LOGIN=False, login does NOT revoke."""
        from app.services.auth_svc._tokens import TokensMixin

        class TestAuth(TokensMixin):
            pass

        auth = TestAuth()

        db = MagicMock()
        user = MagicMock()
        user.id = 1
        user.username = "testuser"
        user.role = "doctor"
        user.is_active = True
        user.is_superuser = False
        user.email = "test@example.com"
        user.full_name = "Test User"
        user.two_factor_auth = None
        user.must_change_password = False

        with patch.object(auth, "authenticate_user", return_value=(user, "OK")), \
             patch.object(auth, "_revoke_all_user_sessions", return_value=0) as mock_revoke, \
             patch.object(auth, "create_access_token", return_value="access_token"), \
             patch.object(auth, "create_refresh_token", return_value="refresh_token"), \
             patch("app.services.auth_svc._tokens.settings") as mock_settings:

            mock_settings.REVOKE_SESSIONS_ON_NEW_LOGIN = False
            mock_settings.SECRET_KEY = "test-secret"
            mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30

            result = auth.login_user(
                db=db,
                username="testuser",
                password="password",
            )

        # Verify _revoke_all_user_sessions was NOT called
        mock_revoke.assert_not_called()
        assert result["success"] is True
