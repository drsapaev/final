"""Repository helpers for user_management endpoints."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.crud.user_management import user_preferences
from app.models.user import User
from app.models.user_profile import UserPreferences


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
        theme: str,
        language: str,
        compact_mode: bool,
        sidebar_collapsed: bool,
    ) -> UserPreferences:
        preferences = UserPreferences(
            user_id=user_id,
            theme=theme,
            language=language,
            compact_mode=compact_mode,
            sidebar_collapsed=sidebar_collapsed,
        )
        self.db.add(preferences)
        return preferences

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
