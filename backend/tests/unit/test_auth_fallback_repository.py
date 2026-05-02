from __future__ import annotations

import pytest

from app.repositories.auth_fallback_repository import AuthFallbackRepository


@pytest.mark.unit
class TestAuthFallbackRepository:
    def test_get_user_model_and_credentials_row(self, db_session, admin_user):
        repository = AuthFallbackRepository(db_session)

        model_user = repository.get_user_model(username=admin_user.username)
        row_user = repository.get_user_credentials_row(username=admin_user.username)

        assert model_user is not None
        assert model_user.id == admin_user.id
        assert row_user is not None
        assert row_user[0] == admin_user.id

