"""Repository helpers for user_management endpoints."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.crud.user_management import user_preferences
from app.models.user import User
from app.models.user_profile import (
    UserNotificationSettings,
    UserPreferences,
    UserProfile,
    UserStatus,
)


class UserManagementApiRepository:
    """Encapsulates DB primitives used in endpoint-level user management flows."""

    def __init__(self, db: Session):
        self.db = db

    def get_preferences_by_user_id(self, user_id: int) -> UserPreferences | None:
        return user_preferences.get_by_user_id(self.db, user_id)

    def create_preferences(
        self,
        *,
        user_id: int,
        profile_id: int,
        theme: str,
        language: str,
        compact_mode: bool,
        sidebar_collapsed: bool,
        security_settings: dict[str, Any] | None = None,
    ) -> UserPreferences:
        preferences = UserPreferences(
            user_id=user_id,
            profile_id=profile_id,
            theme=theme,
            language=language,
            compact_mode=compact_mode,
            sidebar_collapsed=sidebar_collapsed,
            security_settings=security_settings or {},
        )
        self.db.add(preferences)
        return preferences

    def ensure_user_support_records(
        self, user_id: int
    ) -> tuple[UserProfile, UserPreferences, UserNotificationSettings]:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("Пользователь не найден")

        target_status = UserStatus.ACTIVE if user.is_active else UserStatus.INACTIVE

        profile = user.profile
        if not profile:
            profile = UserProfile(
                user_id=user.id,
                full_name=user.full_name,
                status=target_status,
            )
            self.db.add(profile)
            self.db.flush()
            self.db.refresh(profile)
        else:
            if not profile.full_name and user.full_name:
                profile.full_name = user.full_name
            if profile.status != target_status:
                profile.status = target_status

        profile_id = profile.id
        if profile_id is None:
            persisted_profile = (
                self.db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
            )
            if not persisted_profile or persisted_profile.id is None:
                raise ValueError("Не удалось определить профиль пользователя")
            profile = persisted_profile
            profile_id = persisted_profile.id

        preferences = user.preferences
        if not preferences:
            preferences = self.create_preferences(
                user_id=user.id,
                profile_id=profile_id,
                theme="auto",
                language="ru",
                compact_mode=False,
                sidebar_collapsed=False,
                security_settings={},
            )
        elif preferences.profile_id != profile_id:
            preferences.profile_id = profile_id
        elif getattr(preferences, "security_settings", None) is None:
            preferences.security_settings = {}

        notification_settings = user.notification_settings
        if not notification_settings:
            notification_settings = UserNotificationSettings(
                user_id=user.id,
                profile_id=profile_id,
            )
            self.db.add(notification_settings)
        elif notification_settings.profile_id != profile_id:
            notification_settings.profile_id = profile_id

        return profile, preferences, notification_settings

    def apply_profile_fields(self, *, profile: Any, update_data: dict) -> None:
        for field, value in update_data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)

    def get_export_users(self, *, export_filters) -> list[User]:
        users_query = self.db.query(User)

        if export_filters:
            if export_filters.username:
                users_query = users_query.filter(
                    User.username.contains(export_filters.username)
                )
            if export_filters.email:
                users_query = users_query.filter(User.email.contains(export_filters.email))
            if export_filters.role:
                users_query = users_query.filter(User.role == export_filters.role)
            if export_filters.is_active is not None:
                users_query = users_query.filter(User.is_active == export_filters.is_active)
            if export_filters.created_from:
                users_query = users_query.filter(User.created_at >= export_filters.created_from)
            if export_filters.created_to:
                users_query = users_query.filter(User.created_at <= export_filters.created_to)

        return users_query.all()

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, instance: Any) -> None:
        self.db.refresh(instance)

    def rollback(self) -> None:
        self.db.rollback()
