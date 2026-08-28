"""Full happy path of reset_password_with_token must actually work.

Regression for Sentry PYTHON-FASTAPI-10: the function called ghost
`crud_user.get_user`, so EVERY token-confirm attempt died with
AttributeError → 400, making email-based password reset impossible to
finish even with a valid token.
"""
from __future__ import annotations

import pytest

from app.core.security import get_password_hash
from app.crud import user as crud_user
from app.models.user import User
from app.services.password_reset_service import get_password_reset_service


@pytest.fixture
def svc(db_session):
    svc = get_password_reset_service()
    svc.reset_tokens = {}
    return svc


def _seed_user(db_session) -> User:
    user = User(
        username="reset_completion_user",
        email="reset.completion@test.local",
        full_name="Reset Completion",
        hashed_password=get_password_hash("OldPassw0rd!"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _seed_token(svc, user: User) -> str:
    token = "confirm-path-token-abcdef"
    from datetime import datetime, timedelta

    key = svc._get_token_key(token)
    svc.reset_tokens[key] = {
        "user_id": user.id,
        "email": user.email,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(hours=1),
        "used": False,
    }
    return token


@pytest.mark.asyncio
async def test_confirm_completes_and_marks_token_used(db_session, svc):
    user = _seed_user(db_session)
    token = _seed_token(svc, user)
    old_hash = user.hashed_password

    result = svc.reset_password_with_token(db_session, token=token, new_password="BrandNewPass1")

    assert result["success"] is True
    db_session.refresh(user)
    assert user.hashed_password != old_hash
    key = svc._get_token_key(token)
    assert svc.reset_tokens[key]["used"] is True


@pytest.mark.asyncio
async def test_confirm_rejects_same_as_old_password(db_session, svc):
    user = _seed_user(db_session)
    token = _seed_token(svc, user)

    result = svc.reset_password_with_token(
        db_session, token=token, new_password="OldPassw0rd!"
    )

    assert result["success"] is False
    assert result["error_code"] == "PASSWORD_SAME_AS_OLD"
    # неудачная попытка НЕ расходует токен
    assert svc.reset_tokens[svc._get_token_key(token)]["used"] is False
