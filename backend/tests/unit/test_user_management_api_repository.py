from __future__ import annotations

import pytest

from app.core.security import get_password_hash
from app.models.user import User
from app.models.user_profile import UserStatus
from app.repositories.user_management_api_repository import (
    UserManagementApiRepository,
)


from tests.auth_test_credentials import (
    GENERIC_TEST_PASSWORD,
)

@pytest.mark.unit
def test_ensure_user_support_records_bootstraps_profile_preferences_and_notifications(
    db_session,
):
    user = User(
        username="preferences_bootstrap",
        email="preferences@example.com",
        full_name="Preferences Bootstrap",
        hashed_password=get_password_hash(GENERIC_TEST_PASSWORD),
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    repository = UserManagementApiRepository(db_session)
    profile, preferences, notification_settings = repository.ensure_user_support_records(
        user.id
    )

    db_session.commit()

    assert profile.user_id == user.id
    assert profile.full_name == "Preferences Bootstrap"
    assert profile.status == UserStatus.ACTIVE
    assert preferences.user_id == user.id
    assert preferences.profile_id == profile.id
    assert notification_settings.user_id == user.id
    assert notification_settings.profile_id == profile.id
