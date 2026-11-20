from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
            get_active_session_by_token=lambda pending_token: SimpleNamespace(
                user_id=9
            ),
            get_active_session_for_user=lambda user_id, pending_token: None,
            get_user=lambda user_id: SimpleNamespace(id=user_id, username="u9"),
            add_refresh_token=lambda refresh_token_obj: None,
            commit=lambda: None,
        )
        service = TwoFactorAuthApiService(db=None, repository=repository)

        user = service.get_user_from_pending_token("token")

        assert user.username == "u9"

    def test_exchange_pending_token_for_tokens_returns_payload(self):
        added = {"value": None, "access_epoch": None, "refresh_epoch": None, "excluded": None}
        pending_session = SimpleNamespace(
            id=42,
            user_agent="ua",
            revoked=False,
            session_kind="pending_2fa",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        user = SimpleNamespace(
            id=1,
            username="u1",
            role="Admin",
            is_active=True,
            is_superuser=False,
            auth_epoch=7,
        )
        repository = SimpleNamespace(
            db=object(),
            get_active_session_by_token=lambda pending_token: None,
            get_active_session_for_user=lambda user_id, pending_token, lock: (
                pending_session
            ),
            get_user_for_update=lambda user_id: user,
            get_verified_two_factor_for_update=lambda user_id: object(),
            get_user=lambda user_id: None,
            add_refresh_token=lambda refresh_token_obj: added.__setitem__(
                "value",
                refresh_token_obj,
            ),
            flush=lambda: None,
            rollback=lambda: None,
            commit=lambda: None,
        )
        def revoke_for_login(db, locked_user, *, exclude_session_id):
            assert db is repository.db
            assert not pending_session.revoked
            added["excluded"] = exclude_session_id
            locked_user.auth_epoch += 1

        auth_service = SimpleNamespace(
            revoke_all_for_new_login_locked=revoke_for_login,
            create_access_token=lambda payload: (
                added.__setitem__("access_epoch", payload["auth_epoch"])
                or "access-token"
            ),
            create_refresh_token=lambda user_id, jti, auth_epoch: (
                added.__setitem__("refresh_epoch", auth_epoch) or "refresh-token"
            ),
            refresh_token_expire_days=30,
            access_token_expire_minutes=15,
        )
        service = TwoFactorAuthApiService(db=None, repository=repository)

        payload = service.exchange_pending_token_for_tokens(
            user=user,
            pending_token="pending",
            auth_service=auth_service,
        )

        assert payload["access_token"] == "access-token"
        assert payload["refresh_token"] == "refresh-token"
        assert payload["token_type"] == "bearer"
        assert added["value"] is not None
        assert added["access_epoch"] == added["refresh_epoch"] == 8
        assert added["excluded"] == pending_session.id
        assert pending_session.revoked is True
        assert pending_session.user_agent == "ua"
