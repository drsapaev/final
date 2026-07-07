"""
API endpoints для автоматического выставления счетов
"""

import logging
from datetime import date, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.core.security import require_roles
from app.models.billing import InvoiceStatus, InvoiceType, PaymentMethod, RecurrenceType
from app.models.user import User
from app.services.billing_api_service import BillingApiDomainError, BillingApiService
from app.services.billing_service import BillingService

router = APIRouter()
logger = logging.getLogger(__name__)

BILLING_PUBLIC_ERROR = "Internal server error"
BILLING_VIEW_ROLES = ("Admin", "Registrar", "Cashier")
BILLING_WRITE_ROLES = ("Admin", "Cashier")
BILLING_ADMIN_ROLES = ("Admin",)


def _billing_http_error(exc: Exception, operation: str) -> HTTPException:
    logger.warning(
        "Billing endpoint failed operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )
    return HTTPException(status_code=500, detail=BILLING_PUBLIC_ERROR)


# === Pydantic схемы ===


class InvoiceItemCreate(BaseModel):
    service_id: int | None = None
    description: str = Field(..., min_length=1, max_length=500)
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    discount_rate: float = Field(0, ge=0, le=100)
    notes: str | None = None


class InvoiceCreate(BaseModel):
    patient_id: int
    visit_id: int | None = None
    appointment_id: int | None = None
    invoice_type: InvoiceType = InvoiceType.STANDARD
    items: list[InvoiceItemCreate] = Field(..., min_length=1)
    description: str | None = None
    notes: str | None = None
    payment_terms: str | None = None
    due_days: int = Field(30, ge=1, le=365)
    auto_send: bool = False
    send_reminders: bool = True
    # Периодические счета
    is_recurring: bool = False
    recurrence_type: RecurrenceType | None = None
    recurrence_interval: int = Field(1, ge=1)


class InvoiceUpdate(BaseModel):
    description: str | None = None
    notes: str | None = None
    payment_terms: str | None = None
    due_date: datetime | None = None
    auto_send: bool | None = None
    send_reminders: bool | None = None
    status: InvoiceStatus | None = None


class PaymentCreate(BaseModel):
    invoice_id: int
    amount: float = Field(..., gt=0)
    payment_method: PaymentMethod
    reference_number: str | None = Field(None, max_length=100)
    description: str | None = None
    notes: str | None = None


class InvoiceTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    template_content: str = Field(..., min_length=1)
    css_styles: str | None = None
    is_default: bool = False
    auto_generate_for_visits: bool = False
    auto_generate_for_appointments: bool = False
    auto_send_email: bool = False
    auto_send_sms: bool = False


class BillingRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    trigger_event: str = Field(
        ..., pattern=r'^(visit_completed|appointment_created|service_added)$'
    )
    service_types: str | None = None  # JSON строка
    patient_categories: str | None = None  # JSON строка
    amount_threshold_min: float | None = Field(None, ge=0)
    amount_threshold_max: float | None = Field(None, ge=0)
    invoice_type: InvoiceType = InvoiceType.STANDARD
    payment_terms_days: int = Field(30, ge=1, le=365)
    auto_send: bool = False
    send_reminders: bool = True
    template_id: int | None = None
    priority: int = Field(0, ge=0)


class BillingSettingsUpdate(BaseModel):
    invoice_number_prefix: str | None = Field(None, max_length=10)
    default_tax_rate: float | None = Field(None, ge=0, le=100)
    tax_included_in_price: bool | None = None
    default_payment_terms_days: int | None = Field(None, ge=1, le=365)
    overdue_threshold_days: int | None = Field(None, ge=1, le=365)
    auto_generate_invoices: bool | None = None
    auto_send_invoices: bool | None = None
    auto_send_reminders: bool | None = None
    reminder_days_before: str | None = None
    reminder_days_after: str | None = None
    currency_code: str | None = Field(None, max_length=3)
    currency_symbol: str | None = Field(None, max_length=5)
    company_name: str | None = Field(None, max_length=255)
    company_address: str | None = None
    company_phone: str | None = Field(None, max_length=50)
    company_email: str | None = Field(None, max_length=100)
    company_website: str | None = Field(None, max_length=100)


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    patient_id: int
    visit_id: int | None
    appointment_id: int | None
    invoice_type: str
    status: str
    subtotal: float
    tax_rate: float
    tax_amount: float
    discount_amount: float
    total_amount: float
    paid_amount: float
    balance: float
    issue_date: datetime
    due_date: datetime | None
    paid_date: datetime | None
    description: str | None
    notes: str | None
    is_auto_generated: bool
    is_recurring: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    id: int
    payment_number: str
    invoice_id: int
    patient_id: int
    amount: float
    payment_method: str
    payment_date: datetime
    reference_number: str | None
    description: str | None
    is_confirmed: bool
    confirmed_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# === API endpoints ===


@router.post("/invoices", response_model=InvoiceResponse)
def create_invoice(
    invoice_data: InvoiceCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_WRITE_ROLES)),
):
    """Создать счет"""
    service = BillingService(db)
    billing_api_service = BillingApiService(db)

    try:
        # Преобразуем данные позиций
        services = []
        for item in invoice_data.items:
            services.append(
                {
                    'service_id': item.service_id,
                    'description': item.description,
                    'quantity': item.quantity,
                    'unit_price': item.unit_price,
                    'discount_rate': item.discount_rate,
                    'notes': item.notes,
                }
            )

        invoice = service.create_invoice(
            patient_id=invoice_data.patient_id,
            services=services,
            visit_id=invoice_data.visit_id,
            appointment_id=invoice_data.appointment_id,
            invoice_type=invoice_data.invoice_type,
            due_days=invoice_data.due_days,
            auto_send=invoice_data.auto_send,
            created_by=current_user.id,
        )

        # Настраиваем периодичность если нужно
        if invoice_data.is_recurring:
            billing_api_service.configure_recurring_invoice(
                invoice=invoice,
                recurrence_type=invoice_data.recurrence_type,
                recurrence_interval=invoice_data.recurrence_interval,
                next_date_calculator=service._calculate_next_recurrence_date,
            )

        # Создаем напоминания
        if invoice_data.send_reminders:
            service.create_payment_reminders(invoice.id)

        return invoice
    except Exception as e:
        raise HTTPException(status_code=400, detail="Internal server error")


