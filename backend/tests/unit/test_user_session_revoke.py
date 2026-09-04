"""UserSession revoke flow must work without revoked_at (not on ORM model).

Regression for Sentry PYTHON-FASTAPI-E (304×) and PYTHON-FASTAPI-2S (3×):
CRUD code referenced `revoked_at` in update dicts, but the ORM model
doesn't have it. Any revoke attempt raised "Unconsumed column names".
Fix: update dicts now only set `revoked = True` (the column that exists).
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.models.authentication import UserSession
from app.models.user import User
from app.crud.authentication import user_session


@pytest.fixture
def db(db_session):
    return db_session


@pytest.fixture
def user(db):
    u = User(id=1, username="test", email="t@t.local", hashed_password="x",
             role="Admin", is_active=True)
    db.add(u)
    db.commit()
    return u


def _mk_session(db, uid: int, tok: str) -> UserSession:
    s = UserSession(user_id=uid, refresh_token=tok,
                    expires_at=datetime.now(UTC))
    db.add(s)
    db.commit()
    return s


def test_deactivate_sets_revoked_true(db, user):
    s = _mk_session(db, 1, "tok")
    ok = user_session.deactivate_session(db, str(s.id))
    assert ok is True
    db.refresh(s)
    assert s.revoked is True


def test_deactivate_all_revokes_only_active(db, user):
    s1 = _mk_session(db, 1, "a")
    s2 = _mk_session(db, 1, "b")
    s2.revoked = True
    db.commit()

    count = user_session.deactivate_all_user_sessions(db, user_id=1)
    assert count == 1
    db.refresh(s1)
    assert s1.revoked is True
    db.refresh(s2)
    assert s2.revoked is True  # already revoked, unchanged


def test_revoke_does_not_reference_revoked_at(db, user):
    """The revoke must NOT set revoked_at (column not on ORM model)."""
    s = _mk_session(db, 1, "tok")
    user_session.deactivate_session(db, str(s.id))
    db.refresh(s)
    assert s.revoked is True
    # no AttributeError for revoked_at
    assert not hasattr(s, 'revoked_at')
