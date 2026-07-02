"""
Упрощенный endpoint авторизации без сложных зависимостей
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import create_access_token
from app.core.security import verify_password
from app.db.session import get_db
from app.models.user import User
from app.repositories.simple_auth_api_repository import SimpleAuthApiRepository

router = APIRouter()
logger = logging.getLogger(__name__)



def _repo(db: Session) -> SimpleAuthApiRepository:
    return SimpleAuthApiRepository(db)

class SimpleLoginRequest(BaseModel):
    """Простая схема для входа"""
    username: str
    password: str
    remember_me: bool = False


class SimpleLoginResponse(BaseModel):
    """Простая схема ответа"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


@router.post("/simple-login", response_model=SimpleLoginResponse)
async def simple_login(
    request_data: SimpleLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Упрощенный вход в систему без сложных зависимостей
    """
    try:
        logger.debug(
            "Simple fallback login requested",
            extra={
                "login_identifier_kind": (
                    "email" if "@" in request_data.username else "username"
                ),
                "remember_me": bool(request_data.remember_me),
            },
        )

        # Ищем пользователя по username или email
        user = _repo(db).query(User).filter(
            (User.username == request_data.username) |
            (User.email == request_data.username)
        ).first()

        if not user:
            logger.info(
                "Simple fallback login rejected",
                extra={"reason": "user_not_found"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные"
            )

        logger.debug(
            "Simple fallback login user loaded",
            extra={"is_active": bool(user.is_active), "role": user.role},
        )

        if not user.is_active:
            logger.info(
                "Simple fallback login rejected",
                extra={"reason": "inactive_user", "role": user.role},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь деактивирован"
            )

        password_valid = verify_password(request_data.password, user.hashed_password)

        if not password_valid:
            logger.info(
                "Simple fallback login rejected",
                extra={"reason": "invalid_password", "role": user.role},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверные учетные данные"
            )

        # Создаем токен
        expires_delta = timedelta(hours=24 if request_data.remember_me else 8)
        access_token = create_access_token(
            data={"sub": str(user.id), "user_id": user.id, "username": user.username},
            expires_delta=expires_delta
        )

        expires_in = int(expires_delta.total_seconds())

        logger.info(
            "Simple fallback login succeeded",
            extra={"role": user.role, "expires_in": expires_in},
        )

        # Формируем данные пользователя
        user_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser
        }

        return SimpleLoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
            user=user_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Simple fallback login failed",
            extra={"exception_type": type(e).__name__},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка входа"
        )


@router.get("/me")
async def get_current_user_simple(
    db: Session = Depends(get_db),
    current_user: User = Depends(lambda: None)  # Временно отключено
):
    """
    Получить информацию о текущем пользователе
    """
    # Временная заглушка
    return {"message": "Endpoint /me временно недоступен"}

