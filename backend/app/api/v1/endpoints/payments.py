"""
API endpoints для платежной системы
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import (
    PaymentStatus,  # ✅ SSOT: Используем enum из app.models.enums
)
from app.models.payment import Payment
from app.models.payment_webhook import (
    PaymentProvider,
    PaymentTransaction,
    PaymentWebhook,
)
from app.models.visit import Visit
from app.services.billing_service import BillingService
from app.services.payment_init_service import PaymentInitDomainError, PaymentInitService
from app.services.payment_providers.base import PaymentResult
from app.services.payment_providers.manager import PaymentProviderManager

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


# Инициализация менеджера провайдеров
payment_manager = None


def get_payment_manager() -> PaymentProviderManager:
    """Получение менеджера провайдеров платежей"""
    global payment_manager

    if payment_manager is None:
        # Конфигурация провайдеров из настроек
        config = {
            "click": {
                "enabled": getattr(
                    settings, "CLICK_ENABLED", True
                ),  # Включено для тестирования
                "service_id": getattr(settings, "CLICK_SERVICE_ID", "test_service"),
                "merchant_id": getattr(settings, "CLICK_MERCHANT_ID", "test_merchant"),
                "secret_key": getattr(settings, "CLICK_SECRET_KEY", "test_secret"),
                "base_url": getattr(
                    settings, "CLICK_BASE_URL", "https://api.click.uz/v2"
                ),
            },
            "payme": {
                "enabled": getattr(
                    settings, "PAYME_ENABLED", True
                ),  # Включено для тестирования
                "merchant_id": getattr(settings, "PAYME_MERCHANT_ID", "test_merchant"),
                "secret_key": getattr(settings, "PAYME_SECRET_KEY", "test_secret"),
                "base_url": getattr(
                    settings, "PAYME_BASE_URL", "https://checkout.paycom.uz"
                ),
                "api_url": getattr(settings, "PAYME_API_URL", "https://api.paycom.uz"),
            },
            "kaspi": {
                "enabled": getattr(
                    settings, "KASPI_ENABLED", True
                ),  # Включено для тестирования
                "merchant_id": getattr(settings, "KASPI_MERCHANT_ID", "test_merchant"),
                "secret_key": getattr(settings, "KASPI_SECRET_KEY", "test_secret"),
                "base_url": getattr(settings, "KASPI_BASE_URL", "https://kaspi.kz/pay"),
                "api_url": getattr(
                    settings, "KASPI_API_URL", "https://api.kaspi.kz/pay/v1"
                ),
            },
        }

        payment_manager = PaymentProviderManager(config)

    return payment_manager


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

    manager = get_payment_manager()
    provider_info = manager.get_provider_info()

    providers = []
    for code, info in provider_info.items():
        providers.append(
            ProviderInfo(
                name=info["name"],
                code=code,
                supported_currencies=info["supported_currencies"],
                is_active=True,
                features=info["features"],
            )
        )

    return ProvidersResponse(providers=providers)


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
        billing_service = BillingService(db)

        # Определяем visit_id
        visit_id = payment_request.visit_id
        if not visit_id and payment_request.appointment_id:
            # Если передан appointment_id, ищем связанный visit
            from app.models.appointment import Appointment

            appointment = (
                db.query(Appointment)
                .filter(Appointment.id == payment_request.appointment_id)
                .first()
            )
            if appointment:
                # Ищем visit по patient_id и дате
                from datetime import date

                visit = (
                    db.query(Visit)
                    .filter(
                        Visit.patient_id == appointment.patient_id,
                        Visit.visit_date
                        == (appointment.appointment_date or date.today()),
                    )
                    .first()
                )
                if visit:
                    visit_id = visit.id

        if not visit_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не указан visit_id или appointment_id",
            )

        # Создаем платеж через SSOT
        payment = billing_service.create_payment(
            visit_id=visit_id,
            amount=float(payment_request.amount),
            currency=payment_request.currency,
            method=payment_request.method,
            status=PaymentStatus.PAID.value,
            note=payment_request.note,
        )
        
        # =====================================================
        # ВАЖНО: Обновляем статус визита после оплаты
        # =====================================================
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if visit:
            # Проверяем, полностью ли оплачен визит
            from decimal import Decimal
            from app.models.visit import VisitService
            
            # Считаем общую сумму услуг визита
            total_cost = Decimal("0")
            visit_services = db.query(VisitService).filter(VisitService.visit_id == visit_id).all()
            for vs in visit_services:
                price = Decimal(str(vs.price)) if vs.price else Decimal("0")
                qty = vs.qty if vs.qty else 1
                total_cost += price * qty
            
            # Считаем уже оплаченную сумму
            from app.models.payment import Payment
            paid_payments = db.query(Payment).filter(
                Payment.visit_id == visit_id,
                Payment.status.in_(["paid", "completed"])
            ).all()
            total_paid = sum(p.amount for p in paid_payments)
            
            # Если оплачено >= стоимости услуг, обновляем статус визита
            if total_paid >= total_cost:
                visit.status = "paid"
                visit.discount_mode = "paid"
                db.commit()

        # Формируем ответ в том же формате, что и get_payments_list
        from app.models.patient import Patient
        from app.models.service import Service
        from app.models.visit import VisitService

        patient_name = None
        service_name = None
        appointment_time = None

        visit = db.query(Visit).filter(Visit.id == payment.visit_id).first()
        if visit:
            if visit.visit_time:
                appointment_time = visit.visit_time.strftime('%H:%M')
            elif visit.created_at:
                appointment_time = visit.created_at.strftime('%H:%M')

            if visit.patient_id:
                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )
                if patient:
                    patient_name = (
                        patient.short_name()
                        or f"{patient.first_name or ''} {patient.last_name or ''}".strip()
                    )

            first_service = (
                db.query(VisitService).filter(VisitService.visit_id == visit.id).first()
            )
            if first_service:
                service = (
                    db.query(Service)
                    .filter(Service.id == first_service.service_id)
                    .first()
                )
                if service:
                    service_name = service.name

        method = 'Наличные'
        if payment.provider:
            method = payment.provider.capitalize()
        elif payment.method:
            method = payment.method.capitalize()

        return {
            'id': payment.id,
            'payment_id': payment.id,
            'time': appointment_time
            or (payment.created_at.strftime('%H:%M') if payment.created_at else '—'),
            'patient': patient_name or 'Неизвестно',
            'service': service_name or 'Услуга',
            'amount': float(payment.amount),
            'method': method,
            'status': payment.status,
            'currency': payment.currency,
            'created_at': (
                payment.created_at.isoformat() if payment.created_at else None
            ),
            'paid_at': payment.paid_at.isoformat() if payment.paid_at else None,
        }

    except HTTPException:
        raise
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
    import logging

    logger = logging.getLogger(__name__)

    billing_service = BillingService(db)

    # Получаем платежи через SSOT
    payment_responses = billing_service.get_payments_list(
        visit_id=visit_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )

    # ✅ ЛОГИРОВАНИЕ: Для отладки - проверяем, что возвращаются реальные данные из БД
    logger.info(
        f"📊 Возвращено платежей: {len(payment_responses)}, фильтры: visit_id={visit_id}, date_from={date_from}, date_to={date_to}"
    )
    if payment_responses:
        logger.info(f"📊 Первый платеж (пример): {payment_responses[0]}")

    return PaymentListResponse(payments=payment_responses, total=len(payment_responses))


@router.get("/{payment_id}", response_model=PaymentStatusResponse)
def get_payment_status(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier", "Registrar", "Doctor", "Patient")),
) -> PaymentStatusResponse:
    """Получение статуса платежа"""

    # Получаем платеж из БД
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Платеж не найден"
        )

    # Если платеж онлайн и не завершен, проверяем статус у провайдера
    if (
        payment.provider
        and payment.provider_payment_id
        and payment.status
        in [PaymentStatus.PENDING.value, PaymentStatus.PROCESSING.value]
    ):

        manager = get_payment_manager()
        result = manager.check_payment_status(
            payment.provider, payment.provider_payment_id
        )

        if result.success and result.status != payment.status:
            # ✅ SSOT: Обновляем статус через update_payment_status()
            billing_service = BillingService(db)
            meta = {**(payment.provider_data or {}), **result.provider_data}
            billing_service.update_payment_status(
                payment_id=payment.id, new_status=result.status, meta=meta
            )

    return PaymentStatusResponse(
        payment_id=payment.id,
        status=payment.status,
        amount=payment.amount,
        currency=payment.currency,
        provider=payment.provider,
        provider_payment_id=payment.provider_payment_id,
        created_at=payment.created_at,
        paid_at=payment.paid_at,
        provider_data=payment.provider_data,
    )


@router.get("/visit/{visit_id}", response_model=PaymentListResponse)
def get_visit_payments(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier", "Registrar", "Doctor")),
) -> PaymentListResponse:
    """Получение всех платежей по визиту"""

    payments = db.query(Payment).filter(Payment.visit_id == visit_id).all()

    payment_responses = []
    for payment in payments:
        payment_data = {
            'payment_id': payment.id,
            'id': payment.id,
            'status': payment.status,
            'amount': float(payment.amount),
            'currency': payment.currency,
            'provider': payment.provider,
            'provider_payment_id': payment.provider_payment_id,
            'created_at': (
                payment.created_at.isoformat() if payment.created_at else None
            ),
            'paid_at': payment.paid_at.isoformat() if payment.paid_at else None,
            'provider_data': payment.provider_data,
        }
        payment_responses.append(payment_data)

    return PaymentListResponse(payments=payment_responses, total=len(payment_responses))


@router.post("/{payment_id}/cancel")
def cancel_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
) -> Dict[str, Any]:
    """Отмена платежа"""

    # Получаем платеж
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Платеж не найден"
        )

    # Проверяем возможность отмены
    if payment.status not in ["pending", "processing"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Платеж со статусом {payment.status} нельзя отменить",
        )

    # Если онлайн-платеж, пытаемся отменить у провайдера
    if payment.provider and payment.provider_payment_id:
        manager = get_payment_manager()
        result = manager.cancel_payment(payment.provider, payment.provider_payment_id)

        # ✅ SSOT: Используем update_payment_status() вместо прямого изменения
        billing_service = BillingService(db)

        if result.success:
            billing_service.update_payment_status(
                payment_id=payment.id,
                new_status=PaymentStatus.CANCELLED.value,
                meta={**(payment.provider_data or {}), **result.provider_data},
            )
        else:
            # Даже если провайдер не смог отменить, отмечаем как отмененный в нашей системе
            billing_service.update_payment_status(
                payment_id=payment.id,
                new_status=PaymentStatus.CANCELLED.value,
                meta={
                    **(payment.provider_data or {}),
                    "cancel_error": result.error_message,
                },
            )
    else:
        # ✅ SSOT: Обычный платеж - используем update_payment_status()
        billing_service = BillingService(db)
        billing_service.update_payment_status(
            payment_id=payment.id, new_status=PaymentStatus.CANCELLED.value
        )

    return {
        "success": True,
        "payment_id": payment.id,
        "status": payment.status,
        "message": "Платеж отменен",
    }


@router.post("/test-init", response_model=PaymentInitResponse)
def test_init_payment(
    payment_request: PaymentInitRequest, db: Session = Depends(get_db)
) -> PaymentInitResponse:
    """Тестовая инициализация платежа БЕЗ аутентификации"""

    try:
        # Получаем менеджер провайдеров
        payment_manager = get_payment_manager()

        # Создаем запись платежа в БД через SSOT
        billing_service = BillingService(db)
        payment = billing_service.create_payment(
            visit_id=payment_request.visit_id,
            amount=float(payment_request.amount),
            currency=payment_request.currency,
            method="online",
            status=PaymentStatus.PENDING.value,
            provider=payment_request.provider,
            commit=False,  # Не коммитим сразу, обновим после получения данных от провайдера
        )

        # Инициализируем платеж через провайдера
        result = payment_manager.create_payment(
            provider_name=payment_request.provider,
            amount=payment_request.amount,
            currency=payment_request.currency,
            order_id=str(payment.id),
            description=payment_request.description or f"Тестовый платеж #{payment.id}",
            return_url=payment_request.return_url
            or "http://localhost:5173/payment/success",
            cancel_url=payment_request.cancel_url
            or "http://localhost:5173/payment/cancel",
        )

        if result.success:
            # Обновляем данные платежа
            payment.provider_payment_id = result.payment_id
            payment.payment_url = result.payment_url
            # ✅ SSOT: Используем update_payment_status() вместо прямого изменения
            billing_service = BillingService(db)
            billing_service.update_payment_status(
                payment_id=payment.id,
                new_status=PaymentStatus.PROCESSING.value,  # initialized -> processing (более корректный статус)
            )

            return PaymentInitResponse(
                success=True,
                payment_id=payment.id,
                provider=payment_request.provider,
                amount=payment_request.amount,
                currency=payment_request.currency,
                payment_url=result.payment_url,
                provider_payment_id=result.payment_id,
                status="initialized",
                message="Тестовый платеж успешно инициализирован",
            )
        else:
            # ✅ SSOT: Ошибка инициализации - используем update_payment_status()
            billing_service = BillingService(db)
            billing_service.update_payment_status(
                payment_id=payment.id,
                new_status="failed",
                meta={"error": result.error_message},
            )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ошибка инициализации платежа: {result.error_message}",
            )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка инициализации платежа: {str(e)}",
        )


@router.get("/{payment_id}/receipt")
def generate_receipt(
    payment_id: int,
    format_type: str = "pdf",
    db: Session = Depends(get_db),
    current_user=Depends(deps.get_current_user),
):
    """Генерация квитанции об оплате"""

    try:
        # Получаем платеж
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Платеж не найден"
            )

        # Генерируем простую квитанцию
        receipt_data = {
            "payment_id": payment.id,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "status": payment.status,
            "provider": payment.provider,
            "created_at": payment.created_at.isoformat(),
            "description": "Оплата медицинских услуг",
        }

        # Для демо возвращаем данные квитанции
        return {
            "success": True,
            "receipt_data": receipt_data,
            "receipt_url": f"/api/v1/payments/{payment_id}/receipt/download",
            "format": format_type,
        }

    except HTTPException:
        raise
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

    try:
        from fastapi.responses import PlainTextResponse

        # Получаем платеж
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Платеж не найден"
            )

        # Генерируем текстовую квитанцию
        receipt_content = f"""
