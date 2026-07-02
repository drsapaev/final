from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.user_management_api_service import UserManagementApiService


@pytest.mark.unit
class TestUserManagementApiService:
    def test_update_current_user_preferences_bootstraps_support_records_and_commits(self):
        state = {"committed": False, "refreshed": False}
        profile = SimpleNamespace(
            id=101,
            user_id=1,
            full_name="Bootstrap User",
            status="active",
        )
        created_preferences = SimpleNamespace(
            id=202,
            user_id=1,
            profile_id=101,
            emr_settings=None,
            theme="system",
            language="ru",
            compact_mode=False,
            sidebar_collapsed=False,
        )
        notification_settings = SimpleNamespace(id=303, user_id=1, profile_id=101)

        class Repository:
            def ensure_user_support_records(self, user_id):
                assert user_id == 1
                return profile, created_preferences, notification_settings

            def commit(self):
                state["committed"] = True

            def refresh(self, instance):
                state["refreshed"] = True
                assert instance is created_preferences

            def rollback(self):
                raise AssertionError("rollback must not be called")

        service = UserManagementApiService(db=None, repository=Repository())
        result = service.update_current_user_preferences(
            current_user_id=1,
            preferences_data={
                "theme": "light",
                "emr_smart_field_mode": "ghost",
            },
        )

        assert result["success"] is True
        assert state["refreshed"] is True
        assert created_preferences.profile_id == 101
        assert created_preferences.theme == "light"
        assert created_preferences.emr_settings is not None
        assert "emr_smart_field_mode" in created_preferences.emr_settings
        assert state["committed"] is True

    def test_apply_profile_update_sets_fields_and_commits(self):
        profile = SimpleNamespace(full_name="Old")
        state = {"committed": False}

        class Repository:
            def apply_profile_fields(self, *, profile, update_data):
                for key, value in update_data.items():
                    setattr(profile, key, value)

            def commit(self):
                state["committed"] = True

            def refresh(self, instance):
                pass

            def rollback(self):
                raise AssertionError("rollback must not be called")

        service = UserManagementApiService(db=None, repository=Repository())
        updated = service.apply_profile_update(
            profile=profile,
            update_data={"full_name": "New"},
        )

        assert updated.full_name == "New"
        assert state["committed"] is True

    def test_update_current_user_preferences_normalizes_legacy_system_theme(self):
        profile = SimpleNamespace(id=101, user_id=1, full_name="Bootstrap User")
        created_preferences = SimpleNamespace(
            id=202,
            user_id=1,
            profile_id=101,
            emr_settings=None,
            theme="system",
            language="ru",
            compact_mode=False,
            sidebar_collapsed=False,
        )
        notification_settings = SimpleNamespace(id=303, user_id=1, profile_id=101)

        class Repository:
            def ensure_user_support_records(self, user_id):
                assert user_id == 1
                return profile, created_preferences, notification_settings

            def commit(self):
                return None

            def refresh(self, instance):
                return None

            def rollback(self):
                raise AssertionError("rollback must not be called")

        service = UserManagementApiService(db=None, repository=Repository())
        service.update_current_user_preferences(
            current_user_id=1,
            preferences_data={"theme": "system"},
        )

        assert created_preferences.theme == "auto"

    def test_update_current_user_preferences_preserves_custom_theme_values(self):
        profile = SimpleNamespace(id=101, user_id=1, full_name="Bootstrap User")
        preferences = SimpleNamespace(
            id=202,
            user_id=1,
            profile_id=101,
            emr_settings=None,
            theme="light",
            language="ru",
            compact_mode=False,
            sidebar_collapsed=False,
        )
        notification_settings = SimpleNamespace(id=303, user_id=1, profile_id=101)

        class Repository:
            def ensure_user_support_records(self, user_id):
                assert user_id == 1
                return profile, preferences, notification_settings

            def commit(self):
                return None

            def refresh(self, instance):
                return None

            def rollback(self):
                raise AssertionError("rollback must not be called")

        service = UserManagementApiService(db=None, repository=Repository())
        service.update_current_user_preferences(
            current_user_id=1,
            preferences_data={"theme": "glass"},
        )

        assert preferences.theme == "glass"

    def test_update_current_user_preferences_persists_security_settings_blob(self):
        profile = SimpleNamespace(id=101, user_id=1, full_name="Bootstrap User")
        preferences = SimpleNamespace(
            id=202,
            user_id=1,
            profile_id=101,
            emr_settings=None,
            security_settings=None,
            theme="auto",
            language="ru",
            compact_mode=False,
            sidebar_collapsed=False,
        )
        notification_settings = SimpleNamespace(id=303, user_id=1, profile_id=101)

        class Repository:
            def ensure_user_support_records(self, user_id):
                assert user_id == 1
                return profile, preferences, notification_settings

            def commit(self):
                return None

            def refresh(self, instance):
                return None

            def rollback(self):
                raise AssertionError("rollback must not be called")

        service = UserManagementApiService(db=None, repository=Repository())
        service.update_current_user_preferences(
            current_user_id=1,
            preferences_data={
                "security_settings": {
                    "twoFactorEnabled": True,
                    "sessionTimeout": 45,
                    "autoLogout": False,
                }
            },
        )

        assert preferences.security_settings == {
            "twoFactorEnabled": True,
            "sessionTimeout": 45,
            "autoLogout": False,
        }
