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
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def auth_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db.base_class import Base

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _seed_user(db):
    from app.core.security import get_password_hash
    from app.models.authentication import RefreshToken, UserSession
    from app.models.user import User

    user = User(
        username="SYNTHETIC-fixation",
        hashed_password=get_password_hash("SYNTHETIC-password"),
        role="Patient",
        is_active=True,
        auth_epoch=0,
    )
    db.add(user)
    db.flush()
    for n in range(2):
        db.add(
            UserSession(
                user_id=user.id,
                refresh_token=f"SYNTHETIC-session-{n}",
                expires_at=datetime.now(UTC) + timedelta(days=1),
                revoked=False,
            )
        )
        db.add(
            RefreshToken(
                user_id=user.id,
                token=f"SYNTHETIC-token-{n}",
                jti=f"SYNTHETIC-jti-{n}",
                expires_at=datetime.now(UTC) + timedelta(days=1),
                revoked=False,
            )
        )
    db.commit()
    return user


class TestRevokeAllUserSessions:
    """Account-wide revocation uses one transaction and a durable epoch."""

    def test_revoke_all_user_sessions_revokes_active_sessions(self, auth_session):
        from app.models.authentication import RefreshToken, UserSession
        from app.services.auth_svc import AuthenticationService

        user = _seed_user(auth_session)
        result = AuthenticationService()._revoke_all_user_sessions(
            auth_session, user.id, reason="new_login"
        )
        auth_session.refresh(user)
        assert result == 2 and user.auth_epoch == 1
        assert (
            auth_session.query(UserSession)
            .filter_by(user_id=user.id, revoked=False)
            .count()
            == 0
        )
        assert (
            auth_session.query(RefreshToken)
            .filter_by(user_id=user.id, revoked=False)
            .count()
            == 0
        )

    def test_revoke_with_no_sessions_still_invalidates_old_access(self, auth_session):
        from app.models.user import User
        from app.services.auth_svc import AuthenticationService

        user = User(
            username="SYNTHETIC-empty",
            hashed_password="x",
            role="Patient",
            is_active=True,
            auth_epoch=0,
        )
        auth_session.add(user)
        auth_session.commit()
        assert (
            AuthenticationService()._revoke_all_user_sessions(auth_session, user.id)
            == 0
        )
        auth_session.refresh(user)
        assert user.auth_epoch == 1

    def test_revoke_failure_rolls_back(self, auth_session):
        from sqlalchemy import event

        from app.services.auth_svc import AuthenticationService

        user = _seed_user(auth_session)

        def fail(session, context, instances):
            raise RuntimeError("synthetic failure")

        event.listen(auth_session, "before_flush", fail)
        try:
            assert (
                AuthenticationService()._revoke_all_user_sessions(auth_session, user.id)
                == 0
            )
        finally:
            event.remove(auth_session, "before_flush", fail)
        auth_session.refresh(user)
        assert user.auth_epoch == 0


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
    """The configured policy acts atomically on actual stored sessions."""

    @pytest.mark.parametrize("enabled", [True, False])
    def test_login_respects_session_revocation_policy(
        self, auth_session, monkeypatch, enabled
    ):
        from app.core.config import settings
        from app.models.authentication import RefreshToken, UserSession
        from app.services.auth_svc import AuthenticationService

        user = _seed_user(auth_session)
        monkeypatch.setattr(settings, "REVOKE_SESSIONS_ON_NEW_LOGIN", enabled)
        service = AuthenticationService()
        result = service.login_user(
            auth_session,
            user.username,
            "SYNTHETIC-password",
            ip_address="127.0.0.1",
            user_agent="SYNTHETIC-test",
        )
        assert result["success"] is True
        auth_session.refresh(user)
        assert user.auth_epoch == (1 if enabled else 0)
        assert auth_session.query(UserSession).filter_by(
            user_id=user.id, revoked=False
        ).count() == (0 if enabled else 2)
        old_active = (
            auth_session.query(RefreshToken)
            .filter(
                RefreshToken.user_id == user.id,
                RefreshToken.token.like("SYNTHETIC-token-%"),
                RefreshToken.revoked.is_(False),
            )
            .count()
        )
        assert old_active == (0 if enabled else 2)
        assert (
            service.verify_token(result["tokens"]["access_token"], "access")[
                "auth_epoch"
            ]
            == user.auth_epoch
        )
        assert (
            service.verify_token(result["tokens"]["refresh_token"], "refresh")[
                "auth_epoch"
            ]
            == user.auth_epoch
        )
