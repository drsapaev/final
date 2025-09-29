"""
API endpoints для автоматического выставления счетов
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api import deps
from app.services.billing_service import BillingService
from app.models.billing import InvoiceStatus, InvoiceType, PaymentMethod, RecurrenceType
from app.models.user import User


router = APIRouter()


# === Pydantic схемы ===

class InvoiceItemCreate(BaseModel):
    service_id: Optional[int] = None
    description: str = Field(..., min_length=1, max_length=500)
    quantity: float = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)
    discount_rate: float = Field(0, ge=0, le=100)
    notes: Optional[str] = None


class InvoiceCreate(BaseModel):
    patient_id: int
    visit_id: Optional[int] = None
    appointment_id: Optional[int] = None
    invoice_type: InvoiceType = InvoiceType.STANDARD
    items: List[InvoiceItemCreate] = Field(..., min_items=1)
    description: Optional[str] = None
    notes: Optional[str] = None
    payment_terms: Optional[str] = None
    due_days: int = Field(30, ge=1, le=365)
    auto_send: bool = False
    send_reminders: bool = True
    # Периодические счета
    is_recurring: bool = False
    recurrence_type: Optional[RecurrenceType] = None
    recurrence_interval: int = Field(1, ge=1)


class InvoiceUpdate(BaseModel):
    description: Optional[str] = None
    notes: Optional[str] = None
    payment_terms: Optional[str] = None
    due_date: Optional[datetime] = None
    auto_send: Optional[bool] = None
    send_reminders: Optional[bool] = None
    status: Optional[InvoiceStatus] = None


class PaymentCreate(BaseModel):
    invoice_id: int
    amount: float = Field(..., gt=0)
    payment_method: PaymentMethod
    reference_number: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    notes: Optional[str] = None


class InvoiceTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    template_content: str = Field(..., min_length=1)
    css_styles: Optional[str] = None
    is_default: bool = False
    auto_generate_for_visits: bool = False
    auto_generate_for_appointments: bool = False
    auto_send_email: bool = False
    auto_send_sms: bool = False


class BillingRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_event: str = Field(..., pattern=r'^(visit_completed|appointment_created|service_added)$')
    service_types: Optional[str] = None  # JSON строка
    patient_categories: Optional[str] = None  # JSON строка
    amount_threshold_min: Optional[float] = Field(None, ge=0)
    amount_threshold_max: Optional[float] = Field(None, ge=0)
    invoice_type: InvoiceType = InvoiceType.STANDARD
    payment_terms_days: int = Field(30, ge=1, le=365)
    auto_send: bool = False
    send_reminders: bool = True
    template_id: Optional[int] = None
    priority: int = Field(0, ge=0)


class BillingSettingsUpdate(BaseModel):
    invoice_number_prefix: Optional[str] = Field(None, max_length=10)
    default_tax_rate: Optional[float] = Field(None, ge=0, le=100)
    tax_included_in_price: Optional[bool] = None
    default_payment_terms_days: Optional[int] = Field(None, ge=1, le=365)
    overdue_threshold_days: Optional[int] = Field(None, ge=1, le=365)
    auto_generate_invoices: Optional[bool] = None
    auto_send_invoices: Optional[bool] = None
    auto_send_reminders: Optional[bool] = None
    reminder_days_before: Optional[str] = None
    reminder_days_after: Optional[str] = None
    currency_code: Optional[str] = Field(None, max_length=3)
    currency_symbol: Optional[str] = Field(None, max_length=5)
    company_name: Optional[str] = Field(None, max_length=255)
    company_address: Optional[str] = None
    company_phone: Optional[str] = Field(None, max_length=50)
    company_email: Optional[str] = Field(None, max_length=100)
    company_website: Optional[str] = Field(None, max_length=100)


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    patient_id: int
    visit_id: Optional[int]
    appointment_id: Optional[int]
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
    due_date: Optional[datetime]
    paid_date: Optional[datetime]
    description: Optional[str]
    notes: Optional[str]
    is_auto_generated: bool
    is_recurring: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentResponse(BaseModel):
    id: int
    payment_number: str
    invoice_id: int
    patient_id: int
    amount: float
    payment_method: str
    payment_date: datetime
    reference_number: Optional[str]
    description: Optional[str]
    is_confirmed: bool
    confirmed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# === API endpoints ===

@router.post("/invoices", response_model=InvoiceResponse)
def create_invoice(
    invoice_data: InvoiceCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Создать счет"""
    service = BillingService(db)
    
    try:
        # Преобразуем данные позиций
        services = []
        for item in invoice_data.items:
            services.append({
                'service_id': item.service_id,
                'description': item.description,
                'quantity': item.quantity,
                'unit_price': item.unit_price,
                'discount_rate': item.discount_rate,
                'notes': item.notes
            })
        
        invoice = service.create_invoice(
            patient_id=invoice_data.patient_id,
            services=services,
            visit_id=invoice_data.visit_id,
            appointment_id=invoice_data.appointment_id,
            invoice_type=invoice_data.invoice_type,
            due_days=invoice_data.due_days,
            auto_send=invoice_data.auto_send,
            created_by=current_user.id
        )
        
        # Настраиваем периодичность если нужно
        if invoice_data.is_recurring:
            invoice.is_recurring = True
            invoice.recurrence_type = invoice_data.recurrence_type
            invoice.recurrence_interval = invoice_data.recurrence_interval
            invoice.next_invoice_date = service._calculate_next_recurrence_date(
                invoice.issue_date,
                invoice_data.recurrence_type,
                invoice_data.recurrence_interval
            )
            db.commit()
        
        # Создаем напоминания
        if invoice_data.send_reminders:
            service.create_payment_reminders(invoice.id)
        
        return invoice
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/invoices", response_model=List[InvoiceResponse])
def get_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = None,
    status: Optional[InvoiceStatus] = None,
    invoice_type: Optional[InvoiceType] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Получить список счетов"""
    from app.models.billing import Invoice
    
    query = db.query(Invoice)
    
    if patient_id:
        query = query.filter(Invoice.patient_id == patient_id)
    if status:
        query = query.filter(Invoice.status == status)
    if invoice_type:
        query = query.filter(Invoice.invoice_type == invoice_type)
    if date_from:
        query = query.filter(Invoice.issue_date >= date_from)
    if date_to:
        query = query.filter(Invoice.issue_date <= date_to)
    
    invoices = query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()
    return invoices


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Получить счет по ID"""
    from app.models.billing import Invoice
    
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Счет не найден")
    
    return invoice


