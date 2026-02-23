from __future__ import annotations

import pytest

from app.core.security import get_password_hash
from app.models.user import User
from app.repositories.admin_users_repository import AdminUsersRepository


@pytest.mark.unit
class TestAdminUsersRepository:
    def test_list_users_returns_users_ordered_by_id(self, db_session):
        db_session.add(
            User(
                username="zeta_user",
                email="zeta@example.com",
                hashed_password=get_password_hash("secret"),
                role="Registrar",
            )
        )
        db_session.commit()

        repository = AdminUsersRepository(db_session)
        rows = repository.list_users()

        ids = [row.id for row in rows]
        assert ids == sorted(ids)
        assert any(row.username == "zeta_user" for row in rows)

