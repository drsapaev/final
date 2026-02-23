"""
API endpoints для платежной системы
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.services.payment_cancel_service import (
    PaymentCancelDomainError,
    PaymentCancelService,
)
from app.services.payment_create_service import (
    PaymentCreateDomainError,
    PaymentCreateService,
)
from app.services.payment_invoice_service import (
    PaymentInvoiceDomainError,
    PaymentInvoiceService,
)
from app.services.payment_init_service import PaymentInitDomainError, PaymentInitService
from app.services.payment_read_service import PaymentReadDomainError, PaymentReadService
from app.services.payment_test_init_service import (
    PaymentTestInitDomainError,
    PaymentTestInitService,
)
from app.services.payment_provider_manager_factory import get_payment_manager

router = APIRouter()

# ===================== МОДЕЛИ ДЛЯ МОДУЛЯ ОПЛАТЫ =====================


class PaymentInvoiceCreateRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Сумма к оплате")
    currency: str = Field(default="UZS", description="Валюта")
    provider: str = Field(
        ..., pattern="^(click|payme)$", description="Платежный провайдер"
    )
    description: Optional[str] = Field(None, description="Описание платежа")
    patient_info: Optional[Dict[str, Any]] = Field(
        None, description="Информация о пациенте"
    )


class PaymentInvoiceResponse(BaseModel):
    invoice_id: int
    amount: float
    currency: str
    provider: str
    status: str
    description: Optional[str]
    created_at: datetime


class PendingInvoicesResponse(BaseModel):
    invoices: List[PaymentInvoiceResponse]


# Pydantic модели
class PaymentInitRequest(BaseModel):
    """Запрос на инициализацию платежа"""

    visit_id: int = Field(..., description="ID визита")
    provider: str = Field(..., description="Провайдер платежа (click, payme, kaspi)")
    amount: float = Field(..., gt=0, description="Сумма платежа")
    currency: str = Field(default="UZS", description="Валюта платежа")
    description: Optional[str] = Field(None, description="Описание платежа")
    return_url: Optional[str] = Field(None, description="URL возврата при успехе")
    cancel_url: Optional[str] = Field(None, description="URL возврата при отмене")


class PaymentInitResponse(BaseModel):
    """Ответ на инициализацию платежа"""

    success: bool
    payment_id: Optional[int] = None
    provider_payment_id: Optional[str] = None
    payment_url: Optional[str] = None
    status: Optional[str] = None
    error_message: Optional[str] = None


class PaymentStatusResponse(BaseModel):
    """Ответ на запрос статуса платежа"""

    payment_id: int
    status: str
    amount: float
    currency: str
    provider: Optional[str] = None
    provider_payment_id: Optional[str] = None
    created_at: datetime
    paid_at: Optional[datetime] = None
    provider_data: Optional[Dict[str, Any]] = None


class PaymentListResponse(BaseModel):
    """Список платежей"""

    payments: List[Dict[str, Any]]  # Используем Dict для гибкости формата данных
    total: int


class ProviderInfo(BaseModel):
    """Информация о провайдере"""

    name: str
    code: str
    supported_currencies: List[str]
    is_active: bool
    features: Dict[str, bool]


class ProvidersResponse(BaseModel):
    """Список доступных провайдеров"""

    providers: List[ProviderInfo]


# API Endpoints


@router.get("/providers", response_model=ProvidersResponse)
def get_available_providers(db: Session = Depends(get_db)) -> ProvidersResponse:
    """Получение списка доступных провайдеров платежей"""
    service = PaymentReadService(db, get_payment_manager())
    try:
        return ProvidersResponse(**service.get_available_providers())
    except PaymentReadDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/init", response_model=PaymentInitResponse)
def init_payment(
    request: Request,
    payment_request: PaymentInitRequest,
    db: Session = Depends(get_db),
    current_user=Depends(deps.require_roles("Admin", "Registrar", "Cashier")),
) -> PaymentInitResponse:
    """Инициализация платежа"""

    service = PaymentInitService(db, get_payment_manager())

    try:
        result = service.init_payment(
            request=request,
            current_user_id=current_user.id,
            visit_id=payment_request.visit_id,
            provider=payment_request.provider,
            amount=float(payment_request.amount),
            currency=payment_request.currency,
            description=payment_request.description,
            return_url=payment_request.return_url,
            cancel_url=payment_request.cancel_url,
        )
        return PaymentInitResponse(**result)
    except PaymentInitDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


class PaymentCreateRequest(BaseModel):
    """Запрос на создание платежа"""

    visit_id: Optional[int] = Field(None, description="ID визита")
    appointment_id: Optional[int] = Field(None, description="ID записи (appointment)")
    amount: float = Field(..., gt=0, description="Сумма платежа")
    currency: str = Field(default="UZS", description="Валюта платежа")
    method: str = Field(default="cash", description="Метод оплаты (cash, card)")
    note: Optional[str] = Field(None, description="Примечание")


@router.post("/", response_model=Dict[str, Any])
def create_payment(
    request: Request,
    payment_request: PaymentCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
) -> Dict[str, Any]:
    """Создание платежа (для кассы)"""
    try:
        service = PaymentCreateService(db)
        return service.create_payment(
            visit_id=payment_request.visit_id,
            appointment_id=payment_request.appointment_id,
            amount=float(payment_request.amount),
            currency=payment_request.currency,
            method=payment_request.method,
            note=payment_request.note,
        )
    except PaymentCreateDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания платежа: {str(e)}",
        )


@router.get("/", response_model=PaymentListResponse)
def list_payments(
    db: Session = Depends(get_db),
    visit_id: Optional[int] = Query(None, description="Фильтр по ID визита"),
    date_from: Optional[str] = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user=Depends(deps.require_roles("Admin", "Cashier", "Registrar", "Doctor")),
) -> PaymentListResponse:
    """Получение списка платежей с фильтрацией (использует SSOT)"""
    service = PaymentReadService(db)
    return PaymentListResponse(
        **service.list_payments(
            visit_id=visit_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    )


@router.get("/{payment_id}", response_model=PaymentStatusResponse)
def get_payment_status(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier", "Registrar", "Doctor", "Patient")),
) -> PaymentStatusResponse:
    """Получение статуса платежа"""
    service = PaymentReadService(db, get_payment_manager())
    try:
        return PaymentStatusResponse(**service.get_payment_status(payment_id=payment_id))
    except PaymentReadDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/visit/{visit_id}", response_model=PaymentListResponse)
def get_visit_payments(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier", "Registrar", "Doctor")),
) -> PaymentListResponse:
    """Получение всех платежей по визиту"""
    service = PaymentReadService(db)
    return PaymentListResponse(**service.get_visit_payments(visit_id=visit_id))


@router.post("/{payment_id}/cancel")
def cancel_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
) -> Dict[str, Any]:
    """Отмена платежа"""
    service = PaymentCancelService(db, get_payment_manager())
    try:
        return service.cancel_payment(payment_id=payment_id)
    except PaymentCancelDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/test-init", response_model=PaymentInitResponse)
def test_init_payment(
    payment_request: PaymentInitRequest, db: Session = Depends(get_db)
) -> PaymentInitResponse:
    """Тестовая инициализация платежа БЕЗ аутентификации"""
    service = PaymentTestInitService(db, get_payment_manager())
    try:
        result = service.init_test_payment(
            visit_id=payment_request.visit_id,
            provider=payment_request.provider,
            amount=float(payment_request.amount),
            currency=payment_request.currency,
            description=payment_request.description,
            return_url=payment_request.return_url,
            cancel_url=payment_request.cancel_url,
        )
        return PaymentInitResponse(**result)
    except PaymentTestInitDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/{payment_id}/receipt")
def generate_receipt(
    payment_id: int,
    format_type: str = "pdf",
    db: Session = Depends(get_db),
    current_user=Depends(deps.get_current_user),
):
    """Генерация квитанции об оплате"""
    service = PaymentReadService(db)
    try:
        return service.generate_receipt(payment_id=payment_id, format_type=format_type)
    except PaymentReadDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации квитанции: {str(e)}",
        )


@router.get("/{payment_id}/receipt/download")
def download_receipt(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(deps.get_current_user),
):
    """Скачивание квитанции"""
    service = PaymentReadService(db)
    try:
        from fastapi.responses import PlainTextResponse

        receipt_content = service.build_receipt_content(payment_id=payment_id)
        return PlainTextResponse(
            content=receipt_content,
            headers={
                "Content-Disposition": f"attachment; filename=receipt_{payment_id}.txt"
            },
        )

    except PaymentReadDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка скачивания квитанции: {str(e)}",
        )


# ===================== ЭНДПОИНТЫ ДЛЯ МОДУЛЯ ОПЛАТЫ =====================


@router.post("/invoice/create", response_model=PaymentInvoiceResponse)
async def create_payment_invoice(
    request: PaymentInvoiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.get_current_user),
):
    """Создание счета для оплаты из модуля оплаты"""
    service = PaymentInvoiceService(db)
    try:
        return PaymentInvoiceResponse(
            **service.create_invoice(
            amount=request.amount,
            currency=request.currency,
            provider=request.provider,
            description=request.description,
            patient_info=request.patient_info,
            created_by_id=getattr(current_user, "id", None),
        )
        )
    except PaymentInvoiceDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания счета: {str(e)}",
        )


@router.get("/invoices/pending", response_model=List[PaymentInvoiceResponse])
async def get_pending_invoices(
    db: Session = Depends(get_db), current_user: Any = Depends(deps.get_current_user)
):
    """Получение списка неоплаченных счетов"""
    service = PaymentInvoiceService(db)
    try:
        invoices = service.list_pending_invoices(limit=50)
        return [PaymentInvoiceResponse(**invoice) for invoice in invoices]
    except PaymentInvoiceDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения счетов: {str(e)}",
        )
