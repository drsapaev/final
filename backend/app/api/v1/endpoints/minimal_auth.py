"""
Минимальный endpoint авторизации без зависимостей от сложных моделей
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.auth_fallback_service import (
    AuthFallbackDomainError,
    AuthFallbackService,
)

router = APIRouter()


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
    user: Dict[str, Any]


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
    service = AuthFallbackService(db)
    try:
        payload = service.login_with_sql_row(
            username=request_data.username,
            password=request_data.password,
            remember_me=request_data.remember_me,
        )
        return MinimalLoginResponse(**payload)
    except AuthFallbackDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка входа: {str(exc)}",
        ) from exc
