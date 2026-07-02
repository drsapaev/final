from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.authentication_api_service import (
    AuthenticationApiDomainError,
    AuthenticationApiService,
)


@pytest.mark.unit
class TestAuthenticationApiService:
    def test_update_user_profile_updates_fields_and_returns_profile(self):
        calls = {"commit": 0, "refresh": 0}
        repository = SimpleNamespace(
            commit=lambda: calls.__setitem__("commit", calls["commit"] + 1),
            refresh_user=lambda user: calls.__setitem__("refresh", calls["refresh"] + 1),
            rollback=lambda: None,
            get_user_session=lambda session_id: None,
        )
        current_user = SimpleNamespace(id=1, full_name="Old", phone=None)
        service = AuthenticationApiService(db=None, repository=repository)

        profile = service.update_user_profile(
            current_user=current_user,
            update_data={"full_name": "New"},
            profile_loader=lambda user_id: {"id": user_id, "full_name": "New"},
        )

        assert current_user.full_name == "New"
        assert calls["commit"] == 1
        assert calls["refresh"] == 1
        assert profile["full_name"] == "New"

    def test_ensure_session_access_raises_when_missing(self):
        repository = SimpleNamespace(
            commit=lambda: None,
            refresh_user=lambda user: None,
            rollback=lambda: None,
            get_user_session=lambda session_id: None,
        )
        service = AuthenticationApiService(db=None, repository=repository)

        with pytest.raises(AuthenticationApiDomainError) as exc_info:
            service.ensure_session_access(
                session_id=5,
                current_user_id=1,
                allow_admin_access=False,
            )

        assert exc_info.value.status_code == 404

    def test_ensure_session_access_raises_for_foreign_session(self):
        repository = SimpleNamespace(
            commit=lambda: None,
            refresh_user=lambda user: None,
            rollback=lambda: None,
            get_user_session=lambda session_id: SimpleNamespace(id=session_id, user_id=2),
        )
        service = AuthenticationApiService(db=None, repository=repository)

        with pytest.raises(AuthenticationApiDomainError) as exc_info:
            service.ensure_session_access(
                session_id=5,
                current_user_id=1,
                allow_admin_access=False,
            )

        assert exc_info.value.status_code == 403
