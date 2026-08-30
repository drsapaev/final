"""Regression: password change/reset must revoke user sessions.

Sentry (kosmed-clinic/python-fastapi, 14 events): ``Error revoking user
sessions: Unconsumed column names: revoked_at`` — the revocation updates
wrote a ``revoked_at`` column that does not exist on ``user_sessions``
(only ``refresh_tokens`` has it), so SQLAlchemy raised and sessions were
NEVER revoked (broken session-fixation protection on every password
change/reset).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.security import get_password_hash
from app.models.authentication import UserSession
from app.models.user import User


def _make_user(db, username: str, password: str = "OldPassw0rd!1") -> User:
    user = User(
        username=username,
        email=f"{username}@test.local",
        full_name=f"Revoke {username}",
        hashed_password=get_password_hash(password),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _add_session(db, user_id: int, token: str) -> UserSession:
    session = UserSession(
        user_id=user_id,
        refresh_token=token,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


class TestPasswordChangeRevokesSessions:
    def test_change_password_revokes_active_sessions(self, client, db_session):
        from app.services.authentication_service import AuthenticationService

        user = _make_user(db_session, "revoke_change")
        session = _add_session(db_session, user.id, "sess-change-1")

        result = AuthenticationService().change_password(
            db=db_session,
            user_id=user.id,
            current_password="OldPassw0rd!1",
            new_password="NewPassw0rd!2",
        )

        assert result["success"] is True
        db_session.refresh(session)
        assert session.revoked is True

    def test_user_sessions_table_has_no_revoked_at_column(self, db_session):
        """Guard the schema contract the fix relies on."""
        columns = {c["name"] for c in _table_columns(db_session, "user_sessions")}
        assert "revoked" in columns
        assert "revoked_at" not in columns


def _table_columns(db, table_name: str):
    from sqlalchemy import inspect

    inspector = inspect(db.get_bind())
    return inspector.get_columns(table_name)
