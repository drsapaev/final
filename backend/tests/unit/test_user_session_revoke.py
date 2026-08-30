"""UserSession revoke flow must work without AttributeError.

Regression for Sentry PYTHON-FASTAPI-E (304×) and PYTHON-FASTAPI-2S (3×):
UserSession ORM model was missing `revoked_at` column (which exists in the
DB from baseline migration). Any revoke attempt raised
"Unconsumed column names: revoked_at" or type mismatch.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.models.authentication import UserSession
from app.models.user import User
from app.crud.authentication import user_session


def _create_user(db):
    u = User(id=1, username="test", email="t@t.local", hashed_password="x",
             role="Admin", is_active=True)
    db.add(u)
    db.commit()
    return u


def test_deactivate_session_sets_revoked_and_revoked_at(db_session):

    _create_user(db_session)
    s = UserSession(user_id=1, refresh_token="tok", expires_at=datetime.now(UTC))
    db_session.add(s)
    db_session.commit()

    ok = user_session.deactivate_session(db_session, str(s.id))
    assert ok is True
    db_session.refresh(s)
    assert s.revoked is True
    assert s.revoked_at is not None


def test_deactivate_all_user_sessions(db_session):
    _create_user(db_session)
    for i in range(3):
        db_session.add(UserSession(user_id=1, refresh_token=f"tok{i}",
                                   expires_at=datetime.now(UTC)))
    db_session.commit()

    count = user_session.deactivate_all_user_sessions(db_session, user_id=1)
    assert count == 3
    for s in db_session.query(UserSession).all():
        assert s.revoked is True
        assert s.revoked_at is not None
