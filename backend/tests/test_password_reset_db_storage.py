"""
Regression: password-reset tokens lived in a process-local dict on the
service singleton — every deploy/restart wiped all emailed reset links
(users got TOKEN_NOT_FOUND on links that were minutes old). Tokens now
live in the password_reset_tokens table (sha256-hex of the raw token;
the raw bearer token never enters the DB).

The deploy scenario is pinned by constructing a FRESH service instance
after the token was issued and validating against it.
"""

import asyncio
import hashlib
import unittest.mock as mock
from datetime import UTC, datetime, timedelta

import pytest

from app.models.authentication import PasswordResetToken
from app.models.user import User
from app.services.password_reset_service import PasswordResetService


@pytest.fixture
def reset_user(db_session) -> User:
    from app.models.user_profile import UserProfile

    user = User(
        username="reset_db_user",
        email="reset_db@test.com",
        full_name="Reset Db",
        hashed_password="$2b$12$KIXQeQeJhD2PWXcG9dY6nOJmQ6QZ5W8bMOy0SJ3nqOU3cVqP2b7Cu",
        role="Patient",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Phone-based reset looks the user up via UserProfile.phone
    db_session.add(UserProfile(user_id=user.id, phone="+998900000000"))
    db_session.commit()
    return user


class _StubPhone:
    def verify_code(self, phone, code, purpose):
        return {"success": True}


def _issue_token_via_phone(db_session, user, raw="raw-test-token-abc") -> str:
    """Phone flow with a stubbed verification service: returns the raw token."""
    svc = PasswordResetService()
    svc.phone_verification = _StubPhone()
    with mock.patch.object(svc, "generate_reset_token", return_value=raw):
        result = asyncio.run(
            svc.verify_phone_and_get_token(db_session, "+998900000000", "000000")
        )
    assert result["success"] is True, result
    return result["reset_token"]


def test_token_survives_service_restart(db_session, reset_user):
    raw = _issue_token_via_phone(db_session, reset_user)

    # "Deploy": brand-new service instance, empty in-memory state.
    fresh = PasswordResetService()
    validation = fresh.validate_reset_token(db_session, raw)

    assert validation["valid"] is True, validation
    assert validation["user_id"] == reset_user.id
    assert validation["time_left_minutes"] >= 59


def test_db_stores_hash_not_raw_token(db_session, reset_user):
    raw = _issue_token_via_phone(db_session, reset_user)

    row = (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == reset_user.id)
        .first()
    )
    assert row is not None
    assert row.token == hashlib.sha256(raw.encode()).hexdigest()
    assert row.token != raw


def test_reset_marks_used_and_replay_fails(db_session, reset_user):
    raw = _issue_token_via_phone(db_session, reset_user)
    svc = PasswordResetService()

    first = svc.reset_password_with_token(db_session, raw, "NewStrongPass123")
    assert first["success"] is True, first

    replay = svc.reset_password_with_token(db_session, raw, "AnotherPass456")
    assert replay["success"] is False
    assert replay["error_code"] == "TOKEN_ALREADY_USED"

    post = svc.validate_reset_token(db_session, raw)
    assert post["valid"] is False
    assert post["error_code"] == "TOKEN_ALREADY_USED"


def test_expired_token_rejected(db_session, reset_user):
    db_session.add(
        PasswordResetToken(
            user_id=reset_user.id,
            token=hashlib.sha256(b"expired-raw").hexdigest(),
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
            used=False,
        )
    )
    db_session.commit()

    svc = PasswordResetService()
    result = svc.validate_reset_token(db_session, "expired-raw")
    assert result["valid"] is False
    assert result["error_code"] == "TOKEN_EXPIRED"


def test_unknown_token_not_found(db_session):
    svc = PasswordResetService()
    result = svc.validate_reset_token(db_session, "no-such-token")
    assert result["valid"] is False
    assert result["error_code"] == "TOKEN_NOT_FOUND"


def test_email_flow_stores_token_in_db(db_session, reset_user):
    svc = PasswordResetService()

    async def _fake_send(**kwargs):
        return True, "queued"

    with mock.patch.object(
        svc, "generate_reset_token", return_value="raw-email-token"
    ), mock.patch.object(svc.email_service, "send_email_enhanced", new=_fake_send):
        result = asyncio.run(svc.initiate_email_reset(db_session, reset_user.email))

    assert result["success"] is True, result
    rows = (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == reset_user.id)
        .count()
    )
    assert rows >= 1


def test_statistics_from_db(db_session, reset_user):
    _issue_token_via_phone(db_session, reset_user)
    svc = PasswordResetService()
    stats = svc.get_statistics(db_session)
    assert stats["total_tokens"] >= 1
    assert stats["active_tokens"] >= 1
    assert stats["used_tokens"] >= 0
    assert "by_method" in stats
