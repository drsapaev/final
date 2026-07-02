"""
Минимальный endpoint авторизации без зависимостей от сложных моделей
"""

import logging
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import create_access_token
from app.core.security import verify_password
from app.db.session import get_db
from app.repositories.minimal_auth_api_repository import MinimalAuthApiRepository

router = APIRouter()
logger = logging.getLogger(__name__)



def _repo(db: Session) -> MinimalAuthApiRepository:
    return MinimalAuthApiRepository(db)

class MinimalLoginRequest(BaseModel):
    """Минимальная схема для входа"""

    username: str
    password: str
    remember_me: bool = False


class MinimalLoginResponse(BaseModel):
    """Минимальная схема ответа"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict[str, Any]


@router.options("/minimal-login")
async def minimal_login_options():
    """Обработка OPTIONS запроса для CORS"""
    return {"message": "OK"}


@router.post("/minimal-login", response_model=MinimalLoginResponse)
async def minimal_login(
    request_data: MinimalLoginRequest, db: Session = Depends(get_db)
):
    """
    Минимальный вход в систему без зависимостей от сложных моделей
    """
    try:
        logger.debug(
            "Minimal fallback login requested",
            extra={
                "login_identifier_kind": (
                    "email" if "@" in request_data.username else "username"
                ),
                "remember_me": bool(request_data.remember_me),
            },
        )

        # Используем прямой SQL запрос для избежания проблем с моделями
        result = _repo(db).execute(
            text(
                """
            SELECT id, username, email, full_name, role, is_active, is_superuser, hashed_password
            FROM users
            WHERE username = :username OR email = :username
        """
            ),
            {"username": request_data.username},
        )

        user_row = result.fetchone()

        if not user_row:
            logger.info(
                "Minimal fallback login rejected",
                extra={"reason": "user_not_found"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные",
            )

        (
            user_id,
            username,
            email,
            full_name,
            role,
            is_active,
            is_superuser,
            hashed_password,
        ) = user_row

        logger.debug(
            "Minimal fallback login user row loaded",
            extra={"is_active": bool(is_active), "role": role},
        )

        if not is_active:
            logger.info(
                "Minimal fallback login rejected",
                extra={"reason": "inactive_user", "role": role},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь деактивирован",
            )

        password_valid = verify_password(request_data.password, hashed_password)

        if not password_valid:
            logger.info(
                "Minimal fallback login rejected",
                extra={"reason": "invalid_password", "role": role},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные",
            )

        # Создаем токен
        expires_delta = timedelta(hours=24 if request_data.remember_me else 8)
        access_token = create_access_token(
            data={"sub": str(user_id), "user_id": user_id, "username": username},
            expires_delta=expires_delta,
        )

        expires_in = int(expires_delta.total_seconds())

        logger.info(
            "Minimal fallback login succeeded",
            extra={"role": role, "expires_in": expires_in},
        )

        # Формируем данные пользователя
        user_data = {
            "id": user_id,
            "username": username,
            "email": email,
            "full_name": full_name,
            "role": role,
            "is_active": is_active,
            "is_superuser": is_superuser,
        }

        return MinimalLoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            user=user_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Minimal fallback login failed",
            extra={"exception_type": type(e).__name__},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка входа",
        )
