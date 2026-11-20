from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.authentication_api_service import (
    AuthenticationApiDomainError,
    AuthenticationApiService,
)


@pytest.mark.unit
class TestAuthenticationApiService:
    def test_update_user_profile_updates_fields_and_returns_profile(self, db_session):
        import uuid

        from app.models.user import User
        from app.services.profile_contact_security import ProfileBearerContext

        current_user = User(
            username=f"SYNTHETIC_profile_{uuid.uuid4().hex}",
            email=f"{uuid.uuid4().hex}@example.test",
            full_name="Old", hashed_password="synthetic-not-used", is_active=True,
        )
        db_session.add(current_user)
        db_session.commit()
        service = AuthenticationApiService(db_session)

        profile = service.update_user_profile(
            current_user=current_user,
            update_data={"full_name": "New"},
            profile_loader=lambda user_id: {"id": user_id, "full_name": "New"},
            bearer_context=ProfileBearerContext(current_user.id, current_user.auth_epoch, None, None, None),
        )

        assert current_user.full_name == "New"
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
