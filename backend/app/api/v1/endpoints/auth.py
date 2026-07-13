# app/api/v1/endpoints/auth.py
"""
Auth endpoints: /login (OAuth2 password form) and /me (current profile).

This implementation is defensive: it supports get_db() returning either an
AsyncSession (async DB) or a sync Session/sessionmaker. The DB calls are
dispatched either by awaiting (async) or via run_in_threadpool (sync).
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

# helpers from deps
from app.api.deps import get_current_user
from app.core.config import settings

# Import your project's DB session factory / dependency
# get_db should be a dependency that yields either an AsyncSession or sync Session
from app.db.session import get_db

# ORM user model
from app.models.user import User
from app.services.auth_api_service import AuthApiDomainError, AuthApiService

logger = logging.getLogger(__name__)

router = APIRouter()


def _ensure_legacy_login_enabled() -> None:
    if not settings.ENABLE_FALLBACK_AUTH:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Legacy auth login endpoint is disabled. Use /api/v1/authentication/login.",
        )


@router.post("/login", response_model=Any)
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
    _ensure_legacy_login_enabled()
    logger.info("Legacy OAuth login endpoint used")
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
    # PR-27: include doctor specialty so frontend can route to the correct panel
    specialty = None
    doctor_id = None
    cabinet = None
    if hasattr(current_user, 'role') and current_user.role in ('Doctor', 'cardio', 'derma', 'dentist'):
        from app.db.session import SessionLocal
        from app.models.clinic import Doctor
        db = SessionLocal()
        try:
            doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
            if doctor:
                specialty = doctor.specialty
                doctor_id = doctor.id
                cabinet = doctor.cabinet
        finally:
            db.close()

    return {
        "id": getattr(current_user, "id", None),
        "username": getattr(current_user, "username", None),
        "full_name": getattr(current_user, "full_name", None),
        "email": getattr(current_user, "email", None),
        "role": getattr(current_user, "role", None),
        "is_active": getattr(current_user, "is_active", True),
        "is_superuser": getattr(current_user, "is_superuser", False),
        # PR-27: doctor-specific fields for specialty-based routing
        "specialty": specialty,
        "doctor_id": doctor_id,
        "cabinet": cabinet,
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
    user: dict[str, Any]


class CSRFTokenResponse(BaseModel):
    """Ответ для bootstrap CSRF-токена во frontend."""

    csrf_token: str


@router.get("/csrf-token", response_model=CSRFTokenResponse)
async def get_csrf_token(request: Request, response: Response) -> CSRFTokenResponse:
    """
    Возвращает CSRF-токен и дублирует его в cookie для frontend bootstrap.

    Даже если CSRF middleware отключен, endpoint нужен frontend-клиенту,
    чтобы не шуметь 404 в консоли при state-changing запросах.
    """
    # PR-30: secure flag must follow production status. Previously secure=False
    # always — cookie was sent over plain HTTP, allowing MITM interception.
    import os

    is_prod = os.getenv("ENV", "dev").lower() in ("prod", "production")

    token = request.cookies.get("csrf_token") or secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=False,
        secure=is_prod,
        samesite="lax",
        path="/",
        max_age=60 * 60 * 8,
    )
    return CSRFTokenResponse(csrf_token=token)


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
    _ensure_legacy_login_enabled()
    try:
        logger.info("Legacy JSON login endpoint used")
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
    except Exception as exc:
        logger.warning(
            "Legacy JSON login endpoint failed operation=%s error_type=%s",
            "json_login",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc
