from __future__ import annotations

import pytest

from app.models.user import User
from app.schemas.user_management import UserUpdateRequest
from app.services.user_management_service import UserManagementService


def _create_user(
    db_session,
    *,
    username: str,
    email: str,
    role: str = "Admin",
    is_active: bool = True,
    is_superuser: bool = False,
) -> User:
    user = User(
        username=username,
        email=email,
        full_name=username,
        hashed_password="hashed",
        role=role,
        is_active=is_active,
        is_superuser=is_superuser,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.unit
class TestUserManagementServiceGuardrails:
    def test_update_user_rejects_self_deactivation(self, db_session):
        current_admin = _create_user(
            db_session,
            username="self_admin",
            email="self_admin@test.local",
            role="Admin",
            is_active=True,
            is_superuser=True,
        )
        _create_user(
            db_session,
            username="other_admin",
            email="other_admin@test.local",
            role="Admin",
            is_active=True,
            is_superuser=True,
        )
        service = UserManagementService()

        success, message = service.update_user(
            db_session,
            current_admin.id,
            UserUpdateRequest(is_active=False),
            current_admin.id,
        )

        assert success is False
        assert "Нельзя деактивировать текущую учётную запись" in message

    def test_update_user_rejects_removing_last_active_admin(self, db_session):
        last_admin = _create_user(
            db_session,
            username="last_admin",
            email="last_admin@test.local",
            role="Admin",
            is_active=True,
            is_superuser=False,
        )
        service = UserManagementService()

        success, message = service.update_user(
            db_session,
            last_admin.id,
            UserUpdateRequest(is_active=False),
            999,
        )

        assert success is False
        assert "последнего активного администратора" in message

    def test_delete_user_rejects_self_delete(self, db_session):
        current_admin = _create_user(
            db_session,
            username="delete_self_admin",
            email="delete_self_admin@test.local",
            role="Admin",
            is_active=True,
            is_superuser=True,
        )
        _create_user(
            db_session,
            username="delete_self_other",
            email="delete_self_other@test.local",
            role="Admin",
            is_active=True,
            is_superuser=True,
        )
        service = UserManagementService()

        success, message = service.delete_user(
            db_session,
            current_admin.id,
            current_admin.id,
        )

        assert success is False
        assert "Нельзя удалить текущую учётную запись" in message

    def test_delete_user_rejects_last_active_superuser(self, db_session):
        last_superuser = _create_user(
            db_session,
            username="last_superuser",
            email="last_superuser@test.local",
            role="Admin",
            is_active=True,
            is_superuser=True,
        )
        service = UserManagementService()

        success, message = service.delete_user(
            db_session,
            last_superuser.id,
            999,
        )

        assert success is False
        assert "последнего активного суперпользователя" in message
