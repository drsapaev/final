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
    return get_password_reset_service()


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


def _seed_token(db_session, svc, user: User) -> str:
    from datetime import UTC, datetime, timedelta

    from app.models.authentication import PasswordResetToken

    token = "confirm-path-token-abcdef"
    db_session.add(
        PasswordResetToken(
            user_id=user.id,
            token=svc._hash_token(token),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            used=False,
        )
    )
    db_session.commit()
    return token


@pytest.mark.asyncio
async def test_confirm_completes_and_marks_token_used(db_session, svc):
    user = _seed_user(db_session)
    token = _seed_token(db_session, svc, user)
    old_hash = user.hashed_password

    result = svc.reset_password_with_token(db_session, token=token, new_password="BrandNewPass1")

    assert result["success"] is True
    db_session.refresh(user)
    assert user.hashed_password != old_hash
    from app.models.authentication import PasswordResetToken

    row = (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.token == svc._hash_token(token))
        .first()
    )
    assert row.used is True


@pytest.mark.asyncio
async def test_confirm_rejects_same_as_old_password(db_session, svc):
    user = _seed_user(db_session)
    token = _seed_token(db_session, svc, user)

    result = svc.reset_password_with_token(
        db_session, token=token, new_password="OldPassw0rd!"
    )

    assert result["success"] is False
    assert result["error_code"] == "PASSWORD_SAME_AS_OLD"
    # неудачная попытка НЕ расходует токен
    from app.models.authentication import PasswordResetToken

    row = (
        db_session.query(PasswordResetToken)
        .filter(PasswordResetToken.token == svc._hash_token(token))
        .first()
    )
    assert row.used is False
