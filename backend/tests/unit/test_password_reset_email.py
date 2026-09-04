"""Unit tests for the email password-reset initiation path.

Regression guard for two crashes found in production (500 on
POST /api/v1/password-reset/initiate):
1. password_reset_service called ``crud_user.get_user_by_email`` which did
   not exist on ``app.crud.user`` (the method lived only on the CRUDUser
   class in app.crud.authentication).
2. The service called ``email_service.send_email`` while
   EmailSMSEnhancedService only exposes ``send_email_enhanced`` returning
   a (bool, str) tuple.

Also asserts the PII-safe log contract: the recipient address must not be
logged in plaintext.
"""
from __future__ import annotations

import logging

import pytest

from app.core.security import get_password_hash
from app.crud import user as crud_user
from app.models.user import User
from app.services.password_reset_service import get_password_reset_service


@pytest.fixture
def reset_user(db_session):
    user = User(
        username="reset_email_user",
        email="reset.email.user@test.local",
        full_name="Reset Email User",
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_get_user_by_email_exists_and_finds_user(db_session, reset_user):
    found = crud_user.get_user_by_email(db_session, email=reset_user.email)
    assert found is not None
    assert found.id == reset_user.id

    missing = crud_user.get_user_by_email(
        db_session, email="nobody@test.local"
    )
    assert missing is None


@pytest.mark.asyncio
async def test_initiate_email_reset_sends_via_enhanced_sender(
    db_session, reset_user, monkeypatch, caplog
):
    svc = get_password_reset_service()

    calls = {}

    async def fake_send(to_email, subject, **kwargs):
        calls["to"] = to_email
        calls["subject"] = subject
        return True, "sent"

    monkeypatch.setattr(
        svc.email_service, "send_email_enhanced", fake_send
    )

    with caplog.at_level(logging.INFO):
        result = await svc.initiate_email_reset(db_session, email=reset_user.email)

    assert result["success"] is True
    assert calls["to"] == reset_user.email
    # Токен сохранён в БД и помечен неиспользованным
    from app.models.authentication import PasswordResetToken

    rows = (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == reset_user.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].used is False
    # PII: адрес получателя не должен попасть в лог
    assert reset_user.email not in caplog.text


@pytest.mark.asyncio
async def test_initiate_email_reset_unknown_email_is_silent_success(
    db_session, monkeypatch
):
    svc = get_password_reset_service()

    async def fail_if_called(**kwargs):
        raise AssertionError("email must not be sent for unknown address")

    monkeypatch.setattr(
        svc.email_service, "send_email_enhanced", fail_if_called
    )

    result = await svc.initiate_email_reset(db_session, email="ghost@test.local")

    # Не раскрываем существование пользователя + ничего не шлём и не храним
    from app.models.authentication import PasswordResetToken

    assert result["success"] is True
    assert (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id != None)  # noqa: E711
        .count()
        == 0
    )
