"""Password-reset initiation must not allow account enumeration.

Review follow-up to #2800 (P1): the public initiate route returned a
definitive success message + expiry for registered addresses, a generic
message without expiry for unknown ones, and 502 on SMTP failure only for
registered ones — enough to enumerate clinic accounts. Every outcome now
returns the same shape with the same message. Also: get_user_by_email
tolerates legacy duplicate emails (no DB uniqueness on users.email).
"""
from __future__ import annotations

import pytest

from app.core.security import get_password_hash
from app.crud import user as crud_user
from app.models.user import User
from app.services.password_reset_service import get_password_reset_service

GENERIC_EMAIL = (
    "Если пользователь с таким email существует, ссылка для сброса отправлена"
)
GENERIC_PHONE = (
    "Если пользователь с таким номером существует, код для сброса отправлен"
)

_KNOWN_PHONE_USER: User | None = None


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


def _phone_svc(monkeypatch, ok: bool, known_phone: str | None = None):
    """Служба с моком phone-канала.

    User.phone как колонки модели не существует (латентный баг phone-ветки,
    отмечен в #2775) — поиск по номеру мокаем на уровне crud-функции.
    """
    from app.crud import user as crud_user  # noqa: PLC0415 — изоляция мока

    svc = get_password_reset_service()
    svc.reset_tokens = {}

    async def fake_code(phone, purpose, custom_message=None):
        if ok:
            return {"success": True, "expires_in_minutes": 5}
        return {"success": False, "error": "sms provider down"}

    def fake_get_by_phone(db, phone):
        return _KNOWN_PHONE_USER if phone == known_phone else None

    monkeypatch.setattr(svc.phone_verification, "send_verification_code", fake_code)
    monkeypatch.setattr(crud_user, "get_user_by_phone", fake_get_by_phone)
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
    global _KNOWN_PHONE_USER
    _KNOWN_PHONE_USER = _make_user(db_session, username="antienum_phone")
    try:
        unknown = await _phone_svc(
            monkeypatch, ok=True, known_phone=None
        ).initiate_phone_reset(db_session, phone="+998909876543")
        delivered = await _phone_svc(
            monkeypatch, ok=True, known_phone="+998901234567"
        ).initiate_phone_reset(db_session, phone="+998901234567")
        failed = await _phone_svc(
            monkeypatch, ok=False, known_phone="+998901234567"
        ).initiate_phone_reset(db_session, phone="+998901234567")
    finally:
        _KNOWN_PHONE_USER = None

    for outcome in (unknown, delivered, failed):
        assert outcome["success"] is True
        assert outcome["message"] == GENERIC_PHONE
        assert outcome["expires_in_minutes"] == 5
    assert set(unknown) == set(delivered) == set(failed)


@pytest.mark.asyncio
async def test_duplicate_emails_do_not_break_the_lookup(db_session, monkeypatch):
    shared = "dup.shared@test.local"
    _make_user(db_session, username="dup_one", email=shared)
    _make_user(db_session, username="dup_two", email=shared)

    found = crud_user.get_user_by_email(db_session, email=shared)
    assert found is not None  # scalar_one_or_none поднимал MultipleResultsFound

    svc = _email_svc(monkeypatch, ok=True)
    result = await svc.initiate_email_reset(db_session, email=shared)
    assert result["success"] is True
