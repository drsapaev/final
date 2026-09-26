"""
API endpoints для подтверждения визитов через Telegram и PWA.
Публичные эндпоинты без авторизации (используют токены).
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
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
    telegram_user_id: str | None = None
    telegram_username: str | None = None


class PWAConfirmRequest(BaseModel):
    token: str = Field(..., min_length=10)
    patient_phone: str | None = None
    user_agent: str | None = None
    ip_address: str | None = None


class VisitInfoRequest(BaseModel):
    token: str


class VisitInfoServiceItem(BaseModel):
    name: str
    code: str | None
    quantity: int
    price: float
    total: float


class VisitInfoResponse(BaseModel):
    """Patient-safe public visit card (GET/POST /visits/info).

    PR 3390 review P2 + PR 3407 delta review P2: deliberately does NOT
    include ``notes``. The card is bearer-token-addressed and public, so
    the internal clinical/admin field (``diagnosis: …``, cancel reasons,
    force-reopen audit lines) is dropped from the service projection
    itself, and BOTH routes (the new POST and the legacy GET) are
    additionally filtered through this model — defense in depth against
    a future regression re-adding the field to the shared card.
    """

    success: bool
    visit_id: int
    status: str
    patient_name: str
    doctor_name: str
    visit_date: str
    visit_time: str | None
    department: str | None
    discount_mode: str | None
    services: list[VisitInfoServiceItem]
    total_amount: float
    currency: str
    confirmation_expires_at: str | None


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
        if exc.status_code >= 500:
            # This service wraps raw exception text in its 5xx detail.
            # Do not expose that text on the public PWA confirmation route.
            raise HTTPException(
                status_code=exc.status_code,
                detail="Не удалось подтвердить визит",
                headers=exc.headers,
            ) from None
        _raise_http_error(exc)


@router.get("/visits/info/{token}", response_model=VisitInfoResponse)
def get_visit_info_by_token(
    token: str, response: Response, db: Session = Depends(get_db)
):
    """Получение информации о визите по токену (без подтверждения).

    PR 3407 delta review P2: the legacy GET returns the same patient-safe
    card as the POST — the raw ``dict[str, Any]`` response_model is gone,
    so the shared service projection cannot leak internal fields here
    even if it regresses.

    PR 3417 review residual P2: the card is bearer-capability PHI, so the
    response is marked ``Cache-Control: private, no-store`` (same policy
    as dental clinical content), and the 5xx error path is sanitized
    exactly like the POST's — the service wraps raw exception text
    (SQLAlchemy/DB internals) into its 500 detail, which must never
    reach a public bearer-token caller.
    """
    # Bearer-capability PHI must live only in the current response: keep
    # browsers and intermediaries from caching the visit card.
    response.headers["Cache-Control"] = "private, no-store"
    service = VisitConfirmationService(db)

    try:
        return service.get_visit_info(token)
    except VisitConfirmationDomainError as exc:
        # Mirror the POST route: 5xx details from this service carry raw
        # exception text; publish a generic message instead.
        if exc.status_code >= 500:
            raise HTTPException(
                status_code=exc.status_code,
                detail="Не удалось получить информацию о визите",
                headers=exc.headers,
            ) from None
        _raise_http_error(exc)
    except Exception:
        raise HTTPException(
            status_code=500, detail="Не удалось получить информацию о визите"
        ) from None


@router.post("/visits/info", response_model=VisitInfoResponse)
def post_visit_info_by_token(
    request_body: VisitInfoRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Read a public visit card without putting its bearer token in the URL."""
    # Same PHI no-store policy as the legacy GET (PR 3417 review residual P2).
    response.headers["Cache-Control"] = "private, no-store"
    service = VisitConfirmationService(db)

    try:
        return service.get_visit_info(request_body.token)
    except VisitConfirmationDomainError as exc:
        # The service includes raw exception text in its 5xx detail; both
        # public routes now publish the same generic message (the legacy
        # GET mirrors this sanitization since the PR 3417 review).
        detail = (
            "Не удалось получить информацию о визите"
            if exc.status_code >= 500
            else exc.detail
        )
        raise HTTPException(
            status_code=exc.status_code, detail=detail, headers=exc.headers
        ) from None
    except Exception:
        raise HTTPException(
            status_code=500, detail="Не удалось получить информацию о визите"
        ) from None
