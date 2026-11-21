"""Credential validation for the optional fallback auth endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from app.api.deps import create_access_token
from app.core.roles import is_login_blocked_role
from app.core.security import verify_password
from app.repositories.auth_api_repository import AuthApiRepository


@dataclass
class AuthApiDomainError(Exception):
    status_code: int
    detail: str


class AuthApiService:
    """The legacy fallback has no challenge flow, so never bypass 2FA."""

    def __init__(self, db, repository: AuthApiRepository | None = None):
        self.repository = repository or AuthApiRepository(db)

    async def _authenticate(self, identifier: str, password: str, *, email: bool):
        error = AuthApiDomainError(
            status_code=401, detail="Incorrect username or password"
        )
        lookup = (
            self.repository.get_user_by_username_or_email
            if email
            else self.repository.get_user_by_username
        )
        initial = await lookup(identifier)
        if not initial or not verify_password(
            password, getattr(initial, "hashed_password", "")
        ):
            raise error
        user_id, password_hash, epoch = (
            initial.id,
            initial.hashed_password,
            initial.auth_epoch,
        )
        user = await self.repository.get_user_for_update(user_id)
        if (
            not user
            or not user.is_active
            or user.is_superuser
            or is_login_blocked_role(user.role)
            or user.role in {"Admin", "Cashier", "SuperAdmin"}
            or user.hashed_password != password_hash
            or user.auth_epoch != epoch
            or not (user.username == identifier or (email and user.email == identifier))
            or await self.repository.has_configured_second_factor(user_id)
        ):
            raise error
        await self.repository.apply_login_policy(user)
        return user

    async def login_oauth_payload(self, *, username: str, password: str) -> dict:
        user = await self._authenticate(username, password, email=False)
        payload = {
            "access_token": create_access_token(
                {"sub": str(user.id), "auth_epoch": user.auth_epoch}
            ),
            "token_type": "bearer",
        }
        await self.repository.commit()
        return payload

    async def json_login_payload(
        self, *, username: str, password: str, remember_me: bool
    ) -> dict:
        _ = remember_me
        user = await self._authenticate(username, password, email=True)
        payload = {
            "access_token": create_access_token(
                {"sub": str(user.id), "auth_epoch": user.auth_epoch}
            ),
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
        await self.repository.commit()
        return payload
