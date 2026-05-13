"""
Упрощенный endpoint авторизации без сложных зависимостей
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.services.auth_fallback_service import (
    AuthFallbackDomainError,
    AuthFallbackService,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
    service = AuthFallbackService(db)
    try:
        payload = service.login_with_user_model(
            username=request_data.username,
            password=request_data.password,
            remember_me=request_data.remember_me,
        )
        return SimpleLoginResponse(**payload)
    except AuthFallbackDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as exc:
        logger.warning(
            "Simple fallback login endpoint failed operation=%s error_type=%s",
            "simple_login",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from exc


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