@router.get("/invoices", response_model=list[InvoiceResponse])
def get_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
    status: InvoiceStatus | None = None,
    invoice_type: InvoiceType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_VIEW_ROLES)),
):
    """Получить список счетов"""
    return BillingApiService(db).list_invoices(
        skip=skip,
        limit=limit,
        patient_id=patient_id,
        status=status,
        invoice_type=invoice_type,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_VIEW_ROLES)),
):
    """Получить счет по ID"""
    try:
        return BillingApiService(db).get_invoice_or_error(invoice_id=invoice_id)
    except BillingApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.put("/invoices/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: int,
    invoice_data: InvoiceUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_WRITE_ROLES)),
):
    """Обновить счет"""
    try:
        return BillingApiService(db).update_invoice(
            invoice_id=invoice_id,
            update_data=invoice_data.dict(exclude_unset=True),
        )
    except BillingApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.delete("/invoices/{invoice_id}")
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_WRITE_ROLES)),
):
    """Удалить счет"""
    try:
        BillingApiService(db).delete_invoice(invoice_id=invoice_id)
    except BillingApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return {"message": "Счет удален"}


@router.get("/invoices/{invoice_id}/html")
def get_invoice_html(
    invoice_id: int,
    template_id: int | None = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_VIEW_ROLES)),
):
    """Получить HTML счета"""
    service = BillingService(db)

    try:
        html_content = service.generate_invoice_html(invoice_id, template_id)
        return {"html": html_content}
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Internal server error")
    except Exception as e:
        raise _billing_http_error(e, "get_invoice_html") from e


@router.post("/invoices/{invoice_id}/send")
def send_invoice(
    invoice_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_WRITE_ROLES)),
):
    """Отправить счет пациенту"""
    service = BillingService(db)

    # Добавляем задачу в фон
    background_tasks.add_task(service.send_invoice, invoice_id)

    return {"message": "Счет добавлен в очередь отправки"}


