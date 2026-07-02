"""Service layer for auth endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from app.api.deps import create_access_token
from app.core.security import verify_password
from app.repositories.auth_api_repository import AuthApiRepository


@dataclass
class AuthApiDomainError(Exception):
    status_code: int
    detail: str


class AuthApiService:
    """Handles credential validation for auth endpoint responses."""

    def __init__(self, db, repository: AuthApiRepository | None = None):
        self.repository = repository or AuthApiRepository(db)

    async def login_oauth_payload(self, *, username: str, password: str) -> dict:
        user = await self.repository.get_user_by_username(username)
        if not user or not verify_password(password, getattr(user, "hashed_password", "")):
            raise AuthApiDomainError(
                status_code=401,
                detail="Incorrect username or password",
            )

        access_token = create_access_token({"sub": user.username})
        return {"access_token": access_token, "token_type": "bearer"}

    async def json_login_payload(
        self,
        *,
        username: str,
        password: str,
        remember_me: bool,
    ) -> dict:
        _ = remember_me  # kept for API compatibility
        user = await self.repository.get_user_by_username_or_email(username)
        if not user:
            raise AuthApiDomainError(status_code=401, detail="Неверные учетные данные")
        if not user.is_active:
            raise AuthApiDomainError(
                status_code=401,
                detail="Пользователь деактивирован",
            )
        if not verify_password(password, user.hashed_password):
            raise AuthApiDomainError(status_code=401, detail="Неверные учетные данные")

        access_token = create_access_token(data={"sub": str(user.id)})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
            },
        }
