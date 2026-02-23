from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.two_factor_auth_api_service import TwoFactorAuthApiService


@pytest.mark.unit
class TestTwoFactorAuthApiService:
    def test_get_user_from_pending_token_returns_none_when_session_missing(self):
        repository = SimpleNamespace(
            get_active_session_by_token=lambda pending_token: None,
            get_active_session_for_user=lambda user_id, pending_token: None,
            get_user=lambda user_id: None,
            add_refresh_token=lambda refresh_token_obj: None,
            commit=lambda: None,
        )
        service = TwoFactorAuthApiService(db=None, repository=repository)

        assert service.get_user_from_pending_token("token") is None

    def test_get_user_from_pending_token_returns_user(self):
        repository = SimpleNamespace(
            get_active_session_by_token=lambda pending_token: SimpleNamespace(user_id=9),
            get_active_session_for_user=lambda user_id, pending_token: None,
            get_user=lambda user_id: SimpleNamespace(id=user_id, username="u9"),
            add_refresh_token=lambda refresh_token_obj: None,
            commit=lambda: None,
        )
        service = TwoFactorAuthApiService(db=None, repository=repository)

        user = service.get_user_from_pending_token("token")

        assert user.username == "u9"

    def test_exchange_pending_token_for_tokens_returns_payload(self):
        added = {"value": None}
        pending_session = SimpleNamespace(user_agent="ua")
        repository = SimpleNamespace(
            get_active_session_by_token=lambda pending_token: None,
            get_active_session_for_user=lambda user_id, pending_token: pending_session,
            get_user=lambda user_id: None,
            add_refresh_token=lambda refresh_token_obj: added.__setitem__(
                "value",
                refresh_token_obj,
            ),
            commit=lambda: None,
        )
        auth_service = SimpleNamespace(
            create_access_token=lambda payload: "access-token",
            create_refresh_token=lambda user_id, jti: "refresh-token",
            refresh_token_expire_days=30,
            access_token_expire_minutes=15,
        )
        service = TwoFactorAuthApiService(db=None, repository=repository)
        user = SimpleNamespace(
            id=1,
            username="u1",
            role="Admin",
            is_active=True,
            is_superuser=False,
        )

        payload = service.exchange_pending_token_for_tokens(
            user=user,
            pending_token="pending",
            auth_service=auth_service,
        )

        assert payload["access_token"] == "access-token"
        assert payload["refresh_token"] == "refresh-token"
        assert payload["token_type"] == "bearer"
        assert added["value"] is not None
        assert pending_session.user_agent.endswith("|2fa-verified")