@router.post("/payments", response_model=PaymentResponse)
def record_payment(
    payment_data: PaymentCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_WRITE_ROLES)),
):
    """Записать платеж"""
    service = BillingService(db)

    try:
        payment = service.record_payment(
            invoice_id=payment_data.invoice_id,
            amount=payment_data.amount,
            payment_method=payment_data.payment_method,
            reference_number=payment_data.reference_number,
            description=payment_data.description,
            created_by=current_user.id,
        )
        return payment
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Internal server error")
    except Exception as e:
        raise HTTPException(status_code=400, detail="Internal server error")


@router.get("/payments")
def get_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_VIEW_ROLES)),
):
    """Получить список платежей"""
    payments = BillingApiService(db).list_payments(
        skip=skip,
        limit=limit,
        date_from=date_from,
        date_to=date_to,
    )
    return BillingApiService(db).serialize_payments(payments)


@router.post("/auto-generate/visit/{visit_id}")
def auto_generate_invoice_for_visit(
    visit_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_WRITE_ROLES)),
):
    """Автоматически создать счет для визита"""
    service = BillingService(db)

    invoice = service.auto_generate_invoice_for_visit(visit_id)

    if invoice:
        return {
            "message": f"Счет {invoice.invoice_number} создан",
            "invoice_id": invoice.id,
        }
    else:
        return {"message": "Счет не создан - нет подходящих правил или услуг"}


@router.post("/auto-generate/appointment/{appointment_id}")
def auto_generate_invoice_for_appointment(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_WRITE_ROLES)),
):
    """Автоматически создать счет для записи"""
    service = BillingService(db)

    invoice = service.auto_generate_invoice_for_appointment(appointment_id)

    if invoice:
        return {
            "message": f"Счет {invoice.invoice_number} создан",
            "invoice_id": invoice.id,
        }
    else:
        return {"message": "Счет не создан - нет подходящих правил или услуг"}


@router.post("/process-recurring")
def process_recurring_invoices(
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_ADMIN_ROLES)),
):
    """Обработать периодические счета"""
    service = BillingService(db)

    # Добавляем задачу в фон
    background_tasks.add_task(service.create_recurring_invoices)

    return {"message": "Обработка периодических счетов запущена"}


@router.post("/send-reminders")
def send_payment_reminders(
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_WRITE_ROLES)),
):
    """Отправить напоминания об оплате"""
    service = BillingService(db)

    # Добавляем задачу в фон
    background_tasks.add_task(service.send_due_reminders)

    return {"message": "Отправка напоминаний запущена"}


@router.get("/settings")
def get_billing_settings(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_ADMIN_ROLES)),
):
    """Получить настройки биллинга"""
    service = BillingService(db)
    settings = service.get_billing_settings()

    return {
        "invoice_number_prefix": settings.invoice_number_prefix,
        "invoice_number_format": settings.invoice_number_format,
        "next_invoice_number": settings.next_invoice_number,
        "default_tax_rate": settings.default_tax_rate,
        "tax_included_in_price": settings.tax_included_in_price,
        "default_payment_terms_days": settings.default_payment_terms_days,
        "overdue_threshold_days": settings.overdue_threshold_days,
        "auto_generate_invoices": settings.auto_generate_invoices,
        "auto_send_invoices": settings.auto_send_invoices,
        "auto_send_reminders": settings.auto_send_reminders,
        "reminder_days_before": settings.reminder_days_before,
        "reminder_days_after": settings.reminder_days_after,
        "currency_code": settings.currency_code,
        "currency_symbol": settings.currency_symbol,
        "company_name": settings.company_name,
        "company_address": settings.company_address,
        "company_phone": settings.company_phone,
        "company_email": settings.company_email,
        "company_website": settings.company_website,
    }


@router.put("/settings")
def update_billing_settings(
    settings_data: BillingSettingsUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_ADMIN_ROLES)),
):
    """Обновить настройки биллинга"""
    service = BillingService(db)
    settings = service.get_billing_settings()
    BillingApiService(db).update_billing_settings(
        settings=settings,
        update_data=settings_data.dict(exclude_unset=True),
        updated_by=current_user.id,
    )
    return {"message": "Настройки обновлены"}


@router.get("/analytics")
def get_billing_analytics(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(require_roles(*BILLING_VIEW_ROLES)),
):
    """Получить аналитику по счетам"""
    return BillingApiService(db).get_billing_analytics(
        date_from=date_from,
        date_to=date_to,
    )
