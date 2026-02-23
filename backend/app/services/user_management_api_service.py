"""Service layer for user_management endpoints."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.repositories.user_management_api_repository import UserManagementApiRepository


class UserManagementApiService:
    """Handles endpoint-level persistence operations for user management APIs."""

    def __init__(
        self,
        db: Session,
        repository: UserManagementApiRepository | None = None,
    ):
        self.repository = repository or UserManagementApiRepository(db)

    def update_current_user_preferences(
        self,
        *,
        current_user_id: int,
        preferences_data: dict,
    ) -> dict:
        try:
            preferences = self.repository.get_preferences_by_user_id(current_user_id)

            if not preferences:
                preferences = self.repository.create_preferences(
                    user_id=current_user_id,
                    theme=preferences_data.get("theme", "system"),
                    language=preferences_data.get("language", "ru"),
                    compact_mode=preferences_data.get("compact_mode", False),
                    sidebar_collapsed=preferences_data.get("sidebar_collapsed", False),
                )
            else:
                if "theme" in preferences_data:
                    preferences.theme = preferences_data["theme"]
                if "language" in preferences_data:
                    preferences.language = preferences_data["language"]
                if "compact_mode" in preferences_data:
                    preferences.compact_mode = preferences_data["compact_mode"]
                if "sidebar_collapsed" in preferences_data:
                    preferences.sidebar_collapsed = preferences_data["sidebar_collapsed"]

            emr_keys = [
                "emr_smart_field_mode",
                "emr_show_mode_switcher",
                "emr_debounce_ms",
                "emr_recent_icd10",
                "emr_recent_templates",
                "emr_favorite_templates",
                "emr_custom_templates",
            ]

            emr_data: dict = {}
            current_emr = getattr(preferences, "emr_settings", None) or {}
            if isinstance(current_emr, str):
                try:
                    current_emr = json.loads(current_emr)
                except Exception:
                    current_emr = {}

            emr_data.update(current_emr)
            for key in emr_keys:
                if key in preferences_data:
                    emr_data[key] = preferences_data[key]

            if hasattr(preferences, "emr_settings"):
                preferences.emr_settings = json.dumps(emr_data)

            self.repository.commit()
            self.repository.refresh(preferences)
            return {"success": True, "message": "Preferences updated"}
        except Exception:
            self.repository.rollback()
            raise

    def apply_profile_update(self, *, profile, update_data: dict):
        try:
            self.repository.apply_profile_fields(profile=profile, update_data=update_data)
            self.repository.commit()
            self.repository.refresh(profile)
            return profile
        except Exception:
            self.repository.rollback()
            raise

    def get_export_users(self, *, export_filters):
        return self.repository.get_export_users(export_filters=export_filters)

    def rollback(self) -> None:
        self.repository.rollback()
