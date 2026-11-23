"""Repository helpers for auth endpoints."""

from __future__ import annotations

import inspect

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from app.models.two_factor_auth import TwoFactorAuth
from app.models.user import User


class AuthApiRepository:
    """Encapsulates async/sync user lookups for auth endpoint handlers."""

    def __init__(self, db):
        self.db = db

    async def _execute(self, stmt):
        execute_callable = getattr(self.db, "execute", None)
        if inspect.iscoroutinefunction(execute_callable):
            return await self.db.execute(stmt)
        return await run_in_threadpool(self.db.execute, stmt)

    @staticmethod
    def _extract_user(result):
        try:
            return result.scalar_one_or_none()
        except Exception:
            try:
                return result.scalars().first()
            except Exception:
                return None

    async def get_user_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        result = await self._execute(stmt)
        return self._extract_user(result)

    async def get_user_by_username_or_email(self, username: str) -> User | None:
        stmt = select(User).where(
            (User.username == username) | (User.email == username)
        )
        result = await self._execute(stmt)
        return self._extract_user(result)

    async def get_user_for_update(self, user_id: int) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        return self._extract_user(await self._execute(stmt))

    async def has_configured_second_factor(self, user_id: int) -> bool:
        result = await self._execute(
            select(TwoFactorAuth.id).where(
                TwoFactorAuth.user_id == user_id,
                TwoFactorAuth.totp_enabled.is_(True)
                | TwoFactorAuth.totp_verified.is_(True),
            )
        )
        return result.first() is not None

    async def apply_login_policy(self, user: User) -> None:
        from app.services.authentication_service import get_authentication_service

        service = get_authentication_service()
        if inspect.iscoroutinefunction(getattr(self.db, "run_sync", None)):
            await self.db.run_sync(
                lambda session: service.revoke_all_for_new_login_locked(session, user)
            )
        else:
            await run_in_threadpool(
                service.revoke_all_for_new_login_locked, self.db, user
            )

    async def commit(self) -> None:
        if inspect.iscoroutinefunction(getattr(self.db, "commit", None)):
            await self.db.commit()
        else:
            await run_in_threadpool(self.db.commit)
