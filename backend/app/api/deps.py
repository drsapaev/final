# app/api/deps.py
"""
Dependency helpers for the API.

This module provides:
- oauth2_scheme for extracting Bearer token
- create_access_token(...) helper
- get_current_user(...) which works with both async and sync SQLAlchemy sessions
- require_roles(...) dependency factory

It is intentionally defensive: it supports get_db() returning either
an AsyncSession or a regular (sync) Session / sessionmaker instance.
"""
from __future__ import annotations

import inspect
import os
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordBearer, HTTPBearer
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

# try to import settings (SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES)
try:
    from app.core.config import settings  # type: ignore
except Exception:
    # fallback if settings module is absent
    class _Fallback:
        SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
        ALGORITHM = os.getenv("ALGORITHM", "HS256")
        ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
        )

    settings = _Fallback()

# import get_db lazily -- it may return AsyncSession or sync Session
try:
    from app.db.session import get_db  # type: ignore
except Exception:
    # get_db should exist in your project; if not, imports will fail later and you need to provide it.
    get_db = None  # type: ignore

# import User model
try:
    from app.models.user import User  # type: ignore
except Exception:
    # If import fails the project is misconfigured; leave User unresolved to raise early.
    User = None  # type: ignore

# import authentication service
try:
    from app.services.authentication_service import get_authentication_service  # type: ignore
except Exception:
    get_authentication_service = None  # type: ignore
    User = Any  # type: ignore

# Correct tokenUrl to point to our /auth/login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT token with `sub` claim taken from data (if provided).
    Returns encoded JWT string.
    """
    to_encode = data.copy()
    if expires_delta is None:
        expires_delta = timedelta(
            minutes=getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24)
        )
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=getattr(settings, "ALGORITHM", "HS256"),
    )
    return encoded_jwt


def _username_from_token(token: str) -> Optional[str]:
    """
    Decode JWT and extract 'sub' (username) claim. Returns None if invalid.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[getattr(settings, "ALGORITHM", "HS256")],
        )
        sub = payload.get("sub")
        if isinstance(sub, str):
            return sub
        return None
    except JWTError:
        return None


async def _get_user_by_username(db, username: str) -> Optional[User]:
    """
    Universal helper that supports both AsyncSession and sync Session.

    - If db.execute is a coroutine function (AsyncSession) we `await db.execute(...)`
    - Otherwise we call db.execute(...) in a threadpool to avoid blocking event loop.

    Attempts to return a mapped User instance or None.
    """
    if db is None:
        return None

    execute_callable = getattr(db, "execute", None)
    stmt = select(User).where(User.username == username)

    # AsyncSession: await directly
    if inspect.iscoroutinefunction(execute_callable):
        result = await db.execute(stmt)
    else:
        # Sync Session: run in a threadpool
        result = await run_in_threadpool(db.execute, stmt)

    # Try common extraction patterns for Result / AsyncResult
    try:
        user = result.scalar_one_or_none()
        return user
    except Exception:
        pass

    try:
        # result.scalars() exists for many versions
        scalars = result.scalars()
        try:
            return scalars.first()
        except Exception:
            # as last resort, convert to list
            items = list(scalars)
            return items[0] if items else None
    except Exception:
        pass

    return None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db=Depends(get_db),
) -> User:
    """
    Dependency that returns the current authenticated User.
    Works with either async or sync DB sessions returned by get_db().
    Raises 401 on invalid token or missing user.
    """
    username = _username_from_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await _get_user_by_username(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*roles: str) -> Callable[..., Any]:
    """
    Dependency factory that enforces roles for the current user.
    Usage:
        @router.get("/secret")
        def secret(user=Depends(require_roles("admin"))):
            ...

    If the user's attribute 'role' is not in roles and 'is_superuser' is False -> 403.
    """

    def _dep(current_user: User = Depends(get_current_user)) -> User:
        if not roles:
            return current_user
        role = getattr(current_user, "role", None)
        is_super = bool(getattr(current_user, "is_superuser", False))
        if is_super:
            return current_user

        # Проверяем роль с учетом регистра
        role_lower = str(role).lower() if role else ""
        roles_lower = [str(r).lower() for r in roles]

        if role_lower not in roles_lower:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
            )
        return current_user

    return _dep


def get_current_user_from_request(request: Request) -> Optional[User]:
    """Получить текущего пользователя из состояния запроса (для middleware)"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        return None
    
    # Получаем сессию БД
    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        return user
    finally:
        db.close()


def get_current_user_id(request: Request) -> Optional[int]:
    """Получить ID текущего пользователя из состояния запроса"""
    return getattr(request.state, 'user_id', None)


def get_current_user_role(request: Request) -> Optional[str]:
    """Получить роль текущего пользователя из состояния запроса"""
    return getattr(request.state, 'role', None)


def require_authentication(request: Request) -> User:
    """Требует аутентификации пользователя"""
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется аутентификация"
        )
    return user


def require_active_user(request: Request) -> User:
    """Требует активного пользователя"""
    user = require_authentication(request)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь деактивирован"
        )
    return user


def require_superuser(request: Request) -> User:
    """Требует суперпользователя"""
    user = require_active_user(request)
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права суперпользователя"
        )
    return user


def require_admin(request: Request) -> User:
    """Требует администратора"""
    user = require_active_user(request)
    if user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора"
        )
    return user


def require_doctor_or_admin(request: Request) -> User:
    """Требует врача или администратора"""
    user = require_active_user(request)
    if user.role not in ["Admin", "Doctor"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права врача или администратора"
        )
    return user


def require_staff(request: Request) -> User:
    """Требует сотрудника клиники"""
    user = require_active_user(request)
    if user.role not in ["Admin", "Doctor", "Nurse", "Receptionist"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права сотрудника клиники"
        )
    return user


def get_optional_user(request: Request) -> Optional[User]:
    """Получить пользователя, если он аутентифицирован (опционально)"""
    return get_current_user_from_request(request)


def validate_token(token: str, db: Session) -> Optional[dict]:
    """Валидирует JWT токен"""
    if not get_authentication_service:
        return None
    
    try:
        auth_service = get_authentication_service()
        payload = auth_service.verify_token(token, "access")
        return payload
    except Exception:
        return None


def get_user_from_token(token: str, db: Session) -> Optional[User]:
    """Получить пользователя по токену"""
    payload = validate_token(token, db)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    try:
        return db.query(User).filter(User.id == int(user_id)).first()
    except (ValueError, TypeError):
        return None
