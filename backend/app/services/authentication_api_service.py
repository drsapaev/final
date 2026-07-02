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
        support_records_loader=None,
    ) -> dict:
        profile = None
        if support_records_loader is not None:
            profile, _, _ = support_records_loader()
        else:
            profile = getattr(current_user, "profile", None)

        profile_fields = {
            "full_name",
            "first_name",
            "last_name",
            "middle_name",
            "phone",
            "avatar_url",
            "bio",
            "website",
            "language",
            "timezone",
            "nationality",
            "date_of_birth",
            "gender",
        }
        user_fields = {"full_name", "email"}

        phone_updated = False
        email_updated = False

        for field, value in update_data.items():
            if field in user_fields and hasattr(current_user, field):
                setattr(current_user, field, value)
                if field == "email":
                    email_updated = True

            if profile is not None and field in profile_fields and hasattr(profile, field):
                setattr(profile, field, value)
                if field == "phone":
                    phone_updated = True

        if profile is not None:
            if (
                "full_name" not in update_data
                and any(key in update_data for key in ("first_name", "last_name", "middle_name"))
            ):
                composed_name = " ".join(
                    part
                    for part in [
                        getattr(profile, "first_name", None),
                        getattr(profile, "last_name", None),
                        getattr(profile, "middle_name", None),
                    ]
                    if part
                ).strip()
                if composed_name:
                    profile.full_name = composed_name

            if getattr(profile, "full_name", None):
                current_user.full_name = profile.full_name

            if phone_updated:
                profile.phone_verified = False
            if email_updated:
                profile.email_verified = False

        self.repository.commit()
        self.repository.refresh_user(current_user)
        if profile is not None:
            self.repository.refresh(profile)
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
