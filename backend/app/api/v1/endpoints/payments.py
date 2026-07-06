"""
API endpoints для платежной системы
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.clinic import Doctor
from app.models.payment import Payment
from app.models.visit import Visit
from app.services.payment_cancel_service import (
    PaymentCancelDomainError,
    PaymentCancelService,
)
from app.services.payment_create_service import (
    PaymentCreateDomainError,
    PaymentCreateService,
)
from app.services.payment_init_service import PaymentInitDomainError, PaymentInitService
from app.services.payment_invoice_service import (
    PaymentInvoiceDomainError,
    PaymentInvoiceService,
)
from app.services.payment_provider_manager_factory import get_payment_manager
from app.services.payment_read_service import PaymentReadDomainError, PaymentReadService
from app.services.payment_test_init_service import (
    PaymentTestInitDomainError,
    PaymentTestInitService,
)

router = APIRouter()


def _ensure_patient_payment_access(db: Session, payment_id: int, current_user) -> None:
    if getattr(current_user, "role", None) != "Patient":
        return
    if not getattr(current_user, "patient", None):
        raise HTTPException(status_code=403, detail="Access denied")

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Платеж не найден")

    visit = db.query(Visit).filter(Visit.id == payment.visit_id).first()
    if not visit or visit.patient_id != current_user.patient.id:
        raise HTTPException(status_code=403, detail="Access denied")

# ===================== МОДЕЛИ ДЛЯ МОДУЛЯ ОПЛАТЫ =====================


def _ensure_doctor_visit_payment_access(
    db: Session, visit: Visit | None, current_user
) -> None:
    if not visit:
        raise HTTPException(status_code=403, detail="Access denied")

    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id, Doctor.active.is_(True))
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=403, detail="Access denied")
    if visit.doctor_id == doctor.id:
        return

    assigned_doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
    # Legacy writers sometimes stored User.id in visits.doctor_id. Preserve that
    # compatibility only when the value does not point to another Doctor row.
    if not assigned_doctor and visit.doctor_id == current_user.id:
        return
    if assigned_doctor and assigned_doctor.user_id == current_user.id:
        return

    raise HTTPException(status_code=403, detail="Access denied")


def _ensure_visit_payment_access(db: Session, visit_id: int, current_user) -> Visit:
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    role = getattr(current_user, "role", None)
    if role == "Patient":
        if not getattr(current_user, "patient", None):
            raise HTTPException(status_code=403, detail="Access denied")
        if visit.patient_id != current_user.patient.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif role == "Doctor":
        _ensure_doctor_visit_payment_access(db, visit, current_user)

    return visit


def _ensure_payment_read_access(db: Session, payment_id: int, current_user) -> None:
    if getattr(current_user, "role", None) not in {"Patient", "Doctor"}:
        return

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if not payment.visit_id:
        raise HTTPException(status_code=403, detail="Access denied")
    _ensure_visit_payment_access(db, payment.visit_id, current_user)


class PaymentInvoiceCreateRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Сумма к оплате")
    currency: str = Field(default="UZS", description="Валюта")
    provider: str = Field(
        ..., pattern="^(click|payme)$", description="Платежный провайдер"
    )
    description: str | None = Field(None, description="Описание платежа")
    patient_info: dict[str, Any] | None = Field(
        None, description="Информация о пациенте"
    )


class PaymentInvoiceResponse(BaseModel):
    invoice_id: int
    amount: float
    currency: str
    provider: str
    status: str
    description: str | None
    created_at: datetime


class PendingInvoicesResponse(BaseModel):
    invoices: list[PaymentInvoiceResponse]


# Pydantic модели
class PaymentInitRequest(BaseModel):
    """Запрос на инициализацию платежа"""

    visit_id: int = Field(..., description="ID визита")
    provider: str = Field(..., description="Провайдер платежа (click, payme, kaspi)")
    amount: float = Field(..., gt=0, description="Сумма платежа")
    currency: str = Field(default="UZS", description="Валюта платежа")
    description: str | None = Field(None, description="Описание платежа")
    return_url: str | None = Field(None, description="URL возврата при успехе")
    cancel_url: str | None = Field(None, description="URL возврата при отмене")


class PaymentInitResponse(BaseModel):
    """Ответ на инициализацию платежа"""

    success: bool
    payment_id: int | None = None
    provider_payment_id: str | None = None
    payment_url: str | None = None
    status: str | None = None
    error_message: str | None = None


class PaymentStatusResponse(BaseModel):
    """Ответ на запрос статуса платежа"""

    payment_id: int
    status: str
    amount: float
    currency: str
    provider: str | None = None
    provider_payment_id: str | None = None
    created_at: datetime
    paid_at: datetime | None = None
    provider_data: dict[str, Any] | None = None


class PaymentListResponse(BaseModel):
    """Список платежей"""

    payments: list[dict[str, Any]]  # Используем Dict для гибкости формата данных
    total: int


class ProviderInfo(BaseModel):
    """Информация о провайдере"""

    name: str
    code: str
    supported_currencies: list[str]
    is_active: bool
    features: dict[str, bool]


class ProvidersResponse(BaseModel):
    """Список доступных провайдеров"""

    providers: list[ProviderInfo]


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

    visit_id: int | None = Field(None, description="ID визита")
    appointment_id: int | None = Field(None, description="ID записи (appointment)")
    amount: float = Field(..., gt=0, description="Сумма платежа")
    currency: str = Field(default="UZS", description="Валюта платежа")
    method: str = Field(default="cash", description="Метод оплаты (cash, card)")
    note: str | None = Field(None, description="Примечание")


@router.post("/", response_model=dict[str, Any])
def create_payment(
    request: Request,
    payment_request: PaymentCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
) -> dict[str, Any]:
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
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/", response_model=PaymentListResponse)
def list_payments(
    db: Session = Depends(get_db),
    visit_id: int | None = Query(None, description="Фильтр по ID визита"),
    date_from: str | None = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user=Depends(deps.require_roles("Admin", "Cashier", "Registrar", "Doctor")),
) -> PaymentListResponse:
    """Получение списка платежей с фильтрацией (использует SSOT)"""
    if getattr(current_user, "role", None) == "Doctor":
        if visit_id is None:
            raise HTTPException(status_code=403, detail="Access denied")
        _ensure_visit_payment_access(db, visit_id, current_user)
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
    _ensure_payment_read_access(db, payment_id, current_user)
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
    _ensure_visit_payment_access(db, visit_id, current_user)
    service = PaymentReadService(db)
    return PaymentListResponse(**service.get_visit_payments(visit_id=visit_id))


@router.post("/{payment_id}/cancel")
def cancel_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
) -> dict[str, Any]:
    """Отмена платежа"""
    service = PaymentCancelService(db, get_payment_manager())
    try:
        return service.cancel_payment(payment_id=payment_id)
    except PaymentCancelDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/test-init", response_model=PaymentInitResponse)
def test_init_payment(
    payment_request: PaymentInitRequest,
    db: Session = Depends(get_db),
    current_user=Depends(deps.require_roles("Admin", "Registrar", "Cashier")),
) -> PaymentInitResponse:
    """Test payment initialization — DISABLED unless ENABLE_TEST_PAYMENT_INIT=true.

    This endpoint bypasses audit logging and failure notifications.
    Enable only in dev/staging via ENABLE_TEST_PAYMENT_INIT env var.
    """
    if not getattr(settings, "ENABLE_TEST_PAYMENT_INIT", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Test payment init is disabled. Set ENABLE_TEST_PAYMENT_INIT=true to enable.",
        )
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
    current_user=Depends(deps.require_roles("Admin", "Cashier", "Registrar", "Doctor", "Patient")),
):
    """Генерация квитанции об оплате"""
    _ensure_payment_read_access(db, payment_id, current_user)
    service = PaymentReadService(db)
    try:
        return service.generate_receipt(payment_id=payment_id, format_type=format_type)
    except PaymentReadDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{payment_id}/receipt/download")
def download_receipt(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier", "Registrar", "Doctor", "Patient")),
):
    """Скачивание квитанции"""
    _ensure_payment_read_access(db, payment_id, current_user)
    service = PaymentReadService(db)
    try:
        pdf_bytes = service.build_receipt_pdf(payment_id=payment_id)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="receipt_{payment_id}.pdf"'
            },
        )

    except PaymentReadDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== ЭНДПОИНТЫ ДЛЯ МОДУЛЯ ОПЛАТЫ =====================


@router.post("/invoice/create", response_model=PaymentInvoiceResponse)
async def create_payment_invoice(
    request: PaymentInvoiceCreateRequest,
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.require_roles("Admin", "Registrar", "Cashier")),
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
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/invoices/pending", response_model=list[PaymentInvoiceResponse])
async def get_pending_invoices(
    db: Session = Depends(get_db),
    current_user: Any = Depends(deps.require_roles("Admin", "Registrar", "Cashier")),
):
    """Получение списка неоплаченных счетов"""
    service = PaymentInvoiceService(db)
    try:
        invoices = service.list_pending_invoices(limit=50)
        return [PaymentInvoiceResponse(**invoice) for invoice in invoices]
    except PaymentInvoiceDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
