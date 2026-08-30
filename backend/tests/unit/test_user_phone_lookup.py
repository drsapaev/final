"""User.phone как колонки не существует — телефон живёт в UserProfile.

Regression for the production 500 on phone-based password reset:
crud_user.get_user_by_phone filtered on User.phone (no such column) and
raised AttributeError on every call; search_users did the same in its OR
block. Both now go through user_profiles.phone.
"""
from __future__ import annotations

import pytest

from app.core.security import get_password_hash
from app.crud import user as crud_user
from app.models.user import User
from app.models.user_profile import UserProfile


def _user_with_profile(db_session, *, username: str, phone: str | None) -> User:
    user = User(
        username=username,
        email=f"{username}@test.local",
        full_name=username.title(),
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserProfile(user_id=user.id, phone=phone))
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_get_user_by_phone_finds_via_profile(db_session):
    user = _user_with_profile(db_session, username="phone_lookup", phone="+998901234567")

    found = crud_user.get_user_by_phone(db_session, phone="+998901234567")
    assert found is not None
    assert found.id == user.id

    assert crud_user.get_user_by_phone(db_session, phone="+998909876543") is None


@pytest.mark.asyncio
async def test_password_reset_phone_branch_reaches_dispatch(db_session, monkeypatch):
    """Ветка initiate_phone_reset больше не падает 500 на lookup."""
    from app.services.password_reset_service import get_password_reset_service

    _user_with_profile(db_session, username="phone_reset", phone="+998902345678")
    svc = get_password_reset_service()
    svc.reset_tokens = {}

    async def fake_code(phone, purpose, custom_message=None):
        return {"success": True, "expires_in_minutes": 5}

    monkeypatch.setattr(svc.phone_verification, "send_verification_code", fake_code)

    result = await svc.initiate_phone_reset(db_session, phone="+998902345678")

    assert result["success"] is True
    assert result["message"] == (
        "Если пользователь с таким номером существует, код для сброса отправлен"
    )


@pytest.mark.asyncio
async def test_search_users_matches_profile_phone(db_session):
    _user_with_profile(db_session, username="search_hit", phone="+998903456789")
    _user_with_profile(db_session, username="search_miss", phone="+998904567890")

    hits = crud_user.search_users(db_session, query="03456789")

    ids = [u.id for u in hits]
    usernames = [u.username for u in hits]
    assert len(ids) >= 1
    assert "search_miss" not in usernames
