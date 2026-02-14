"""Service layer for authentication endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.authentication_api_repository import AuthenticationApiRepository


@dataclass
class AuthenticationApiDomainError(Exception):
    status_code: int
    detail: str


class AuthenticationApiService:
    """Handles endpoint-side profile/session checks for authentication API."""

    def __init__(
        self,
        db: Session,
        repository: AuthenticationApiRepository | None = None,
    ):
        self.repository = repository or AuthenticationApiRepository(db)

    def update_user_profile(
        self,
        *,
        current_user,
        update_data: dict,
        profile_loader,
    ) -> dict:
        for field, value in update_data.items():
            if hasattr(current_user, field):
                setattr(current_user, field, value)

        self.repository.commit()
        self.repository.refresh_user(current_user)
        profile = profile_loader(current_user.id)
        if not profile:
            raise AuthenticationApiDomainError(
                status_code=404,
                detail="Профиль пользователя не найден",
            )
        return profile

    def ensure_session_access(
        self,
        *,
        session_id: int,
        current_user_id: int,
        allow_admin_access: bool,
    ):
        session = self.repository.get_user_session(session_id)
        if not session:
            raise AuthenticationApiDomainError(
                status_code=404,
                detail="Сессия не найдена",
            )

        if session.user_id != current_user_id and not allow_admin_access:
            raise AuthenticationApiDomainError(
                status_code=403,
                detail="Нет доступа к этой сессии",
            )
        return session

    def rollback(self) -> None:
        self.repository.rollback()