КВИТАНЦИЯ ОБ ОПЛАТЕ
===================

Номер платежа: {payment.id}
Дата: {payment.created_at.strftime('%d.%m.%Y %H:%M')}
Сумма: {payment.amount} {payment.currency}
Провайдер: {payment.provider.title()}
Статус: {payment.status.title()}

Описание: Оплата медицинских услуг

Спасибо за использование наших услуг!
        """.strip()

        return PlainTextResponse(
            content=receipt_content,
            headers={
                "Content-Disposition": f"attachment; filename=receipt_{payment_id}.txt"
            },
        )

    except HTTPException:
        raise
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
    try:
        from app.models.payment_invoice import PaymentInvoice

        # Создаем новый счет
        invoice = PaymentInvoice(
            amount=request.amount,
            currency=request.currency,
            provider=request.provider,
            status=PaymentStatus.PENDING.value,
            description=request.description,
            payment_method=request.provider,
            created_by_id=current_user.id,
        )

        db.add(invoice)
        db.commit()
        db.refresh(invoice)

        return PaymentInvoiceResponse(
            invoice_id=invoice.id,
            amount=invoice.amount,
            currency=invoice.currency,
            provider=invoice.provider,
            status=invoice.status,
            description=invoice.description,
            created_at=invoice.created_at,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания счета: {str(e)}",
        )


@router.get("/invoices/pending", response_model=List[PaymentInvoiceResponse])
async def get_pending_invoices(
    db: Session = Depends(get_db), current_user: Any = Depends(deps.get_current_user)
):
    """Получение списка неоплаченных счетов"""
    try:
        from app.models.payment_invoice import PaymentInvoice

        # Получаем неоплаченные счета
        invoices = (
            db.query(PaymentInvoice)
            .filter(PaymentInvoice.status.in_(["pending", "processing"]))
            .order_by(PaymentInvoice.created_at.desc())
            .limit(50)
            .all()
        )

        return [
            PaymentInvoiceResponse(
                invoice_id=invoice.id,
                amount=invoice.amount,
                currency=invoice.currency,
                provider=invoice.provider,
                status=invoice.status,
                description=invoice.description,
                created_at=invoice.created_at,
            )
            for invoice in invoices
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения счетов: {str(e)}",
        )
