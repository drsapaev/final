"""
API endpoints для подтверждения визитов через Telegram и PWA.
Публичные эндпоинты без авторизации (используют токены).
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
)

router = APIRouter()


class TelegramConfirmRequest(BaseModel):
    token: str = Field(..., min_length=10)
    telegram_user_id: Optional[str] = None
    telegram_username: Optional[str] = None


class PWAConfirmRequest(BaseModel):
    token: str = Field(..., min_length=10)
    patient_phone: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None


class ConfirmationResponse(BaseModel):
    success: bool
    message: str
    visit_id: int
    status: str
    patient_name: str
    visit_date: str
    visit_time: Optional[str]
    queue_numbers: Optional[Dict[str, Any]] = None
    print_tickets: Optional[List[Dict[str, Any]]] = None


def _raise_http_error(exc: VisitConfirmationDomainError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail, headers=exc.headers)


@router.post("/telegram/visits/confirm", response_model=ConfirmationResponse)
def confirm_visit_by_telegram(
    request_body: TelegramConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Подтверждение визита через Telegram бот по токену."""
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
        _raise_http_error(exc)


@router.post("/patient/visits/confirm", response_model=ConfirmationResponse)
def confirm_visit_by_pwa(
    request_body: PWAConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Подтверждение визита через PWA по токену."""
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
        _raise_http_error(exc)


@router.get("/visits/info/{token}")
def get_visit_info_by_token(token: str, db: Session = Depends(get_db)):
    """Получение информации о визите по токену (без подтверждения)."""
    service = VisitConfirmationService(db)

    try:
        return service.get_visit_info(token)
    except VisitConfirmationDomainError as exc:
        _raise_http_error(exc)
