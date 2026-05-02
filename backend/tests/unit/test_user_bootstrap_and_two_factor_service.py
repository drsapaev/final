from __future__ import annotations

import pytest

from app.core.security import get_password_hash
from app.models.two_factor_auth import (
    TwoFactorAuth,
    TwoFactorBackupCode,
    TwoFactorRecovery,
)
from app.models.user import User
from app.models.user_profile import UserStatus
from app.services.two_factor_service import TwoFactorService
from app.services.user_management_service import UserManagementService


@pytest.mark.unit
def test_ensure_user_support_records_creates_profile_preferences_and_notifications(
    db_session,
):
    user = User(
        username="bootstrap_user",
        email="bootstrap@example.com",
        full_name="Bootstrap User",
        hashed_password=get_password_hash("password123"),
        role="Receptionist",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    service = UserManagementService()
    profile, preferences, notification_settings = service.ensure_user_support_records(
        db_session, user.id
    )

    assert profile.user_id == user.id
    assert profile.full_name == "Bootstrap User"
    assert profile.status == UserStatus.ACTIVE
    assert preferences.user_id == user.id
    assert preferences.profile_id == profile.id
    assert notification_settings.user_id == user.id
    assert notification_settings.profile_id == profile.id


@pytest.mark.unit
def test_two_factor_service_returns_empty_logs_and_recovery_methods_without_setup(
    db_session,
):
    user = User(
        username="two_factor_empty",
        email="twofactor@example.com",
        hashed_password=get_password_hash("password123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    service = TwoFactorService()

    assert service.get_security_logs(db_session, user.id) == []
    assert service.get_recovery_methods(db_session, user.id) == []


@pytest.mark.unit
def test_setup_two_factor_auth_creates_codes_without_recovery_contact(db_session):
    user = User(
        username="two_factor_setup",
        email="setup@example.com",
        hashed_password=get_password_hash("password123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    service = TwoFactorService()

    setup_data = service.setup_two_factor_auth(db_session, user.id)

    two_factor_auth = (
        db_session.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user.id).first()
    )
    backup_codes = (
        db_session.query(TwoFactorBackupCode)
        .filter(TwoFactorBackupCode.two_factor_auth_id == two_factor_auth.id)
        .all()
    )
    recovery_rows = (
        db_session.query(TwoFactorRecovery)
        .filter(TwoFactorRecovery.two_factor_auth_id == two_factor_auth.id)
        .all()
    )

    assert two_factor_auth is not None
    assert two_factor_auth.backup_codes_generated is True
    assert two_factor_auth.backup_codes_count == len(setup_data["backup_codes"])
    assert len(backup_codes) == len(setup_data["backup_codes"]) == service.backup_codes_count
    assert recovery_rows == []
    assert setup_data["recovery_token"] is None
    assert setup_data["expires_at"] is None
