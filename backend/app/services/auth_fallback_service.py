"""Service layer for minimal/simple auth endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.api.deps import create_access_token
from app.core.security import verify_password
from app.repositories.auth_fallback_repository import AuthFallbackRepository


@dataclass
class AuthFallbackDomainError(Exception):
    status_code: int
    detail: str


class AuthFallbackService:
    """Performs credential validation for fallback auth endpoints."""

    def __init__(
        self,
        db: Session,
        repository: AuthFallbackRepository | None = None,
    ):
        self.repository = repository or AuthFallbackRepository(db)

    @staticmethod
    def _build_response_payload(
        *,
        user_id: int,
        username: str,
        email: str | None,
        full_name: str | None,
        role: str | None,
        is_active: bool,
        is_superuser: bool,
        remember_me: bool,
    ) -> dict:
        expires_delta = timedelta(hours=24 if remember_me else 8)
        access_token = create_access_token(
            data={"sub": str(user_id), "user_id": user_id, "username": username},
            expires_delta=expires_delta,
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": int(expires_delta.total_seconds()),
            "user": {
                "id": user_id,
                "username": username,
                "email": email,
                "full_name": full_name,
                "role": role,
                "is_active": is_active,
                "is_superuser": is_superuser,
            },
        }

    def login_with_sql_row(
        self,
        *,
        username: str,
        password: str,
        remember_me: bool,
    ) -> dict:
        user_row = self.repository.get_user_credentials_row(username=username)
        if not user_row:
            raise AuthFallbackDomainError(
                status_code=401,
                detail="Неверные учетные данные",
            )

        (
            user_id,
            found_username,
            email,
            full_name,
            role,
            is_active,
            is_superuser,
            hashed_password,
        ) = user_row

        if not is_active:
            raise AuthFallbackDomainError(
                status_code=401,
                detail="Пользователь деактивирован",
            )
        if not verify_password(password, hashed_password):
            raise AuthFallbackDomainError(
                status_code=401,
                detail="Неверные учетные данные",
            )

        return self._build_response_payload(
            user_id=user_id,
            username=found_username,
            email=email,
            full_name=full_name,
            role=role,
            is_active=is_active,
            is_superuser=is_superuser,
            remember_me=remember_me,
        )

    def login_with_user_model(
        self,
        *,
        username: str,
        password: str,
        remember_me: bool,
    ) -> dict:
        user = self.repository.get_user_model(username=username)
        if not user:
            raise AuthFallbackDomainError(
                status_code=401,
                detail="Неверные учетные данные",
            )
        if not user.is_active:
            raise AuthFallbackDomainError(
                status_code=401,
                detail="Пользователь деактивирован",
            )
        if not verify_password(password, user.hashed_password):
            raise AuthFallbackDomainError(
                status_code=401,
                detail="Неверные учетные данные",
            )

        return self._build_response_payload(
            user_id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            remember_me=remember_me,
        )

