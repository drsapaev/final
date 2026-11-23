"""
Unit tests for Session Fixation Protection (M4-P0-3).

Tests staff login revocation and the independent Telegram patient sessions.

Covers:
- Staff login revokes existing sessions
- Patient exchange always issues a fresh, server-owned session id
- Prior patient devices remain independent and staff sessions stay untouched
- Revoke with no existing sessions (no-op)
- Revoke failure is non-blocking (returns 0, doesn't raise)
- REVOKE_SESSIONS_ON_NEW_LOGIN setting controls behavior
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

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


class TestPatientSessionFixationProtection:
    """Fresh patient identities never adopt or revoke unrelated sessions."""

    @pytest.fixture
    def patient_link(self, db_session, test_patient):
        from tests.unit.test_telegram_mini_app_jwt import link_patient

        return link_patient(db_session, test_patient)

    def test_new_launch_cannot_choose_or_reuse_a_session_id(
        self, db_session, patient_link
    ):
        from app.services.telegram_mini_app_jwt import exchange_init_data_for_jwt
        from tests.unit.test_telegram_mini_app_jwt import (
            BOT_TOKEN,
            create_session,
            signed_init_data,
            verified_claims,
        )

        first = create_session(db_session)
        first_claims = verified_claims(first["access_token"])
        second = exchange_init_data_for_jwt(
            db_session,
            signed_init_data(nonce=first_claims["sid"]),
            bot_token=BOT_TOKEN,
        )
        second_claims = verified_claims(second["access_token"])
        assert second_claims["sid"] != first_claims["sid"]
        assert second_claims["jti"] != first_claims["jti"]
        assert second["refresh_token"] != first["refresh_token"]

    def test_new_login_preserves_independent_existing_device(
        self, db_session, patient_link
    ):
        from app.services.telegram_mini_app_jwt import (
            list_patient_sessions,
            verify_patient_jwt,
        )
        from tests.unit.test_telegram_mini_app_jwt import create_session

        first = create_session(db_session)
        second = create_session(db_session)
        _, listed = list_patient_sessions(db_session, second["access_token"])
        assert listed["total"] == 2
        assert sum(session["is_current"] for session in listed["sessions"]) == 1
        assert verify_patient_jwt(first["access_token"], db_session)

    def test_exchange_does_not_return_credentials_when_persistence_fails(
        self, db_session, patient_link
    ):
        from app.models.telegram_mini_app_session import TelegramMiniAppSession
        from tests.unit.test_telegram_mini_app_jwt import create_session

        with patch.object(
            db_session, "commit", side_effect=RuntimeError("SYNTHETIC failure")
        ):
            with pytest.raises(RuntimeError, match="SYNTHETIC failure"):
                create_session(db_session)
        db_session.rollback()
        assert db_session.query(TelegramMiniAppSession).count() == 0

    def test_patient_login_and_revoke_never_modify_staff_sessions(
        self, db_session, patient_link, admin_user
    ):
        from app.models.authentication import UserSession
        from app.services.telegram_mini_app_jwt import revoke_patient_sessions
        from tests.unit.test_telegram_mini_app_jwt import create_session

        staff_session = UserSession(
            user_id=admin_user.id,
            refresh_token="SYNTHETIC-staff-refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            revoked=False,
        )
        db_session.add(staff_session)
        db_session.commit()
        create_session(db_session)
        current = create_session(db_session)
        revoke_patient_sessions(db_session, current["access_token"])
        revoke_patient_sessions(db_session, current["access_token"], logout=True)
        db_session.refresh(staff_session)
        assert staff_session.revoked is False
        assert staff_session.refresh_token == "SYNTHETIC-staff-refresh"
        assert db_session.query(UserSession).count() == 1


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
