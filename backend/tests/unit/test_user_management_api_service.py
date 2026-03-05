from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.user_management_api_service import UserManagementApiService


@pytest.mark.unit
class TestUserManagementApiService:
    def test_update_current_user_preferences_creates_new_record_and_commits(self):
        state = {"committed": False, "refreshed": False}
        created_preferences = SimpleNamespace(
            emr_settings=None,
            theme="system",
            language="ru",
            compact_mode=False,
            sidebar_collapsed=False,
        )

        class Repository:
            def get_preferences_by_user_id(self, user_id):
                return None

            def create_preferences(self, **kwargs):
                created_preferences.theme = kwargs["theme"]
                return created_preferences

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
            preferences_data={"emr_smart_field_mode": "ghost"},
        )

        assert result["success"] is True
        assert state["committed"] is True
        assert state["refreshed"] is True
        assert "emr_smart_field_mode" in created_preferences.emr_settings
        assert created_preferences.theme == "auto"

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
        created_preferences = SimpleNamespace(
            emr_settings=None,
            theme="system",
            language="ru",
            compact_mode=False,
            sidebar_collapsed=False,
        )

        class Repository:
            def get_preferences_by_user_id(self, user_id):
                return None

            def create_preferences(self, **kwargs):
                created_preferences.theme = kwargs["theme"]
                return created_preferences

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
        preferences = SimpleNamespace(
            emr_settings=None,
            theme="light",
            language="ru",
            compact_mode=False,
            sidebar_collapsed=False,
        )

        class Repository:
            def get_preferences_by_user_id(self, user_id):
                return preferences

            def create_preferences(self, **kwargs):
                raise AssertionError("create_preferences must not be called")

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
