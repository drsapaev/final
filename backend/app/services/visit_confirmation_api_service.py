"""
API endpoints для подтверждения визитов через Telegram и PWA
Публичные эндпоинты без авторизации (используют токены)
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================


class TelegramConfirmRequest(BaseModel):
    token: str = Field(..., min_length=10)
    telegram_user_id: str | None = None
    telegram_username: str | None = None


class PWAConfirmRequest(BaseModel):
    token: str = Field(..., min_length=10)
    patient_phone: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None


class ConfirmationResponse(BaseModel):
    success: bool
    message: str
    visit_id: int
    status: str
    patient_name: str
    visit_date: str
    visit_time: str | None
    queue_numbers: list[dict[str, Any]] | None = None
    print_tickets: list[dict[str, Any]] | None = None


# ===================== TELEGRAM ПОДТВЕРЖДЕНИЕ =====================


@router.post("/telegram/visits/confirm", response_model=ConfirmationResponse)
def confirm_visit_by_telegram(
    request_body: TelegramConfirmRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Подтверждение визита через Telegram бот по токену
    Публичный эндпоинт без авторизации
    """
    service = VisitConfirmationService(db)
    source_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        result = service.confirm_by_telegram(
            token=request_body.token,
            telegram_user_id=request_body.telegram_user_id,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return ConfirmationResponse(**result)
    except VisitConfirmationDomainError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        ) from exc


# ===================== PWA ПОДТВЕРЖДЕНИЕ =====================


@router.post("/patient/visits/confirm", response_model=ConfirmationResponse)
def confirm_visit_by_pwa(
    request_body: PWAConfirmRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Подтверждение визита через PWA приложение по токену
    Публичный эндпоинт без авторизации
    """
    service = VisitConfirmationService(db)
    source_ip = request.client.host if request.client else request_body.ip_address
    user_agent = request.headers.get("user-agent") or request_body.user_agent

    try:
        result = service.confirm_by_pwa(
            token=request_body.token,
            patient_phone=request_body.patient_phone,
            source_ip=source_ip,
            user_agent=user_agent,
        )
        return ConfirmationResponse(**result)
    except VisitConfirmationDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


# ===================== ИНФОРМАЦИОННЫЕ ЭНДПОИНТЫ =====================


@router.get("/visits/info/{token}")
def get_visit_info_by_token(token: str, db: Session = Depends(get_db)):
    """
    Получение информации о визите по токену (без подтверждения)
    Для предварительного просмотра перед подтверждением
    """
    service = VisitConfirmationService(db)
    try:
        return service.get_visit_info(token)
    except VisitConfirmationDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
