"""Password-reset initiation must not allow account enumeration.

Review follow-up to #2800 (P1): the public initiate route returned a
definitive success message + expiry for registered addresses, a generic
message without expiry for unknown ones, and 502 on SMTP failure only for
registered ones — enough to enumerate clinic accounts. Every outcome now
returns the same shape with the same message. Also: get_user_by_email
tolerates legacy duplicate emails (no DB uniqueness on users.email).
"""
from __future__ import annotations

import asyncio

import pytest

from app.core.security import get_password_hash
from app.models.user import User
from app.services.password_reset_service import (
    _PHONE_RESET_TASKS,
    get_password_reset_service,
)

GENERIC_EMAIL = (
    "Если пользователь с таким email существует, ссылка для сброса отправлена"
)
GENERIC_PHONE = (
    "Если пользователь с таким номером существует, код для сброса отправлен"
)

def _make_user(db_session, *, username: str, email: str | None = None) -> User:
    user = User(
        username=username,
        email=email or f"{username}@test.local",
        full_name=username.title(),
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _email_svc(monkeypatch, ok: bool):
    svc = get_password_reset_service()
    svc.reset_tokens = {}

    async def fake_send(to_email, subject, **kwargs):
        return ok, "smtp unavailable" if not ok else "sent"

    monkeypatch.setattr(svc.email_service, "send_email_enhanced", fake_send)
    return svc


def _phone_svc(monkeypatch, ok: bool, sent: list):
    """Mock only the SMS transport; retain the real verified-owner lookup."""
    svc = get_password_reset_service()
    svc.reset_tokens = {}

    async def fake_code(phone, purpose, custom_message=None, account_binding=None):
        sent.append((purpose, account_binding))
        if ok:
            return {"success": True, "expires_in_minutes": 5}
        return {"success": False, "error": "sms provider down"}

    monkeypatch.setattr(svc.phone_verification, "send_verification_code", fake_code)
    return svc


@pytest.mark.asyncio
async def test_email_outcomes_share_identical_response_shape(db_session, monkeypatch):
    user = _make_user(db_session, username="antienum_user")

    unknown = await _email_svc(monkeypatch, ok=True).initiate_email_reset(
        db_session, email="ghost@test.local"
    )
    delivered = await _email_svc(monkeypatch, ok=True).initiate_email_reset(
        db_session, email=user.email
    )
    failed = await _email_svc(monkeypatch, ok=False).initiate_email_reset(
        db_session, email=user.email
    )

    for outcome in (unknown, delivered, failed):
        assert outcome["success"] is True
        assert outcome["message"] == GENERIC_EMAIL
        assert outcome["expires_in_hours"] == delivered["expires_in_hours"]
    # Ключи идентичны — различие набора полей тоже раскрывало бы аккаунт
    assert set(unknown) == set(delivered) == set(failed)
    # Токен создаётся только при реальной доставке
    assert failed.get("error") is None


@pytest.mark.asyncio
async def test_phone_outcomes_share_identical_response_shape(db_session, monkeypatch):
    from app.models.user_profile import UserProfile

    user = _make_user(db_session, username="antienum_phone")
    db_session.add(UserProfile(user_id=user.id, phone="+998901234567", phone_verified=True))
    db_session.commit()
    sent = []
    unknown = await _phone_svc(monkeypatch, ok=True, sent=sent).initiate_phone_reset(
        db_session, phone="+998909876543"
    )
    if _PHONE_RESET_TASKS:
        await asyncio.gather(*tuple(_PHONE_RESET_TASKS))
    delivered = await _phone_svc(monkeypatch, ok=True, sent=sent).initiate_phone_reset(
        db_session, phone="+998901234567"
    )
    if _PHONE_RESET_TASKS:
        await asyncio.gather(*tuple(_PHONE_RESET_TASKS))
    failed = await _phone_svc(monkeypatch, ok=False, sent=sent).initiate_phone_reset(
        db_session, phone="+998901234567"
    )
    if _PHONE_RESET_TASKS:
        await asyncio.gather(*tuple(_PHONE_RESET_TASKS))

    for outcome in (unknown, delivered, failed):
        assert outcome["success"] is True
        assert outcome["message"] == GENERIC_PHONE
        assert outcome["expires_in_minutes"] == 5
    assert set(unknown) == set(delivered) == set(failed)
    assert len(sent) == 2


def test_duplicate_emails_are_rejected_by_schema(db_session):
    """0053_users_email_unique formalized the invariant: duplicate emails
    can no longer EXIST, so the old graceful-dup-lookup test (two users,
    one email) is obsolete by construction. Pin the new contract instead:
    the second insert raises at the DB level."""
    import pytest as _pytest
    from sqlalchemy.exc import IntegrityError

    shared = "dup.shared@test.local"
    _make_user(db_session, username="dup_one", email=shared)

    with _pytest.raises(IntegrityError):
        _make_user(db_session, username="dup_two", email=shared)
        db_session.commit()
