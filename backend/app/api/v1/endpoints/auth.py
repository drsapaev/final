# app/api/v1/endpoints/auth.py
"""
Auth endpoints: /login (OAuth2 password form) and /me (current profile).

This implementation is defensive: it supports get_db() returning either an
AsyncSession (async DB) or a sync Session/sessionmaker. The DB calls are
dispatched either by awaiting (async) or via run_in_threadpool (sync).
"""
from __future__ import annotations

import inspect
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select

# helpers from deps
from app.api.deps import create_access_token, get_current_user

# password verification helper (assumed present in project)
from app.core.security import verify_password

# Import your project's DB session factory / dependency
# get_db should be a dependency that yields either an AsyncSession or sync Session
from app.db.session import get_db

# ORM user model
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)
) -> Any:
    """
    OAuth2 password flow (token endpoint).

    Accepts form fields:
      - username
      - password
      - scope (ignored)
    Returns:
      {"access_token": "<jwt>", "token_type": "bearer"}

    Works with both async and sync SQLAlchemy sessions returned by get_db().
    """
    # DEBUG: Add logging
    logger.info(f"Login attempt for username: {form_data.username}")

    # build select statement
    stmt = select(User).where(User.username == form_data.username)

    # Detect whether db.execute is a coroutine function (AsyncSession) or sync Session
    execute_callable = getattr(db, "execute", None)
    if inspect.iscoroutinefunction(execute_callable):
        # AsyncSession: await directly
        result = await db.execute(stmt)
    else:
        # Sync Session: run in threadpool to avoid blocking event loop
        result = await run_in_threadpool(db.execute, stmt)

    # Try to extract user from result in a robust way
    user = None
    try:
        user = result.scalar_one_or_none()
    except Exception:
        try:
            # fallback for Result API
            user = result.scalars().first()
        except Exception:
            user = None

    # DEBUG: Log user info
    if user:
        logger.debug(f"User found: {user.username}, active: {user.is_active}")
        # Secure: Do not log hashed password
    else:
        logger.warning(f"User not found for username: {form_data.username}")

    if not user or not verify_password(
        form_data.password, getattr(user, "hashed_password", "")
    ):
        logger.warning(f"Authentication failed for {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create JWT access token (create_access_token implemented in deps)
    access_token = create_access_token({"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=None)
async def me(current_user: User = Depends(get_current_user)):
    """Return current authenticated user profile as plain JSON."""
    return {
        "id": getattr(current_user, "id", None),
        "username": getattr(current_user, "username", None),
        "full_name": getattr(current_user, "full_name", None),
        "email": getattr(current_user, "email", None),
        "role": getattr(current_user, "role", None),
        "is_active": getattr(current_user, "is_active", True),
        "is_superuser": getattr(current_user, "is_superuser", False),
    }


class JSONLoginRequest(BaseModel):
    """Схема для JSON входа"""

    username: str
    password: str
    remember_me: bool = False


class JSONLoginResponse(BaseModel):
    """Схема ответа JSON входа"""

    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


@router.post("/json-login", response_model=JSONLoginResponse)
async def json_login(request_data: JSONLoginRequest, db=Depends(get_db)) -> Any:
    """
    JSON login endpoint (альтернатива OAuth2 form).

    Accepts JSON:
      - username (email или username)
      - password
      - remember_me (опционально)
    Returns:
      {"access_token": "<jwt>", "token_type": "bearer", "user": {...}}
    """
    try:
        logger.info(f"JSON login called with username={request_data.username}")

        # Определяем тип сессии БД
        is_async = inspect.iscoroutinefunction(
            db.__class__.__aenter__
            if hasattr(db.__class__, '__aenter__')
            else lambda: None
        )

        if is_async:
            # Async session
            stmt = select(User).where(
                (User.username == request_data.username)
                | (User.email == request_data.username)
            )
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
        else:
            # Sync session
            user = await run_in_threadpool(
                lambda: db.query(User)
                .filter(
                    (User.username == request_data.username)
                    | (User.email == request_data.username)
                )
                .first()
            )

        if not user:
            logger.warning(f"User not found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные",
            )

        logger.debug(f"User found: {user.username}")

        if not user.is_active:
            logger.warning(f"User is inactive")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь деактивирован",
            )

        # Проверяем пароль
        password_valid = verify_password(request_data.password, user.hashed_password)
        # logger.debug(f"Password valid: {password_valid}")

        if not password_valid:
            logger.warning(f"Invalid password")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные",
            )

        # Создаем токен
        access_token = create_access_token(data={"sub": str(user.id)})

        logger.info(f"Token created successfully")

        return JSONLoginResponse(
            access_token=access_token,
            token_type="bearer",
            user={
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception in JSON login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка входа: {str(e)}",
        )
