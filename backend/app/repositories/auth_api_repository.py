"""Repository helpers for auth endpoints."""

from __future__ import annotations

import inspect

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

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
