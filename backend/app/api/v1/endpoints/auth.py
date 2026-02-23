# app/api/v1/endpoints/auth.py
"""
Auth endpoints: /login (OAuth2 password form) and /me (current profile).

This implementation is defensive: it supports get_db() returning either an
AsyncSession (async DB) or a sync Session/sessionmaker. The DB calls are
dispatched either by awaiting (async) or via run_in_threadpool (sync).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

# helpers from deps
from app.api.deps import get_current_user

# Import your project's DB session factory / dependency
# get_db should be a dependency that yields either an AsyncSession or sync Session
from app.db.session import get_db

# ORM user model
from app.models.user import User
from app.services.auth_api_service import AuthApiDomainError, AuthApiService

logger = logging.getLogger(__name__)

router = APIRouter()


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
    logger.info(f"Login attempt for username: {form_data.username}")
    try:
        return await AuthApiService(db).login_oauth_payload(
            username=form_data.username,
            password=form_data.password,
        )
    except AuthApiDomainError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


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
        payload = await AuthApiService(db).json_login_payload(
            username=request_data.username,
            password=request_data.password,
            remember_me=request_data.remember_me,
        )
        return JSONLoginResponse(
            access_token=payload["access_token"],
            token_type=payload["token_type"],
            user=payload["user"],
        )
    except AuthApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception in JSON login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка входа: {str(e)}",
        )
