from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.security import get_password_hash
from app.services.auth_fallback_service import (
    AuthFallbackDomainError,
    AuthFallbackService,
)


@pytest.mark.unit
class TestAuthFallbackService:
    def test_login_with_sql_row_raises_for_missing_user(self):
        repository = SimpleNamespace(get_user_credentials_row=lambda username: None)
        service = AuthFallbackService(db=None, repository=repository)

        with pytest.raises(AuthFallbackDomainError) as exc_info:
            service.login_with_sql_row(
                username="missing",
                password="pass",
                remember_me=False,
            )

        assert exc_info.value.status_code == 401

    def test_login_with_user_model_returns_token_payload(self):
        repository = SimpleNamespace(
            get_user_model=lambda username: SimpleNamespace(
                id=7,
                username="doctor",
                email="doctor@example.com",
                full_name="Doctor Test",
                role="Doctor",
                is_active=True,
                is_superuser=False,
                hashed_password=get_password_hash("secret"),
            )
        )
        service = AuthFallbackService(db=None, repository=repository)

        payload = service.login_with_user_model(
            username="doctor",
            password="secret",
            remember_me=False,
        )

        assert payload["token_type"] == "bearer"
        assert payload["expires_in"] > 0
        assert payload["user"]["username"] == "doctor"