@router.put("/invoices/{invoice_id}", response_model=InvoiceResponse)
def update_invoice(
    invoice_id: int,
    invoice_data: InvoiceUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Обновить счет"""
    from app.models.billing import Invoice
    
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Счет не найден")
    
    # Обновляем поля
    for field, value in invoice_data.dict(exclude_unset=True).items():
        setattr(invoice, field, value)
    
    db.commit()
    db.refresh(invoice)
    return invoice


@router.delete("/invoices/{invoice_id}")
def delete_invoice(
    invoice_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Удалить счет"""
    from app.models.billing import Invoice
    
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Счет не найден")
    
    # Можно удалять только черновики
    if invoice.status != InvoiceStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Можно удалять только черновики")
    
    db.delete(invoice)
    db.commit()
    return {"message": "Счет удален"}


@router.get("/invoices/{invoice_id}/html")
def get_invoice_html(
    invoice_id: int,
    template_id: Optional[int] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Получить HTML счета"""
    service = BillingService(db)
    
    try:
        html_content = service.generate_invoice_html(invoice_id, template_id)
        return {"html": html_content}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invoices/{invoice_id}/send")
def send_invoice(
    invoice_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
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
    current_user: User = Depends(deps.get_current_user)
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
            created_by=current_user.id
        )
        return payment
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/payments", response_model=List[PaymentResponse])
def get_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    invoice_id: Optional[int] = None,
    patient_id: Optional[int] = None,
    payment_method: Optional[PaymentMethod] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Получить список платежей"""
    from app.models.billing import Payment
    
    query = db.query(Payment)
    
    if invoice_id:
        query = query.filter(Payment.invoice_id == invoice_id)
    if patient_id:
        query = query.filter(Payment.patient_id == patient_id)
    if payment_method:
        query = query.filter(Payment.payment_method == payment_method)
    if date_from:
        query = query.filter(Payment.payment_date >= date_from)
    if date_to:
        query = query.filter(Payment.payment_date <= date_to)
    
    payments = query.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()
    return payments


@router.post("/auto-generate/visit/{visit_id}")
def auto_generate_invoice_for_visit(
    visit_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Автоматически создать счет для визита"""
    service = BillingService(db)
    
    invoice = service.auto_generate_invoice_for_visit(visit_id)
    
    if invoice:
        return {"message": f"Счет {invoice.invoice_number} создан", "invoice_id": invoice.id}
    else:
        return {"message": "Счет не создан - нет подходящих правил или услуг"}


@router.post("/auto-generate/appointment/{appointment_id}")
def auto_generate_invoice_for_appointment(
    appointment_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Автоматически создать счет для записи"""
    service = BillingService(db)
    
    invoice = service.auto_generate_invoice_for_appointment(appointment_id)
    
    if invoice:
        return {"message": f"Счет {invoice.invoice_number} создан", "invoice_id": invoice.id}
    else:
        return {"message": "Счет не создан - нет подходящих правил или услуг"}


@router.post("/process-recurring")
def process_recurring_invoices(
    background_tasks: BackgroundTasks,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
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
    current_user: User = Depends(deps.get_current_user)
):
    """Отправить напоминания об оплате"""
    service = BillingService(db)
    
    # Добавляем задачу в фон
    background_tasks.add_task(service.send_due_reminders)
    
    return {"message": "Отправка напоминаний запущена"}


@router.get("/settings")
def get_billing_settings(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
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
        "company_website": settings.company_website
    }


@router.put("/settings")
def update_billing_settings(
    settings_data: BillingSettingsUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Обновить настройки биллинга"""
    service = BillingService(db)
    settings = service.get_billing_settings()
    
    # Обновляем поля
    for field, value in settings_data.dict(exclude_unset=True).items():
        setattr(settings, field, value)
    
    settings.updated_by = current_user.id
    
    db.commit()
    return {"message": "Настройки обновлены"}


@router.get("/analytics")
def get_billing_analytics(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Получить аналитику по счетам"""
    from app.models.billing import Invoice, Payment
    from sqlalchemy import func
    
    # Базовые фильтры
    invoice_query = db.query(Invoice)
    payment_query = db.query(Payment)
    
    if date_from:
        invoice_query = invoice_query.filter(Invoice.issue_date >= date_from)
        payment_query = payment_query.filter(Payment.payment_date >= date_from)
    if date_to:
        invoice_query = invoice_query.filter(Invoice.issue_date <= date_to)
        payment_query = payment_query.filter(Payment.payment_date <= date_to)
    
    # Статистика по счетам
    total_invoices = invoice_query.count()
    total_amount = invoice_query.with_entities(func.sum(Invoice.total_amount)).scalar() or 0
    paid_amount = invoice_query.filter(Invoice.status == InvoiceStatus.PAID).with_entities(func.sum(Invoice.total_amount)).scalar() or 0
    overdue_amount = invoice_query.filter(Invoice.status == InvoiceStatus.OVERDUE).with_entities(func.sum(Invoice.balance)).scalar() or 0
    
    # Статистика по платежам
    total_payments = payment_query.count()
    payments_amount = payment_query.with_entities(func.sum(Payment.amount)).scalar() or 0
    
    # Статистика по статусам
    status_stats = db.query(
        Invoice.status,
        func.count(Invoice.id).label('count'),
        func.sum(Invoice.total_amount).label('amount')
    ).group_by(Invoice.status).all()
    
    return {
        "period": {
            "date_from": date_from,
            "date_to": date_to
        },
        "summary": {
            "total_invoices": total_invoices,
            "total_amount": total_amount,
            "paid_amount": paid_amount,
            "overdue_amount": overdue_amount,
            "total_payments": total_payments,
            "payments_amount": payments_amount,
            "collection_rate": (paid_amount / total_amount * 100) if total_amount > 0 else 0
        },
        "status_breakdown": [
            {
                "status": stat.status,
                "count": stat.count,
                "amount": stat.amount or 0
            }
            for stat in status_stats
        ]
    }
