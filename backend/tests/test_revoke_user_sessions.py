"""
Regression (Sentry PYTHON-FASTAPI-E, 21 events/24h on every login):
TokensMixin._revoke_all_user_sessions passed "revoked_at" to a
UserSession.bulk-update, but UserSession has no such column since #2924.
The CompileError hit the outer except -> rollback, so on every login the
session-revocation was silently skipped (returned 0) AND the RefreshToken
revocation in the same transaction was rolled back too — stale sessions
and refresh tokens stayed active.

The fix removes revoked_at from the three UserSession updates in
auth_svc/_tokens.py; this test pins that revocation actually works.
"""

from datetime import UTC, datetime, timedelta

from app.models.authentication import RefreshToken, UserSession
from app.models.user import User
from app.services.authentication_service import get_authentication_service


def _mk_user(db_session) -> User:
    user = User(
        username="revoke_rt_user",
        email="revoke_rt@test.com",
        full_name="Revoke RT",
        hashed_password="not-verified-here",
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_revoke_all_user_sessions_revokes_sessions_and_refresh_tokens(db_session):
    user = _mk_user(db_session)
    future = datetime.now(UTC) + timedelta(days=1)

    db_session.add(
        UserSession(user_id=user.id, expires_at=future, revoked=False)
    )
    db_session.add(
        UserSession(user_id=user.id, expires_at=future, revoked=False)
    )
    db_session.add(
        RefreshToken(
            user_id=user.id,
            token="revoke-rt-token-1",
            jti="revoke-rt-jti-1",
            expires_at=future,
            revoked=False,
        )
    )
    db_session.commit()

    svc = get_authentication_service()
    revoked_sessions = svc._revoke_all_user_sessions(
        db_session, user.id, reason="new_login"
    )

    # Pre-fix this was 0: CompileError -> rollback -> silently skipped
    assert revoked_sessions == 2

    assert (
        db_session.query(UserSession)
        .filter(UserSession.user_id == user.id, UserSession.revoked == False)  # noqa: E712
        .count()
        == 0
    )
    assert (
        db_session.query(RefreshToken)
        .filter(RefreshToken.user_id == user.id, RefreshToken.revoked == False)  # noqa: E712
        .count()
        == 0
    )
    # RefreshToken keeps its revocation timestamp (the column exists there)
    rt = (
        db_session.query(RefreshToken)
        .filter(RefreshToken.token == "revoke-rt-token-1")
        .first()
    )
    assert rt.revoked is True
    assert rt.revoked_at is not None


def test_revoke_is_noop_for_user_without_sessions(db_session):
    user = _mk_user(db_session)
    svc = get_authentication_service()
    assert svc._revoke_all_user_sessions(db_session, user.id, reason="new_login") == 0
