"""Single-session logout must actually revoke the linked UserSession row.

Sentry PYTHON-FASTAPI-3D: logout_user updated UserSession with
``{"revoked": True, "revoked_at": ...}``, but UserSession has no
revoked_at column (#2924 documents the deliberate omission). SQLAlchemy
raised UnconsumedColumnError, the outer except rolled the whole logout
back, and the function returned success=False — the server-side session
and refresh token stayed valid while the client believed it logged out.

Run:
    pytest backend/tests/unit/test_logout_user_session_revocation.py -v
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base_class import Base
from app.models.authentication import RefreshToken, UserSession
from app.models.user import User
from app.services.auth_svc import AuthenticationService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()


def seed_session(db_session):
    """One user + one valid refresh token + one linked active session."""
    user = User(
        username="logout_probe",
        hashed_password="x",
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    refresh = RefreshToken(
        user_id=user.id,
        token="logout-probe-refresh-token",
        jti="logout-probe-jti",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    session_row = UserSession(
        user_id=user.id,
        refresh_token="logout-probe-refresh-token",
        expires_at=datetime.now(UTC) + timedelta(days=7),
        revoked=False,
    )
    db_session.add_all([refresh, session_row])
    db_session.commit()
    return user, refresh, session_row


def test_single_session_logout_revokes_the_linked_user_session(db_session):
    """Seeds a user + refresh token + linked ACTIVE session, then logs out:
    the linked UserSession row must flip to revoked (the Sentry-3D bug left
    it active because the update carried a nonexistent revoked_at column)."""
    service = AuthenticationService()
    user, refresh, session_row = seed_session(db_session)

    result = service.logout_user(
        db_session, refresh_token="logout-probe-refresh-token"
    )

    assert result.get("success") is True, result
    db_session.expire_all()
    assert refresh.revoked is True, "refresh token was not revoked"
    assert session_row.revoked is True, "linked session was not revoked"


def test_logout_all_revokes_every_session_without_revoked_at_write(db_session):
    """The logout-all branch must revoke all sessions using the revoked flag
    only (UserSession has no revoked_at column - #2924)."""
    service = AuthenticationService()
    user = User(
        username="logout_all_probe",
        hashed_password="x",
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add_all(
        [
            UserSession(user_id=user.id, expires_at=datetime.now(UTC) + timedelta(days=7)),
            UserSession(user_id=user.id, expires_at=datetime.now(UTC) + timedelta(days=7)),
        ]
    )
    db_session.commit()

    result = service.logout_user(db_session, user_id=user.id, logout_all=True)

    assert result.get("success") is True, result
    rows = db_session.query(UserSession).filter(UserSession.user_id == user.id).all()
    assert rows and all(r.revoked is True for r in rows)
