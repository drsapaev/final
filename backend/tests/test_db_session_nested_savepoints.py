"""Real application SAVEPOINTs must coexist with db_session isolation."""

import pytest

from app.models.user import User


def test_nested_success_and_rollback_do_not_replace_fixture_savepoint(db_session):
    user = User(
        username="SYNTHETIC_nested_fixture_scope",
        email="synthetic-nested-fixture@example.test",
        hashed_password="synthetic-unused-hash",
        role="Nurse",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    with db_session.begin_nested():
        user.full_name = "SYNTHETIC nested committed"
    with pytest.raises(ValueError, match="synthetic rollback"):
        with db_session.begin_nested():
            user.full_name = "SYNTHETIC nested rolled back"
            db_session.flush()
            raise ValueError("synthetic rollback")
    db_session.refresh(user)
    assert user.full_name == "SYNTHETIC nested committed"
    db_session.commit()
    assert db_session.get(User, user.id).full_name == "SYNTHETIC nested committed"


def test_previous_test_did_not_escape_fixture_transaction(db_session):
    assert (
        db_session.query(User)
        .filter(User.username == "SYNTHETIC_nested_fixture_scope")
        .count()
        == 0
    )
