"""
API endpoints для мастера регистрации с поддержкой корзины
Расширение существующего registrar_integration.py
"""

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import String, literal
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import clinic as crud_clinic
from app.crud import online_queue as crud_queue
from app.crud.appointment import appointment as crud_appointment
from app.models.clinic import ClinicSettings, Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.patient import Patient
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.notifications import notification_sender_service
from app.services.online_queue_new_service import (
    OnlineQueueNewDomainError,
    OnlineQueueNewService,
)
from app.services.payment_provider_manager_factory import get_payment_manager
from app.services.queue_service import queue_service
from app.services.registrar_edit_delta_service import (
    RegistrarEditDeltaItem,
    RegistrarEditDeltaService,
)
from app.services.registrar_wizard_queue_assignment_service import (
    RegistrarWizardQueueAssignmentService,
)
from app.services.service_mapping import get_service_code, normalize_service_code
from app.services.visits_api_service import VisitsApiService

logger = logging.getLogger(__name__)

router = APIRouter()


def _ensure_visit_doctor_access(db: Session, visit: Visit, current_user: User) -> None:
    if current_user.role == "Admin" or current_user.is_superuser:
        return
    if current_user.role != "Doctor":
        return

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
    # Legacy writers sometimes stored User.id in Visit.doctor_id. Keep that
    # compatibility only when the value is not another real Doctor row.
    if not assigned_doctor and visit.doctor_id == current_user.id:
        return
    if assigned_doctor and assigned_doctor.user_id == current_user.id:
        return

    raise HTTPException(status_code=403, detail="Access denied")

# ===================== СХЕМЫ ДЛЯ КОРЗИНЫ =====================


class ServiceItemRequest(BaseModel):
    service_id: int
    quantity: int = Field(default=1, ge=1)
    custom_price: Decimal | None = None  # Для врачебного переопределения цены


class VisitRequest(BaseModel):
    doctor_id: int | None = None  # Может быть None для лабораторных услуг
    services: list[ServiceItemRequest]
    visit_date: date
    visit_time: str | None = None  # HH:MM
    department: str | None = None
    notes: str | None = None


class CartRequest(BaseModel):
    patient_id: int
    visits: list[VisitRequest]
    discount_mode: str = Field(default="none")  # none|repeat|benefit|all_free
    payment_method: str = Field(default="cash")  # cash|card|online|click|payme
    all_free: bool = Field(default=False)  # Чекбокс "All Free"
    notes: str | None = None


class CartResponse(BaseModel):
    success: bool
    message: str
    invoice_id: int
    visit_ids: list[int]
    total_amount: Decimal
    queue_numbers: dict[
        int, list[dict]
    ]  # visit_id -> [{"queue_tag": str, "number": int, "queue_id": int}]
    print_tickets: list[dict[str, Any]]
    created_visits: list[dict[str, Any]] | None = (
        None  # Информация о созданных визитах
    )


class EditDeltaPatientData(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    birth_date: date | None = None
    sex: str | None = None
    address: str | None = None


class EditDeltaServiceItem(BaseModel):
    service_id: int
    quantity: int = Field(default=1, ge=1)
    specialist_id: int | None = None


class EditDeltaRequest(BaseModel):
    patient_id: int
    target_date: date = Field(default_factory=date.today)
    payment_method: str = Field(default="cash")
    discount_mode: str = Field(default="none")
    all_free: bool = Field(default=False)
    patient_data: EditDeltaPatientData | None = None
    services: list[EditDeltaServiceItem] = Field(default_factory=list)
    existing_queue_entry_ids: list[int] = Field(default_factory=list)
    # R-08 fix: optimistic locking — map of entry_id → ISO updated_at string.
    # Frontend передаёт updated_at каждой existing entry при последнем чтении.
    # Если какая-либо entry была изменена другим пользователем — 409 Conflict.
    expected_entry_updated_at: dict[int, str] = Field(default_factory=dict)


class EditDeltaResponse(BaseModel):
    success: bool
    message: str
    invoice_id: int | None = None
    visit_ids: list[int] = Field(default_factory=list)
    total_amount: Decimal = Decimal("0")
    queue_numbers: dict[int, list[dict[str, Any]]] = Field(default_factory=dict)
    print_tickets: list[dict[str, Any]] = Field(default_factory=list)
    created_visits: list[dict[str, Any]] = Field(default_factory=list)
    updated_queue_entries: list[dict[str, Any]] = Field(default_factory=list)


class MarkPaidRequest(BaseModel):
    # REG-AUDIT-28 P0-2: validate amount is positive and reasonable
    amount: Decimal | None = Field(None, gt=0, le=Decimal("1000000000"))
    method: str | None = Field(default="cash")


class RegistrarRecordRef(BaseModel):
    record_kind: str
    record_id: int


class RegistrarRecordActionRequest(BaseModel):
    action: str
    record_kind: str | None = None
    record_id: int | None = None
    records: list[RegistrarRecordRef] | None = None
    reason: str | None = None
    # REG-AUDIT-28 P0-2: validate amount is positive and reasonable
    amount: Decimal | None = Field(None, gt=0, le=Decimal("1000000000"))
    method: str | None = Field(default="cash")


class RegistrarRecordActionItemResponse(BaseModel):
    record_kind: str
    record_id: int
    success: bool
    skipped: bool = False
    status: str | None = None
    payment_status: str | None = None
    error: str | None = None
    result: dict[str, Any] | None = None


class RegistrarRecordActionResponse(BaseModel):
    action: str
    success: bool
    success_count: int
    skipped_count: int
    failed_count: int
    results: list[RegistrarRecordActionItemResponse]


class RepeatEligibilityCandidate(BaseModel):
    service_id: int
    doctor_id: int | None = None
    visit_date: date
    candidate_key: str | None = None


class RepeatEligibilityPreviewRequest(BaseModel):
    patient_id: int
    candidates: list[RepeatEligibilityCandidate] = Field(default_factory=list)


class RepeatEligibilityPreviewItem(BaseModel):
    candidate_key: str | None = None
    service_id: int
    doctor_id: int | None = None
    visit_date: date
    eligible: bool
    reason: str
    repeat_window_days: int
    repeat_discount_percent: int


class RepeatEligibilityPreviewResponse(BaseModel):
    patient_id: int
    items: list[RepeatEligibilityPreviewItem]


# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================


def _check_repeat_visit_eligibility(
    db: Session,
    patient_id: int,
    doctor_id: int,
    service_ids: list[int],
    days_window: int = 21,
) -> bool:
    """
    Проверка права на повторный визит (≤N дней у того же специалиста)
    """
    # Получаем консультации этого врача за последние N дней
    cutoff_date = date.today() - timedelta(days=days_window)

    recent_visits = (
        db.query(Visit)
        .filter(
            Visit.patient_id == patient_id,
            Visit.doctor_id == doctor_id,
            Visit.visit_date >= cutoff_date,
            Visit.status != "cancelled",
        )
        .all()
    )

    if not recent_visits:
        return False

    # Проверяем, есть ли среди выбранных услуг консультации
    consultation_services = (
        db.query(Service)
        .filter(Service.id.in_(service_ids), Service.is_consultation == True)
        .all()
    )

    return len(consultation_services) > 0


def _resolve_effective_discount_mode(cart_data: CartRequest) -> str:
    """All Free checkbox wins over the legacy discount_mode radio."""
    if cart_data.all_free or cart_data.discount_mode == "all_free":
        return "all_free"
    return cart_data.discount_mode or "none"


def _load_registration_discount_settings(db: Session) -> dict[str, Any]:
    """Load repeat/benefit settings with safe defaults."""
    defaults = {
        "repeat_visit_days": 21,
        "repeat_visit_discount": 0,
        "benefit_consultation_free": True,
        "all_free_auto_approve": False,
    }
    settings = defaults.copy()

    rows = (
        db.query(ClinicSettings)
        .filter(
            ClinicSettings.key.in_(
                [
                    "repeat_visit_days",
                    "repeat_visit_discount",
                    "benefit_consultation_free",
                    "all_free_auto_approve",
                ]
            )
        )
        .all()
    )

    for row in rows:
        if row.key in {"repeat_visit_days", "repeat_visit_discount"}:
            try:
                settings[row.key] = int(row.value)
            except (TypeError, ValueError):
                pass
        elif row.key in {"benefit_consultation_free", "all_free_auto_approve"}:
            settings[row.key] = bool(row.value)

    return settings


def _apply_service_discount(
    base_price: Decimal,
    discount_mode: str,
    settings: dict[str, Any],
    is_consultation: bool,
) -> Decimal:
    """Apply deterministic service pricing rules for the registrar cart."""
    if discount_mode == "all_free":
        return Decimal("0")

    if discount_mode == "repeat" and is_consultation:
        repeat_discount = Decimal(str(settings.get("repeat_visit_discount", 0) or 0))
        repeat_discount = max(Decimal("0"), min(repeat_discount, Decimal("100")))
        return (base_price * (Decimal("100") - repeat_discount) / Decimal("100")).quantize(
            Decimal("0.01")
        )

    if discount_mode == "benefit" and is_consultation:
        if settings.get("benefit_consultation_free", True):
            return Decimal("0")

    return base_price


def _visit_has_paid_payment(db: Session, visit_id: int) -> bool:
    """Payment truth comes from the payments table, not from discount_mode."""
    try:
        from app.models.payment import Payment

        payment_row = (
            db.query(Payment)
            .filter(Payment.visit_id == visit_id)
            .order_by(Payment.created_at.desc())
            .first()
        )
        return bool(
            payment_row
            and (str(payment_row.status).lower() == "paid" or payment_row.paid_at)
        )
    except Exception:
        return False


REGISTRATION_DISCOUNT_MODES = {"none", "repeat", "benefit", "all_free"}


def _normalize_registration_discount_mode(raw_value: str | None) -> str:
    normalized = str(raw_value or "none").strip().lower()
    if normalized in REGISTRATION_DISCOUNT_MODES:
        return normalized
    return "none"


def _resolve_payment_truth(
    db: Session,
    *,
    visit_id: int | None = None,
    legacy_paid_at: datetime | None = None,
) -> tuple[str, str | None]:
    if visit_id:
        try:
            from app.models.payment import Payment

            payment_row = (
                db.query(Payment)
                .filter(Payment.visit_id == visit_id)
                .order_by(Payment.created_at.desc())
                .first()
            )
            if payment_row:
                payment_status = (
                    "paid"
                    if (
                        str(getattr(payment_row, "status", "") or "").lower() == "paid"
                        or getattr(payment_row, "paid_at", None)
                    )
                    else "pending"
                )
                return payment_status, getattr(payment_row, "method", None) or None
        except Exception:
            logger.debug(
                "registrar_wizard: failed to resolve payment truth for visit %s",
                visit_id,
                exc_info=True,
            )

    return ("paid", None) if legacy_paid_at else ("pending", None)


def _build_repeat_eligibility_preview_item(
    db: Session,
    *,
    patient_id: int,
    candidate: RepeatEligibilityCandidate,
    repeat_visit_days: int,
    repeat_discount_percent: int,
) -> RepeatEligibilityPreviewItem:
    service = db.query(Service).filter(Service.id == candidate.service_id).first()

    if not service:
        return RepeatEligibilityPreviewItem(
            candidate_key=candidate.candidate_key,
            service_id=candidate.service_id,
            doctor_id=candidate.doctor_id,
            visit_date=candidate.visit_date,
            eligible=False,
            reason="Услуга не найдена",
            repeat_window_days=repeat_visit_days,
            repeat_discount_percent=repeat_discount_percent,
        )

    if not service.is_consultation:
        return RepeatEligibilityPreviewItem(
            candidate_key=candidate.candidate_key,
            service_id=candidate.service_id,
            doctor_id=candidate.doctor_id,
            visit_date=candidate.visit_date,
            eligible=False,
            reason="Повторная скидка доступна только для консультаций",
            repeat_window_days=repeat_visit_days,
            repeat_discount_percent=repeat_discount_percent,
        )

    if not candidate.doctor_id:
        return RepeatEligibilityPreviewItem(
            candidate_key=candidate.candidate_key,
            service_id=candidate.service_id,
            doctor_id=candidate.doctor_id,
            visit_date=candidate.visit_date,
            eligible=False,
            reason="Выберите врача для проверки повторной скидки",
            repeat_window_days=repeat_visit_days,
            repeat_discount_percent=repeat_discount_percent,
        )

    eligible = _check_repeat_visit_eligibility(
        db,
        patient_id,
        candidate.doctor_id,
        [candidate.service_id],
        days_window=repeat_visit_days,
    )

    reason = (
        f"Доступна повторная скидка {repeat_discount_percent}%"
        if eligible
        else f"Нет консультации у этого врача за последние {repeat_visit_days} дней"
    )

    return RepeatEligibilityPreviewItem(
        candidate_key=candidate.candidate_key,
        service_id=candidate.service_id,
        doctor_id=candidate.doctor_id,
        visit_date=candidate.visit_date,
        eligible=eligible,
        reason=reason,
        repeat_window_days=repeat_visit_days,
        repeat_discount_percent=repeat_discount_percent,
    )


# _calculate_visit_price() удалена - используйте billing_service.calculate_total() (SSOT)


def _create_queue_entries(
    db: Session, visits: list[Visit], queue_settings: dict[str, Any]
) -> dict[int, int]:
    """
    Создание записей в очереди для визитов на сегодня
    """
    queue_numbers = {}
    today = date.today()

    for visit in visits:
        if visit.visit_date != today:
            continue

        # Определяем все уникальные типы очередей для услуг визита
        visit_services = (
            db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        )
        service_ids = [vs.service_id for vs in visit_services]
        services = db.query(Service).filter(Service.id.in_(service_ids)).all()

        # Собираем все уникальные queue_tag для создания отдельных очередей
        unique_queue_tags = set()
        for service in services:
            if service.queue_tag:
                unique_queue_tags.add(service.queue_tag)
            else:
                unique_queue_tags.add("general")  # По умолчанию

        # Создаём отдельную запись в очереди для каждого типа услуг
        visit_queue_numbers = []
        try:
            for queue_tag in unique_queue_tags:
                # Определяем врача для очереди
                doctor_id = visit.doctor_id

                # Для очередей без конкретного врача используем ресурс-врачей
                if queue_tag == "ecg" and not doctor_id:
                    # Ищем ресурс-врача ЭКГ
                    from app.models.user import User

                    ecg_resource = (
                        db.query(User)
                        .filter(User.username == "ecg_resource", User.is_active == True)
                        .first()
                    )
                    if ecg_resource:
                        doctor_id = ecg_resource.id
                    else:
                        logger.warning(
                            "ЭКГ ресурс-врач не найден для queue_tag=%s", queue_tag
                        )
                        continue

                elif queue_tag == "lab" and not doctor_id:
                    # Ищем ресурс-врача лаборатории
                    from app.models.user import User

                    lab_resource = (
                        db.query(User)
                        .filter(User.username == "lab_resource", User.is_active == True)
                        .first()
                    )
                    if lab_resource:
                        # ✅ ИСПРАВЛЕНО: Находим Doctor по user_id для правильного specialist_id
                        lab_doctor = (
                            db.query(Doctor)
                            .filter(Doctor.user_id == lab_resource.id)
                            .first()
                        )
                        if lab_doctor:
                            doctor_id = (
                                lab_doctor.id
                            )  # Используем doctor_id, а не user_id
                            logger.info(
                                f"Для queue_tag={queue_tag} используется ресурс-врач: lab_resource (Doctor ID: {doctor_id})"
                            )
                        else:
                            logger.warning(
                                f"У ресурс-пользователя lab_resource (User ID: {lab_resource.id}) нет записи в таблице doctors"
                            )
                            continue
                    else:
                        logger.warning(
                            "Лаборатория ресурс-врач не найден для queue_tag=%s",
                            queue_tag,
                        )
                        continue

                daily_queue = crud_queue.get_or_create_daily_queue(
                    db, today, doctor_id, queue_tag
                )

                start_number = queue_settings.get("start_numbers", {}).get(queue_tag, 1)
                next_number = queue_service.get_next_queue_number(
                    db,
                    daily_queue=daily_queue,
                    queue_tag=queue_tag,
                    default_start=start_number,
                )

                queue_entry = queue_service.create_queue_entry(  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
                    db,
                    daily_queue=daily_queue,
                    patient_id=visit.patient_id,
                    number=next_number,
                    source="desk",
                )

                visit_queue_numbers.append(
                    {
                        "queue_tag": queue_tag,
                        "number": next_number,
                        "queue_id": daily_queue.id,
                    }
                )

            # Сохраняем все номера очередей для визита
            queue_numbers[visit.id] = visit_queue_numbers
        except Exception as e:
            logger.warning(
                "Could not create queue entries for visit %d: %s",
                visit.id,
                e,
                exc_info=True,
            )

    return queue_numbers


# ===================== CLICK ИНТЕГРАЦИЯ =====================


class InvoicePaymentRequest(BaseModel):
    invoice_id: int
    provider: str = Field(default="click")  # click|payme
    return_url: str | None = None
    cancel_url: str | None = None


class InvoicePaymentResponse(BaseModel):
    success: bool
    payment_url: str | None = None
    provider_payment_id: str | None = None
    error_message: str | None = None


SUPPORTED_INVOICE_PAYMENT_PROVIDERS = {"click", "payme"}


@router.post("/registrar/invoice/init-payment", response_model=InvoicePaymentResponse)
def init_invoice_payment(
    payment_req: InvoicePaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Инициация оплаты для invoice через Click/PayMe
    """
    try:
        # Получаем invoice
        invoice = (
            db.query(PaymentInvoice)
            .filter(PaymentInvoice.id == payment_req.invoice_id)
            .first()
        )
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice не найден")

        if invoice.status != "pending":
            raise HTTPException(
                status_code=400, detail=f"Invoice уже обработан: {invoice.status}"
            )

        # Инициализируем провайдер платежей
        provider_name = payment_req.provider.lower()
        if provider_name not in SUPPORTED_INVOICE_PAYMENT_PROVIDERS:
            return InvoicePaymentResponse(
                success=False,
                error_message=f"Провайдер {payment_req.provider} не поддерживается",
            )

        # Создаём платёж
        result = get_payment_manager().create_payment(
            provider_name=provider_name,
            amount=invoice.total_amount,
            currency=invoice.currency,
            order_id=f"invoice_{invoice.id}",
            description=f"Оплата визитов #{invoice.id}",
            return_url=payment_req.return_url,
            cancel_url=payment_req.cancel_url,
        )

        if result.success:
            # Обновляем invoice
            invoice.provider_payment_id = result.payment_id
            invoice.payment_method = provider_name
            invoice.provider = provider_name
            invoice.status = "processing"
            invoice.provider_data = result.provider_data
            db.commit()

            return InvoicePaymentResponse(
                success=True,
                payment_url=result.payment_url,
                provider_payment_id=result.payment_id,
            )
        else:
            return InvoicePaymentResponse(
                success=False, error_message=result.error_message
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.get("/registrar/invoice/{invoice_id}/status")
def check_invoice_status(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Проверка статуса оплаты invoice
    """
    try:
        invoice = (
            db.query(PaymentInvoice).filter(PaymentInvoice.id == invoice_id).first()
        )
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice не найден")

        # Если статус уже финальный, возвращаем как есть
        if invoice.status in ["paid", "failed", "cancelled"]:
            return {
                "invoice_id": invoice.id,
                "status": invoice.status,
                "total_amount": invoice.total_amount,
                "currency": invoice.currency,
                "provider_payment_id": invoice.provider_payment_id,
            }

        # Проверяем статус у провайдера
        if invoice.provider_payment_id and invoice.provider:
            provider_name = invoice.provider.lower()

            if provider_name in SUPPORTED_INVOICE_PAYMENT_PROVIDERS:
                result = get_payment_manager().check_payment_status(
                    provider_name, invoice.provider_payment_id
                )

                if result.success:
                    # Обновляем статус invoice
                    if result.status == "completed":
                        invoice.status = "paid"
                        invoice.paid_at = datetime.now(UTC)

                        # [OK] ИСПРАВЛЕНО: Создаем платежи для всех визитов через SSOT
                        from app.services.billing_service import BillingService

                        billing_service = BillingService(db)

                        # Помечаем все визиты как оплаченные и создаем платежи
                        invoice_visits = (
                            db.query(PaymentInvoiceVisit)
                            .filter(PaymentInvoiceVisit.invoice_id == invoice.id)
                            .all()
                        )

                        for iv in invoice_visits:
                            visit = (
                                db.query(Visit).filter(Visit.id == iv.visit_id).first()
                            )
                            if visit:
                                # Проверяем, не создан ли уже платеж
                                from app.models.payment import Payment

                                existing_payment = (
                                    db.query(Payment)
                                    .filter(
                                        Payment.visit_id == visit.id,
                                        Payment.status == "paid",
                                    )
                                    .first()
                                )

                                if not existing_payment:
                                    # Создаем платеж через SSOT
                                    payment = billing_service.create_payment(
                                        visit_id=visit.id,
                                        amount=float(iv.visit_amount),
                                        currency=invoice.currency,
                                        method="online",  # Онлайн оплата через провайдера
                                        status="paid",
                                        provider=invoice.provider,
                                        note=f"Оплата через {invoice.provider} (invoice {invoice.id})",
                                    )
                                    logger.info(
                                        "check_invoice_status: Создан платеж ID=%d для визита %d",
                                        payment.id,
                                        visit.id,
                                    )

                                visit.status = "confirmed"  # Оплачено и подтверждено

                        db.commit()
                    elif result.status in ["failed", "cancelled"]:
                        invoice.status = result.status
                        db.commit()

        return {
            "invoice_id": invoice.id,
            "status": invoice.status,
            "total_amount": invoice.total_amount,
            "currency": invoice.currency,
            "provider_payment_id": invoice.provider_payment_id,
            "paid_at": invoice.paid_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Internal server error"
        )


@router.post(
    "/registrar/repeat-eligibility-preview",
    response_model=RepeatEligibilityPreviewResponse,
    summary="Preview eligibility for repeat discount in registrar wizard",
)
def preview_repeat_eligibility(
    payload: RepeatEligibilityPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    _ = current_user

    patient_exists = (
        db.query(Patient.id).filter(Patient.id == payload.patient_id).first() is not None
    )
    if not patient_exists:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

    settings = _load_registration_discount_settings(db)
    repeat_visit_days = int(settings.get("repeat_visit_days", 21) or 21)
    repeat_discount_percent = int(settings.get("repeat_visit_discount", 0) or 0)

    items = [
        _build_repeat_eligibility_preview_item(
            db,
            patient_id=payload.patient_id,
            candidate=candidate,
            repeat_visit_days=repeat_visit_days,
            repeat_discount_percent=repeat_discount_percent,
        )
        for candidate in payload.candidates
    ]

    return RepeatEligibilityPreviewResponse(patient_id=payload.patient_id, items=items)


# ===================== ОСНОВНОЙ ENDPOINT =====================


@router.post("/registrar/cart", response_model=CartResponse)
def create_cart_appointments(
    cart_data: CartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Создание корзины визитов с единым платежом
    Поддерживает: повторные/льготные визиты, All Free, динамические цены, очереди по queue_tag
    """
    effective_discount_mode = _resolve_effective_discount_mode(cart_data)
    logger.info(
        "REGISTRATION: Получен запрос на создание корзины. Patient ID: %s, Визитов: %d, Discount mode: %s, Effective discount mode: %s, All free: %s, Payment method: %s",
        cart_data.patient_id,
        len(cart_data.visits),
        cart_data.discount_mode,
        effective_discount_mode,
        cart_data.all_free,
        cart_data.payment_method,
    )

    try:
        # Валидация пациента
        # (Предполагаем, что пациент уже существует, так как он выбран в мастере)

        # Получаем настройки очереди
        queue_settings = crud_clinic.get_queue_settings(db)  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
        registration_settings = _load_registration_discount_settings(db)

        created_visits = []
        created_visit_amounts: dict[int, Decimal] = {}
        total_invoice_amount = Decimal('0')

        # Создаём визиты
        from time import sleep

        logger.info("REGISTRATION: Создаём %d визитов", len(cart_data.visits))
        for idx, visit_req in enumerate(cart_data.visits):
            logger.debug(
                "REGISTRATION: Визит %d: department=%s, services=%d",
                idx + 1,
                visit_req.department,
                len(visit_req.services),
            )
            # Проверяем право на повторный визит
            if effective_discount_mode == "repeat" and visit_req.doctor_id:
                service_ids = [s.service_id for s in visit_req.services]
                repeat_visit_days = int(registration_settings["repeat_visit_days"])
                if not _check_repeat_visit_eligibility(
                    db,
                    cart_data.patient_id,
                    visit_req.doctor_id,
                    service_ids,
                    days_window=repeat_visit_days,
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Повторный визит недоступен: нет консультации у этого врача за последние {repeat_visit_days} дней",
                    )

            # [OK] ИСПРАВЛЕНО: Регистратор всегда создаёт подтверждённые записи
            # Фича-флаг "confirmation_before_queue" применяется только для онлайн-записей (телеграм/PWA)
            # Записи от регистратора сразу попадают в очередь
            visit_status = "confirmed"
            confirmed_at = datetime.now(UTC)
            confirmed_by = f"registrar_{current_user.id}"

            # [OK] ИСПРАВЛЕНО: Добавляем микрозадержку для разных created_at
            # Это гарантирует, что визиты одного пациента будут иметь разные временные метки
            if idx > 0:
                sleep(0.001)  # 1 миллисекунда задержки между визитами

            # Подготавливаем услуги для передачи в create_visit
            services_data = []
            visit_amount = Decimal("0")
            for service_item in visit_req.services:
                service = (
                    db.query(Service)
                    .filter(Service.id == service_item.service_id)
                    .first()
                )
                if not service:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Услуга с ID {service_item.service_id} не найдена",
                    )

                base_price = (
                    service_item.custom_price
                    if service_item.custom_price is not None
                    else service.price or Decimal("0")
                )
                item_price = _apply_service_discount(
                    Decimal(str(base_price)),
                    effective_discount_mode,
                    registration_settings,
                    service.is_consultation,
                )
                visit_amount += item_price * Decimal(service_item.quantity)

                services_data.append(
                    {
                        "service_id": service.id,
                        # ⭐ SSOT: используем canonical service_code helper
                        "code": service.service_code or get_service_code(service.id, db),
                        "name": service.name,
                        "qty": service_item.quantity,
                        "price": float(item_price),
                    }
                )

            # Создаём визит используя единую функцию create_visit для обеспечения Single Source of Truth
            from app.crud.visit import create_visit

            visit = create_visit(
                db=db,
                patient_id=cart_data.patient_id,
                doctor_id=visit_req.doctor_id,
                visit_date=visit_req.visit_date,
                visit_time=visit_req.visit_time,
                department=visit_req.department,
                notes=visit_req.notes,
                discount_mode=effective_discount_mode,
                services=services_data,
                status=visit_status,
                approval_status=(
                    "approved"
                    if effective_discount_mode != "all_free"
                    or registration_settings["all_free_auto_approve"]
                    else "pending"
                ),
                confirmed_at=confirmed_at,
                confirmed_by=confirmed_by,
                auto_status=False,  # Статус уже установлен выше
                notify=False,  # Уведомления отправляются отдельно
                log=True,
            )
            logger.info("REGISTRATION: Визит %d создан через create_visit()", visit.id)

            created_visits.append(visit)
            created_visit_amounts[visit.id] = visit_amount
            total_invoice_amount += visit_amount
            logger.info(
                "REGISTRATION: Визит %d создан успешно для пациента %d",
                visit.id,
                cart_data.patient_id,
            )

        # Создаём единый invoice
        logger.info("REGISTRATION: Создаём инвойс на сумму %s", total_invoice_amount)
        invoice = PaymentInvoice(
            patient_id=cart_data.patient_id,
            total_amount=total_invoice_amount,
            currency="UZS",
            status="pending",
            payment_method=cart_data.payment_method,
            notes=cart_data.notes,
        )
        db.add(invoice)
        db.flush()  # Получаем ID invoice
        logger.info("REGISTRATION: Инвойс %d создан", invoice.id)

        # Связываем визиты с invoice
        for visit in created_visits:
            visit_amount = created_visit_amounts.get(visit.id, Decimal("0"))
            invoice_visit = PaymentInvoiceVisit(
                invoice_id=invoice.id, visit_id=visit.id, visit_amount=visit_amount
            )
            db.add(invoice_visit)

        # Assign queue entries for confirmed same-day visits via extracted seam.
        queue_numbers = {}
        today = date.today()

        queue_numbers = RegistrarWizardQueueAssignmentService(db).assign_same_day_queue_numbers(
            created_visits,
            target_day=today,
            source="desk",
        )

        db.commit()
        logger.info("REGISTRATION: Транзакция зафиксирована в базе данных")

        if effective_discount_mode == "all_free":
            for visit in created_visits:
                if visit.approval_status != "pending":
                    continue
                try:
                    asyncio.run(
                        notification_sender_service.send_all_free_request_notification(
                            db=db,
                            visit=visit,
                            actor_user=current_user,
                        )
                    )
                except Exception as notification_error:
                    logger.warning(
                        "[FIX:NOTIFICATIONS] failed to publish all_free_requested after cart commit",
                        extra={
                            "visit_id": visit.id,
                            "patient_id": cart_data.patient_id,
                            "actor_id": current_user.id,
                            "error": str(notification_error),
                        },
                    )

        # Формируем талоны для визитов с присвоенными номерами очередей
        print_tickets = []
        # Блок формирования талонов пропускаем, так как queue_numbers пустой

        # Формируем информацию о созданных визитах
        created_visits_info = []
        try:
            for visit in created_visits:
                # Получаем данные пациента
                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )
                patient_name = (
                    patient.short_name() if patient else "Неизвестный пациент"
                )

                # Получаем данные врача
                doctor = (
                    db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
                    if visit.doctor_id
                    else None
                )
                # [OK] ИСПРАВЛЕНО: User имеет full_name, а не first_name/last_name
                if doctor and doctor.user_id:
                    user = db.query(User).filter(User.id == doctor.user_id).first()
                    doctor_name = (
                        (user.full_name or user.username) if user else "Без врача"
                    )
                else:
                    doctor_name = "Без врача"

                # Получаем услуги визита
                visit_services = (
                    db.query(VisitService)
                    .filter(VisitService.visit_id == visit.id)
                    .all()
                )
                services_info = []
                for vs in visit_services:
                    services_info.append(
                        {
                            "name": vs.name,
                            "code": (
                                normalize_service_code(vs.code) if vs.code else None
                            ),
                            "quantity": vs.qty,
                            "price": float(vs.price) if vs.price else 0,
                        }
                    )

                created_visits_info.append(
                    {
                        "visit_id": visit.id,
                        "patient_name": patient_name,
                        "doctor_name": doctor_name,
                        "visit_date": visit.visit_date.isoformat(),
                        "visit_time": visit.visit_time,
                        "status": visit.status,
                        "department": visit.department,
                        "services": services_info,
                        "confirmation_required": visit.status == "pending_confirmation",
                        "confirmation_token": (
                            visit.confirmation_token
                            if visit.status == "pending_confirmation"
                            else None
                        ),
                    }
                )
        except Exception as e:
            logger.warning(
                "REGISTRATION: Ошибка формирования ответа (визиты уже сохранены): %s",
                str(e),
                exc_info=True,
            )
            # Визиты уже сохранены, поэтому не откатываем транзакцию

        # Определяем сообщение в зависимости от результата
        if queue_numbers:
            message = f"Корзина создана успешно. Присвоено номеров в очередях: {sum(len(assignments) for assignments in queue_numbers.values())}"
        else:
            message = "Визиты созданы. Номера в очередях будут присвоены в день визита."

        logger.info(
            "REGISTRATION: Корзина создана успешно. Создано визитов: %d, ID визитов: %s, Invoice ID: %d, Total amount: %s",
            len(created_visits),
            [v.id for v in created_visits],
            invoice.id,
            total_invoice_amount,
        )

        return CartResponse(
            success=True,
            message=message,
            invoice_id=invoice.id,
            visit_ids=[v.id for v in created_visits],
            total_amount=total_invoice_amount,
            queue_numbers=queue_numbers,
            print_tickets=print_tickets,
            created_visits=created_visits_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "REGISTRATION: cart creation failed",
            extra={"error_class": e.__class__.__name__},
        )
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка создания корзины",
        )


# ===================== УПРАВЛЕНИЕ ИЗМЕНЕНИЯМИ ЦЕН =====================


@router.post("/registrar/cart/edit-delta", response_model=EditDeltaResponse)
def apply_registrar_cart_edit_delta(
    request: EditDeltaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    try:
        result = RegistrarEditDeltaService(db).apply(
            patient_id=request.patient_id,
            services=[
                RegistrarEditDeltaItem(
                    service_id=item.service_id,
                    quantity=item.quantity,
                    specialist_id=item.specialist_id,
                )
                for item in request.services
            ],
            target_date=request.target_date,
            payment_method=request.payment_method,
            discount_mode=request.discount_mode,
            all_free=request.all_free,
            patient_data=(
                request.patient_data.model_dump(exclude_none=True)
                if request.patient_data
                else None
            ),
            existing_queue_entry_ids=request.existing_queue_entry_ids,
            expected_entry_updated_at=request.expected_entry_updated_at,
            current_user=current_user,
        )
        return EditDeltaResponse(**result)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        logger.exception(
            "REGISTRATION: edit delta failed",
            extra={"error_class": exc.__class__.__name__},
        )
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка обновления записи",
        )


class PriceOverrideApprovalRequest(BaseModel):
    override_id: int
    action: str = Field(..., pattern="^(approve|reject)$")  # approve или reject
    rejection_reason: str | None = None


class PriceOverrideListResponse(BaseModel):
    id: int
    visit_id: int
    service_id: int
    service_name: str
    doctor_name: str
    doctor_specialty: str
    patient_name: str | None
    original_price: Decimal
    new_price: Decimal
    reason: str
    details: str | None
    status: str
    available_actions: list[str]
    can_approve: bool
    can_reject: bool
    created_at: datetime


def _price_override_available_actions(override_status: str) -> list[str]:
    if override_status == "pending":
        return ["approve", "reject"]
    return []


@router.get(
    "/registrar/price-overrides", summary="Получить все изменения цен для одобрения"
)
def get_pending_price_overrides(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    status_filter: str | None = Query(
        default="pending", pattern="^(pending|approved|rejected|all)$"
    ),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PriceOverrideListResponse]:
    """
    Получить список изменений цен для одобрения регистратурой
    """
    try:
        query = db.query(DoctorPriceOverride).join(Service).join(Doctor)

        if status_filter != "all":
            query = query.filter(DoctorPriceOverride.status == status_filter)

        overrides = (
            query.order_by(DoctorPriceOverride.created_at.desc()).limit(limit).all()
        )

        result = []
        for override in overrides:
            available_actions = _price_override_available_actions(override.status)
            # Получаем данные визита и пациента
            visit = db.query(Visit).filter(Visit.id == override.visit_id).first()
            patient_name = None
            if visit:
                # Здесь нужно получить имя пациента из модели Patient
                # Пока используем заглушку
                patient_name = f"Пациент #{visit.patient_id}"

            result.append(
                PriceOverrideListResponse(
                    id=override.id,
                    visit_id=override.visit_id,
                    service_id=override.service_id,
                    service_name=override.service.name,
                    doctor_name=f"Врач #{override.doctor.id}",  # Здесь нужно получить имя врача
                    doctor_specialty=override.doctor.specialty,
                    patient_name=patient_name,
                    original_price=override.original_price,
                    new_price=override.new_price,
                    reason=override.reason,
                    details=override.details,
                    status=override.status,
                    available_actions=available_actions,
                    can_approve="approve" in available_actions,
                    can_reject="reject" in available_actions,
                    created_at=override.created_at,
                )
            )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/registrar/price-override/approve", summary="Одобрить или отклонить изменение цены"
)
def approve_price_override(
    approval_data: PriceOverrideApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
) -> dict[str, Any]:
    """
    Одобрить или отклонить изменение цены врачом
    """
    try:
        # Получаем изменение цены
        override = (
            db.query(DoctorPriceOverride)
            .filter(DoctorPriceOverride.id == approval_data.override_id)
            .first()
        )

        if not override:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Изменение цены не найдено",
            )

        if override.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Изменение цены уже обработано (статус: {override.status})",
            )

        # Обновляем статус
        if approval_data.action == "approve":
            override.status = "approved"
            override.approved_by = current_user.id
            override.approved_at = datetime.now(UTC)

            # Обновляем цену в визите
            visit = db.query(Visit).filter(Visit.id == override.visit_id).first()
            if visit:
                # Обновляем doctor_price_override в JSON поле
                if not visit.doctor_price_override:
                    visit.doctor_price_override = {}

                visit.doctor_price_override[str(override.service_id)] = {
                    "original_price": float(override.original_price),
                    "new_price": float(override.new_price),
                    "override_id": override.id,
                    "approved_at": override.approved_at.isoformat(),
                }

            message = "Изменение цены одобрено"

        elif approval_data.action == "reject":
            override.status = "rejected"
            override.approved_by = current_user.id
            override.approved_at = datetime.now(UTC)
            override.rejection_reason = approval_data.rejection_reason

            message = "Изменение цены отклонено"

        db.commit()
        db.refresh(override)

        return {
            "success": True,
            "message": message,
            "override_id": override.id,
            "new_status": override.status,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== УПРАВЛЕНИЕ ЛЬГОТАМИ ALL FREE =====================


class AllFreeApprovalRequest(BaseModel):
    visit_id: int
    action: str = Field(..., pattern="^(approve|reject)$")  # approve или reject
    rejection_reason: str | None = None


class AllFreeVisitResponse(BaseModel):
    id: int
    patient_id: int
    patient_name: str | None
    patient_phone: str | None
    services: list[str]
    total_original_amount: Decimal
    doctor_name: str | None
    doctor_specialty: str | None
    visit_date: date | None
    visit_time: str | None
    notes: str | None
    created_at: datetime
    approval_status: str
    available_actions: list[str]
    can_approve: bool
    can_reject: bool


def _all_free_available_actions(approval_status: str) -> list[str]:
    if approval_status == "pending":
        return ["approve", "reject"]
    return []


@router.get(
    "/admin/all-free-requests", summary="Получить заявки All Free для одобрения"
)
def get_all_free_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
    status_filter: str | None = Query(
        default="pending", pattern="^(pending|approved|rejected|all)$"
    ),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AllFreeVisitResponse]:
    """
    Получить список заявок All Free для одобрения администратором
    """
    try:
        query = db.query(Visit).filter(Visit.discount_mode == "all_free")

        if status_filter != "all":
            query = query.filter(Visit.approval_status == status_filter)

        visits = query.order_by(Visit.created_at.desc()).limit(limit).all()

        result = []
        for visit in visits:
            available_actions = _all_free_available_actions(visit.approval_status)
            # Получаем услуги визита
            visit_services = (
                db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            )
            service_names = []
            total_original_amount = Decimal('0')

            for vs in visit_services:
                service = db.query(Service).filter(Service.id == vs.service_id).first()
                if service:
                    service_names.append(service.name)
                    total_original_amount += (service.price or Decimal('0')) * vs.qty

            # Получаем данные врача
            doctor_name = None
            doctor_specialty = None
            if visit.doctor_id:
                try:
                    doctor = (
                        db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
                    )
                    if doctor:
                        # Получаем имя врача из связанного пользователя
                        # [OK] ИСПРАВЛЕНО: Используем явный запрос вместо relationship, чтобы избежать ошибок
                        if doctor.user_id:
                            user = (
                                db.query(User).filter(User.id == doctor.user_id).first()
                            )
                            if user:
                                # [OK] ИСПРАВЛЕНО: User имеет full_name, а не first_name/last_name
                                doctor_name = (
                                    (user.full_name or user.username)
                                    if user
                                    else f"Врач #{doctor.id}"
                                )
                            else:
                                doctor_name = f"Врач #{doctor.id}"
                        else:
                            doctor_name = f"Врач #{doctor.id}"
                        doctor_specialty = doctor.specialty
                except Exception as e:
                    logger.warning(
                        "get_all_free_requests: Ошибка получения данных врача для visit %d: %s",
                        visit.id,
                        e,
                        exc_info=True,
                    )
                    doctor_name = f"Врач #{visit.doctor_id}"
                    doctor_specialty = None

            # [OK] ИСПРАВЛЕНО: Получаем реальные данные пациента
            patient_name = f"Пациент #{visit.patient_id}"
            patient_phone = None
            if visit.patient_id:
                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )
                if patient:
                    # Формируем ФИО пациента
                    name_parts = []
                    if patient.last_name:
                        name_parts.append(patient.last_name)
                    if patient.first_name:
                        name_parts.append(patient.first_name)
                    if patient.middle_name:
                        name_parts.append(patient.middle_name)
                    patient_name = (
                        ' '.join(name_parts)
                        if name_parts
                        else f"Пациент #{visit.patient_id}"
                    )
                    patient_phone = patient.phone

            result.append(
                AllFreeVisitResponse(
                    id=visit.id,
                    patient_id=visit.patient_id,
                    patient_name=patient_name,
                    patient_phone=patient_phone,
                    services=service_names,
                    total_original_amount=total_original_amount,
                    doctor_name=doctor_name,
                    doctor_specialty=doctor_specialty,
                    visit_date=visit.visit_date,
                    visit_time=visit.visit_time,
                    notes=visit.notes,
                    created_at=visit.created_at,
                    approval_status=visit.approval_status,
                    available_actions=available_actions,
                    can_approve="approve" in available_actions,
                    can_reject="reject" in available_actions,
                )
            )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/admin/all-free-approve", summary="Одобрить или отклонить заявку All Free"
)
def approve_all_free_request(
    approval_data: AllFreeApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> dict[str, Any]:
    """
    Одобрить или отклонить заявку All Free администратором
    """
    try:
        # Получаем визит
        visit = db.query(Visit).filter(Visit.id == approval_data.visit_id).first()

        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("visit.not_found")
            )

        if visit.discount_mode != "all_free":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Это не заявка All Free"
            )

        if visit.approval_status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Заявка уже обработана (статус: {visit.approval_status})",
            )

        # Обновляем статус
        if approval_data.action == "approve":
            visit.approval_status = "approved"
            message = "Заявка All Free одобрена"

        elif approval_data.action == "reject":
            visit.approval_status = "rejected"
            # Можно добавить поле для причины отклонения в модель Visit
            if approval_data.rejection_reason:
                visit.notes = (
                    visit.notes or ""
                ) + f"\nОтклонено: {approval_data.rejection_reason}"

            message = "Заявка All Free отклонена"

        db.commit()
        db.refresh(visit)

        try:
            asyncio.run(
                notification_sender_service.send_all_free_decision_notification(
                    db=db,
                    visit=visit,
                    actor_user=current_user,
                    rejection_reason=approval_data.rejection_reason,
                )
            )
        except Exception as notification_error:
            logger.warning(
                "[FIX:NOTIFICATIONS] failed to publish all_free decision notification",
                extra={
                    "visit_id": visit.id,
                    "approval_status": visit.approval_status,
                    "actor_id": current_user.id,
                    "error": str(notification_error),
                },
            )

        return {
            "success": True,
            "message": message,
            "visit_id": visit.id,
            "new_status": visit.approval_status,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== НАСТРОЙКИ ЛЬГОТ =====================


class BenefitSettingsRequest(BaseModel):
    repeat_visit_days: int = Field(
        default=21, ge=1, le=365
    )  # Окно повторного визита в днях
    repeat_visit_discount: int = Field(
        default=0, ge=0, le=100
    )  # Скидка на повторный визит в %
    benefit_consultation_free: bool = Field(
        default=True
    )  # Льготные консультации бесплатны
    all_free_auto_approve: bool = Field(default=False)  # Автоодобрение All Free заявок


class BenefitSettingsResponse(BaseModel):
    repeat_visit_days: int
    repeat_visit_discount: int
    benefit_consultation_free: bool
    all_free_auto_approve: bool
    updated_at: datetime


@router.get("/admin/benefit-settings", summary="Получить настройки льгот")
def get_benefit_settings(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
) -> BenefitSettingsResponse:
    """
    Получить текущие настройки льгот и повторных визитов
    """
    try:
        # Получаем настройки из базы данных
        settings = {}

        # Окно повторного визита (дни)
        repeat_days_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "repeat_visit_days")
            .first()
        )
        settings['repeat_visit_days'] = (
            int(repeat_days_setting.value) if repeat_days_setting else 21
        )

        # Скидка на повторный визит (%)
        repeat_discount_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "repeat_visit_discount")
            .first()
        )
        settings['repeat_visit_discount'] = (
            int(repeat_discount_setting.value) if repeat_discount_setting else 0
        )

        # Льготные консультации бесплатны
        benefit_free_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "benefit_consultation_free")
            .first()
        )
        settings['benefit_consultation_free'] = (
            bool(benefit_free_setting.value) if benefit_free_setting else True
        )

        # Автоодобрение All Free заявок
        auto_approve_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "all_free_auto_approve")
            .first()
        )
        settings['all_free_auto_approve'] = (
            bool(auto_approve_setting.value) if auto_approve_setting else False
        )

        # Время последнего обновления
        latest_update = (
            db.query(ClinicSettings)
            .filter(
                ClinicSettings.key.in_(
                    [
                        "repeat_visit_days",
                        "repeat_visit_discount",
                        "benefit_consultation_free",
                        "all_free_auto_approve",
                    ]
                )
            )
            .order_by(ClinicSettings.updated_at.desc())
            .first()
        )

        updated_at = latest_update.updated_at if latest_update else datetime.now(UTC)

        return BenefitSettingsResponse(
            repeat_visit_days=settings['repeat_visit_days'],
            repeat_visit_discount=settings['repeat_visit_discount'],
            benefit_consultation_free=settings['benefit_consultation_free'],
            all_free_auto_approve=settings['all_free_auto_approve'],
            updated_at=updated_at,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/admin/benefit-settings", summary="Обновить настройки льгот")
def update_benefit_settings(
    settings_data: BenefitSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> dict[str, Any]:
    """
    Обновить настройки льгот и повторных визитов
    """
    try:
        # Список настроек для обновления
        settings_to_update = [
            {
                "key": "repeat_visit_days",
                "value": settings_data.repeat_visit_days,
                "description": "Окно повторного визита в днях",
            },
            {
                "key": "repeat_visit_discount",
                "value": settings_data.repeat_visit_discount,
                "description": "Скидка на повторный визит в процентах",
            },
            {
                "key": "benefit_consultation_free",
                "value": settings_data.benefit_consultation_free,
                "description": "Льготные консультации бесплатны",
            },
            {
                "key": "all_free_auto_approve",
                "value": settings_data.all_free_auto_approve,
                "description": "Автоматическое одобрение All Free заявок",
            },
        ]

        # Обновляем каждую настройку
        for setting_data in settings_to_update:
            setting = (
                db.query(ClinicSettings)
                .filter(ClinicSettings.key == setting_data["key"])
                .first()
            )

            if setting:
                # Обновляем существующую настройку
                setting.value = setting_data["value"]
                setting.updated_by = current_user.id
                setting.updated_at = datetime.now(UTC)
            else:
                # Создаём новую настройку
                setting = ClinicSettings(
                    key=setting_data["key"],
                    value=setting_data["value"],
                    category="benefits",
                    description=setting_data["description"],
                    updated_by=current_user.id,
                )
                db.add(setting)

        db.commit()

        return {
            "success": True,
            "message": "Настройки льгот обновлены успешно",
            "settings": {
                "repeat_visit_days": settings_data.repeat_visit_days,
                "repeat_visit_discount": settings_data.repeat_visit_discount,
                "benefit_consultation_free": settings_data.benefit_consultation_free,
                "all_free_auto_approve": settings_data.all_free_auto_approve,
            },
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ==================== НАСТРОЙКИ МАСТЕРА РЕГИСТРАЦИИ ====================


class WizardSettingsResponse(BaseModel):
    use_new_wizard: bool
    updated_at: datetime


class WizardSettingsRequest(BaseModel):
    use_new_wizard: bool = Field(
        default=False, description="Использовать новый мастер регистрации"
    )


@router.get("/admin/wizard-settings", summary="Получить настройки мастера регистрации")
def get_wizard_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """Получить настройки мастера регистрации"""
    try:
        # Получаем настройку использования нового мастера
        use_new_wizard_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "wizard_use_new_version")
            .first()
        )

        use_new_wizard = False
        updated_at = datetime.now(UTC)

        if use_new_wizard_setting:
            use_new_wizard = (
                use_new_wizard_setting.value.get("enabled", False)
                if use_new_wizard_setting.value
                else False
            )
            updated_at = use_new_wizard_setting.updated_at or updated_at

        return WizardSettingsResponse(
            use_new_wizard=use_new_wizard, updated_at=updated_at
        )

    except Exception as e:
        logger.error(f"Error getting wizard settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении настроек мастера",
        )


@router.post("/admin/wizard-settings", summary="Обновить настройки мастера регистрации")
def update_wizard_settings(
    settings_data: WizardSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Обновить настройки мастера регистрации"""
    try:
        # Обновляем или создаем настройку
        use_new_wizard_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "wizard_use_new_version")
            .first()
        )

        if not use_new_wizard_setting:
            use_new_wizard_setting = ClinicSettings(
                key="wizard_use_new_version",
                category="wizard",
                description="Использовать новый мастер регистрации вместо старого",
            )
            db.add(use_new_wizard_setting)

        use_new_wizard_setting.value = {
            "enabled": settings_data.use_new_wizard,
            "updated_by": current_user.id,
        }
        use_new_wizard_setting.updated_by = current_user.id
        use_new_wizard_setting.updated_at = datetime.now(UTC)

        db.commit()
        db.refresh(use_new_wizard_setting)

        settings_response = WizardSettingsResponse(
            use_new_wizard=settings_data.use_new_wizard,
            updated_at=use_new_wizard_setting.updated_at,
        )

        return {
            "success": True,
            "message": f"Настройки мастера обновлены. {'Включен новый мастер' if settings_data.use_new_wizard else 'Включен старый мастер'}",
            "settings": settings_response,
        }

    except Exception as e:
        logger.error(f"Error updating wizard settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при обновлении настроек мастера",
        )


# ===================== ЭНДПОИНТ ДЛЯ ПОЛУЧЕНИЯ ЗАПИСЕЙ ИЗ VISITS =====================


class VisitResponse(BaseModel):
    id: int
    patient_id: int
    patient_fio: str | None = None
    patient_phone: str | None = None
    doctor_id: int | None = None
    doctor_name: str | None = None
    doctor_specialty: str | None = None
    department: str | None = None
    visit_date: date | None = None
    visit_time: str | None = None
    status: str
    discount_mode: str
    approval_status: str
    services: list[str] | None = None
    notes: str | None = None
    created_at: datetime


@router.get("/registrar/visits", response_model=list[VisitResponse])
def get_visits(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "cardio", "derma", "dentist", "Cashier", "Lab")),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = Query(None, description="Фильтр по ID пациента"),
    doctor_id: int | None = Query(None, description="Фильтр по ID врача"),
    department: str | None = Query(None, description="Фильтр по отделению"),
    date_from: str | None = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Дата окончания (YYYY-MM-DD)"),
):
    """Получить объединенный список записей из таблиц visits (новый мастер) и appointments (старый мастер)"""
    try:
        from app.models.appointment import Appointment
        from app.models.clinic import Doctor
        from app.models.patient import Patient
        from app.models.service import Service
        from app.models.visit import Visit, VisitService

        result = []

        # 1. ПОЛУЧАЕМ ЗАПИСИ ИЗ СТАРОЙ ТАБЛИЦЫ APPOINTMENTS
        try:
            appointments_query = db.query(Appointment)

            # Фильтры для appointments
            if patient_id:
                appointments_query = appointments_query.filter(Appointment.patient_id == patient_id)
            if doctor_id:
                appointments_query = appointments_query.filter(Appointment.doctor_id == doctor_id)
            if department:
                appointments_query = appointments_query.filter(Appointment.department == department)
            if date_from:
                try:
                    from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                    appointments_query = appointments_query.filter(Appointment.appointment_date >= from_date)
                except ValueError:
                    pass
            if date_to:
                try:
                    to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                    appointments_query = appointments_query.filter(Appointment.appointment_date <= to_date)
                except ValueError:
                    pass

            appointments = (
                appointments_query
                .order_by(Appointment.created_at.desc())
                .limit(limit)
                .all()
            )

            # Обрабатываем записи из appointments
            for appointment in appointments:
                # Получаем данные пациента
                patient_fio = f"Пациент #{appointment.patient_id}"
                patient_phone = None
                try:
                    if appointment.patient_id:
                        patient = (
                            db.query(Patient)
                            .filter(Patient.id == appointment.patient_id)
                            .first()
                        )
                        if patient:
                            patient_fio = patient.short_name()
                            patient_phone = patient.phone
                except Exception:
                    pass

                result.append(
                    VisitResponse(
                        id=appointment.id
                        + 10000,  # Добавляем смещение чтобы избежать конфликтов ID
                        patient_id=appointment.patient_id,
                        patient_fio=patient_fio,
                        patient_phone=patient_phone,
                        doctor_id=appointment.doctor_id,
                        doctor_name=None,
                        doctor_specialty=None,
                        department=appointment.department,
                        visit_date=appointment.appointment_date,
                        visit_time=appointment.appointment_time,
                        status=appointment.status,
                        discount_mode="none",
                        approval_status="approved",
                        services=appointment.services or [],
                        notes=appointment.notes,
                        created_at=appointment.created_at,
                    )
                )
        except Exception as e:
            logger.error("Error processing appointments: %s", e, exc_info=True)

        # 2. ПОЛУЧАЕМ ЗАПИСИ ИЗ НОВОЙ ТАБЛИЦЫ VISITS
        visits_query = db.query(Visit)

        # Фильтры для visits
        if patient_id:
            visits_query = visits_query.filter(Visit.patient_id == patient_id)
        if doctor_id:
            visits_query = visits_query.filter(Visit.doctor_id == doctor_id)
        if department:
            visits_query = visits_query.filter(Visit.department == department)
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date >= from_date)
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date <= to_date)
            except ValueError:
                pass

        visits = visits_query.order_by(Visit.created_at.desc()).all()

        # Обрабатываем записи из visits
        for visit in visits:
            # Получаем услуги визита
            visit_services = (
                db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            )
            service_names = []
            for vs in visit_services:
                if vs.name:  # Используем сохраненное имя
                    service_names.append(vs.name)
                else:  # Fallback - ищем в таблице services
                    service = (
                        db.query(Service).filter(Service.id == vs.service_id).first()
                    )
                    if service:
                        service_names.append(service.name)

            # Получаем данные врача
            doctor_name = None
            doctor_specialty = None
            if visit.doctor_id:
                doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
                if doctor:
                    # [OK] ИСПРАВЛЕНО: User имеет full_name, а не first_name/last_name
                    if doctor.user_id:
                        user = db.query(User).filter(User.id == doctor.user_id).first()
                        doctor_name = (
                            (user.full_name or user.username)
                            if user
                            else f"Врач #{doctor.id}"
                        )
                    else:
                        doctor_name = f"Врач #{doctor.id}"
                    doctor_specialty = doctor.specialty

            # Получаем данные пациента
            patient_fio = f"Пациент #{visit.patient_id}"
            patient_phone = None
            if visit.patient_id:
                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )
                if patient:
                    patient_fio = patient.short_name()
                    patient_phone = patient.phone

            result.append(
                VisitResponse(
                    id=visit.id,
                    patient_id=visit.patient_id,
                    patient_fio=patient_fio,
                    patient_phone=patient_phone,
                    doctor_id=visit.doctor_id,
                    doctor_name=doctor_name,
                    doctor_specialty=doctor_specialty,
                    department=visit.department,
                    visit_date=visit.visit_date,
                    visit_time=visit.visit_time,
                    status=visit.status,
                    discount_mode=visit.discount_mode,
                    approval_status=visit.approval_status,
                    services=service_names,
                    notes=visit.notes,
                    created_at=visit.created_at,
                )
            )

        # Сортируем объединенный результат по дате создания
        result.sort(key=lambda x: x.created_at, reverse=True)

        # Применяем пагинацию к объединенному результату
        total_results = result[skip : skip + limit]

        return total_results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== ПРОСТОЙ ЭНДПОИНТ ДЛЯ ОБЪЕДИНЕНИЯ ДАННЫХ =====================


@router.get("/registrar/all-appointments")
def get_all_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Doctor",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
            "Lab",
        )
    ),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    date_from: str | None = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    search: str | None = Query(
        None, description="Поиск по ФИО, телефону или услугам"
    ),
):
    """Простое объединение appointments + visits для фронтенда"""
    try:
        from datetime import datetime

        from sqlalchemy import func, or_

        from app.models.appointment import Appointment
        from app.models.patient import Patient
        from app.models.visit import Visit

        result = []

        # 1. Получаем старые appointments с фильтрацией
        appointments_query = db.query(Appointment)

        # Применяем фильтры по дате
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                appointments_query = appointments_query.filter(
                    Appointment.appointment_date >= from_date
                )
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                appointments_query = appointments_query.filter(
                    Appointment.appointment_date <= to_date
                )
            except ValueError:
                pass

        patient_search_name = func.trim(
            func.coalesce(Patient.last_name, "")
            + literal(" ")
            + func.coalesce(Patient.first_name, "")
            + literal(" ")
            + func.coalesce(Patient.middle_name, "")
        )

        # Применяем поиск
        if search:
            # Для поиска по телефону извлекаем только цифры
            search_digits = ''.join(filter(str.isdigit, search))

            if search_digits:
                # Поиск по ФИО, телефону и ID записи (включая только цифры)
                appointments_query = appointments_query.join(
                    Patient, Appointment.patient_id == Patient.id
                ).filter(
                    or_(
                        patient_search_name.ilike(f"%{search}%"),
                        Patient.phone.ilike(f"%{search}%"),
                        func.regexp_replace(Patient.phone, r'[^\d]', '', 'g').ilike(
                            f"%{search_digits}%"
                        ),
                        Appointment.id.cast(String).ilike(f"%{search_digits}%"),
                    )
                )
            else:
                # Если нет цифр, ищем только по ФИО
                appointments_query = appointments_query.join(
                    Patient, Appointment.patient_id == Patient.id
                ).filter(patient_search_name.ilike(f"%{search}%"))

        appointments = (
            appointments_query.order_by(Appointment.created_at.desc())
            .limit(limit // 2)
            .all()
        )
        for apt in appointments:
            related_visit = None
            # Получаем имя пациента
            patient_fio = None
            if apt.patient_id:
                patient = db.query(Patient).filter(Patient.id == apt.patient_id).first()
                if patient:
                    patient_fio = patient.short_name()

            # Преобразуем ID услуг в названия для appointments
            service_names = []
            service_codes = []
            total_amount = 0

            if apt.services and isinstance(apt.services, list):
                from app.models.service import Service

                for service_id in apt.services:
                    try:
                        service_id_int = int(service_id)
                        service = (
                            db.query(Service)
                            .filter(Service.id == service_id_int)
                            .first()
                        )
                        if service:
                            service_names.append(service.name)
                            service_code = service.service_code or get_service_code(
                                service.id, db
                            )
                            if service_code:
                                service_codes.append(service_code)
                            if service.price:
                                total_amount += float(service.price)
                    except (ValueError, TypeError):
                        # Если service_id не число, возможно это уже название
                        service_names.append(str(service_id))

            # Определяем payment_status для Appointment по Payment table.
            try:
                from sqlalchemy import and_

                related_visit = (
                    db.query(Visit)
                    .filter(
                        and_(
                            Visit.patient_id == apt.patient_id,
                            Visit.visit_date == apt.appointment_date,
                            Visit.doctor_id == apt.doctor_id,
                        )
                    )
                    .first()
                )
            except Exception:
                related_visit = None

            visit_type = _normalize_registration_discount_mode(
                getattr(apt, 'visit_type', None)
            )
            appointment_payment_processed_at = getattr(apt, 'payment_processed_at', None)
            payment_status, payment_type = _resolve_payment_truth(
                db,
                visit_id=related_visit.id if related_visit else None,
                legacy_paid_at=appointment_payment_processed_at,
            )

            result.append(
                {
                    'id': apt.id,
                    'appointment_id': apt.id,
                    'visit_id': related_visit.id if related_visit else None,
                    'patient_id': apt.patient_id,
                    'patient_fio': patient_fio,
                    'doctor_id': apt.doctor_id,
                    'department': apt.department,
                    'appointment_date': apt.appointment_date,
                    'appointment_time': apt.appointment_time,
                    'status': _preserve_operational_status_on_payment(apt.status),
                    'services': service_names,  # Преобразованные названия услуг
                    'service_codes': service_codes,  # Коды услуг для фильтрации
                    'total_amount': total_amount,  # Общая сумма услуг
                    'payment_status': payment_status,  # [OK] ДОБАВЛЕНО: Статус оплаты
                    'payment_type': payment_type,
                    'visit_type': visit_type,  # Тип визита для совместимости
                    'notes': apt.notes,
                    'created_at': apt.created_at,
                    'source': 'appointments',
                    'queue_numbers': [],  # Старые appointments не имеют номеров в новых очередях
                    'confirmation_status': 'none',  # Старые appointments не требуют подтверждения
                    'confirmed_at': None,
                    'confirmed_by': None,
                }
            )

        # 2. Получаем новые visits с фильтрацией
        visits_query = db.query(Visit)

        # Применяем фильтры по дате
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date >= from_date)
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date <= to_date)
            except ValueError:
                pass

        # Применяем поиск
        if search:
            # Для поиска по телефону извлекаем только цифры
            search_digits = ''.join(filter(str.isdigit, search))

            if search_digits:
                # Поиск по ФИО, телефону и ID записи (включая только цифры)
                visits_query = visits_query.join(
                    Patient, Visit.patient_id == Patient.id
                ).filter(
                    or_(
                        Patient.full_name.ilike(f"%{search}%"),
                        Patient.phone.ilike(f"%{search}%"),
                        func.regexp_replace(Patient.phone, r'[^\d]', '', 'g').ilike(
                            f"%{search_digits}%"
                        ),
                        Visit.id.cast(String).ilike(f"%{search_digits}%"),
                    )
                )
            else:
                # Если нет цифр, ищем только по ФИО
                visits_query = visits_query.join(
                    Patient, Visit.patient_id == Patient.id
                ).filter(Patient.full_name.ilike(f"%{search}%"))

        visits = visits_query.order_by(Visit.created_at.desc()).limit(limit // 2).all()
        for visit in visits:
            # Получаем имя пациента
            patient_fio = None
            if visit.patient_id:
                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )
                if patient:
                    patient_fio = patient.short_name()

            # Получаем услуги визита
            from app.models.service import Service
            from app.models.visit import VisitService

            visit_services = (
                db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            )
            service_names = []
            service_codes = []
            total_amount = 0

            for vs in visit_services:
                service_price = 0
                if vs.price is not None:  # Используем сохраненную цену (включая 0)
                    service_price = float(vs.price)
                elif vs.service_id:  # Fallback - ищем цену в таблице services
                    service = (
                        db.query(Service).filter(Service.id == vs.service_id).first()
                    )
                    if service and service.price:
                        service_price = float(service.price)

                total_amount += service_price * (vs.qty or 1)

                if vs.name:  # Используем сохраненное имя
                    service_names.append(vs.name)
                    if vs.code:
                        service_codes.append(normalize_service_code(vs.code))
                else:  # Fallback - ищем в таблице services
                    service = (
                        db.query(Service).filter(Service.id == vs.service_id).first()
                    )
                    if service:
                        service_names.append(service.name)
                        service_code = service.service_code or get_service_code(
                            service.id, db
                        )
                        if service_code:
                            service_codes.append(service_code)

            # Получаем информацию о номерах в очередях для визита
            queue_numbers = []
            confirmation_status = None

            if visit.visit_date == date.today():
                # Ищем записи в очередях для этого визита
                from app.models.online_queue import DailyQueue, OnlineQueueEntry

                queue_entries = (
                    db.query(OnlineQueueEntry)
                    .filter(OnlineQueueEntry.visit_id == visit.id)
                    .all()
                )

                for entry in queue_entries:
                    queue = (
                        db.query(DailyQueue)
                        .filter(DailyQueue.id == entry.queue_id)
                        .first()
                    )
                    if queue:
                        queue_names = {
                            "ecg": "ЭКГ",
                            "cardiology_common": "Кардиолог",
                            "dermatology": "Дерматолог",
                            "stomatology": "Стоматолог",
                            "cosmetology": "Косметолог",
                            "lab": "Лаборатория",
                            "general": "Общая очередь",
                        }

                        queue_numbers.append(
                            {
                                "queue_tag": queue.queue_tag or "general",
                                "queue_name": queue_names.get(
                                    queue.queue_tag or "general",
                                    queue.queue_tag or "Общая",
                                ),
                                "number": entry.number,
                                "status": entry.status,
                            }
                        )

            # Определяем статус подтверждения
            if visit.status == "pending_confirmation":
                confirmation_status = "pending"
            elif visit.confirmed_at:
                confirmation_status = "confirmed"
            else:
                confirmation_status = "none"

            payment_status, payment_type = _resolve_payment_truth(
                db,
                visit_id=visit.id,
                legacy_paid_at=getattr(visit, 'payment_processed_at', None),
            )
            discount_mode = _normalize_registration_discount_mode(
                getattr(visit, 'discount_mode', None)
            )

            result.append(
                {
                    'id': visit.id + 20000,  # Смещение для избежания конфликтов
                    'appointment_id': None,
                    'visit_id': visit.id,
                    'patient_id': visit.patient_id,
                    'patient_fio': patient_fio,
                    'doctor_id': visit.doctor_id,
                    'department': visit.department,
                    'appointment_date': visit.visit_date,
                    'appointment_time': visit.visit_time,
                    'status': _preserve_operational_status_on_payment(visit.status),
                    'services': service_names,  # Реальные названия услуг
                    'service_codes': service_codes,  # Коды услуг для фильтрации
                    'total_amount': total_amount,  # Общая сумма услуг
                    'payment_status': payment_status,  # [OK] ДОБАВЛЕНО: Статус оплаты
                    'payment_type': payment_type,
                    'discount_mode': discount_mode,  # Тип визита для отображения
                    'approval_status': visit.approval_status,  # [OK] ДОБАВЛЕНО: Статус одобрения для all_free
                    'notes': visit.notes,
                    'created_at': visit.created_at,
                    'source': 'visits',
                    'queue_numbers': queue_numbers,  # Номера в очередях
                    'confirmation_status': confirmation_status,  # Статус подтверждения
                    'confirmed_at': (
                        visit.confirmed_at.isoformat() if visit.confirmed_at else None
                    ),
                    'confirmed_by': visit.confirmed_by,
                }
            )

        # Сортируем по дате создания
        result.sort(key=lambda x: x['created_at'], reverse=True)

        # Применяем пагинацию
        paginated_result = result[offset : offset + limit]

        return {
            "data": paginated_result,
            "total": len(result),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < len(result),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== ЭНДПОИНТ ДЛЯ ОТМЕТКИ ЗАПИСЕЙ ИЗ VISITS КАК ОПЛАЧЕННЫХ =====================


def _preserve_operational_status_on_payment(raw_status: str | None) -> str:
    """Payment is stored separately; old status='paid' data stays in the queue as waiting."""
    if not raw_status or raw_status == "paid":
        return "waiting"
    return raw_status


def _sync_payment_invoices_for_paid_visit(
    db: Session,
    *,
    visit_id: int,
    payment_method: str,
) -> None:
    """Mark linked registrar invoices paid once all their visits have paid Payment rows."""
    from app.models.payment import Payment

    links = (
        db.query(PaymentInvoiceVisit)
        .filter(PaymentInvoiceVisit.visit_id == visit_id)
        .all()
    )
    for link in links:
        invoice = link.invoice
        if not invoice or invoice.status not in {"pending", "processing"}:
            continue

        visit_ids = [invoice_visit.visit_id for invoice_visit in invoice.visits]
        if not visit_ids:
            continue

        paid_visit_ids = {
            row[0]
            for row in (
                db.query(Payment.visit_id)
                .filter(
                    Payment.visit_id.in_(visit_ids),
                    Payment.status == "paid",
                )
                .distinct()
                .all()
            )
        }
        if all(invoice_visit_id in paid_visit_ids for invoice_visit_id in visit_ids):
            invoice.status = "paid"
            invoice.payment_method = payment_method or invoice.payment_method
            invoice.paid_at = datetime.now(UTC)


REGISTRAR_COMMAND_ROLE_BY_ACTION = {
    "mark_paid": {"admin", "registrar", "cashier"},
    "start_visit": {
        "doctor",
        "cardio",
        "cardiology",
        "cardiologist",
        "derma",
        "dermatologist",
        "dentist",
        "lab",
    },
    "complete": {
        "doctor",
        "cardio",
        "cardiology",
        "cardiologist",
        "derma",
        "dermatologist",
        "dentist",
        "lab",
    },
    "cancel": {"admin", "registrar", "cashier", "receptionist", "doctor"},
}

REGISTRAR_SUPPORTED_RECORD_KINDS = {"visit", "online_queue", "appointment"}
REGISTRAR_APPOINTMENT_WORKFLOW_ROLES = {"admin", "registrar", "receptionist"}


def _registrar_user_role_names(user: User | None) -> set[str]:
    role_names: set[str] = set()
    primary_role = getattr(user, "role", None)
    if primary_role:
        role_names.add(str(primary_role).strip().lower())

    for role in getattr(user, "roles", None) or []:
        role_name = getattr(role, "name", None)
        if role_name:
            role_names.add(str(role_name).strip().lower())

    return role_names


def _normalize_registrar_action(action: str | None) -> str:
    return str(action or "").strip().lower().replace("-", "_")


def _normalize_registrar_record_kind(record_kind: str | None) -> str:
    return str(record_kind or "").strip().lower()


def _registrar_command_allowed_roles(
    action: str,
    record_kind: str | None = None,
) -> set[str] | None:
    if (
        record_kind == "appointment"
        and action in {"start_visit", "complete"}
    ):
        return REGISTRAR_APPOINTMENT_WORKFLOW_ROLES
    return REGISTRAR_COMMAND_ROLE_BY_ACTION.get(action)


def _ensure_registrar_command_role(
    user: User | None,
    action: str,
    record_kind: str | None = None,
) -> None:
    allowed_roles = _registrar_command_allowed_roles(action, record_kind)
    if not allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported registrar action: {action}",
        )
    if not (_registrar_user_role_names(user) & allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action is not available for this user",
        )


def _registrar_command_item(
    *,
    record_kind: str,
    record_id: int,
    success: bool,
    skipped: bool = False,
    status_value: str | None = None,
    payment_status: str | None = None,
    error: str | None = None,
    result: dict[str, Any] | None = None,
) -> RegistrarRecordActionItemResponse:
    return RegistrarRecordActionItemResponse(
        record_kind=record_kind,
        record_id=record_id,
        success=success,
        skipped=skipped,
        status=status_value,
        payment_status=payment_status,
        error=error,
        result=result,
    )


def _run_single_registrar_record_action(
    *,
    db: Session,
    current_user: User,
    record: RegistrarRecordRef,
    action: str,
    request: RegistrarRecordActionRequest,
) -> RegistrarRecordActionItemResponse:
    record_kind = _normalize_registrar_record_kind(record.record_kind)
    record_id = record.record_id

    if record_kind not in REGISTRAR_SUPPORTED_RECORD_KINDS:
        return _registrar_command_item(
            record_kind=record_kind,
            record_id=record_id,
            success=False,
            error="unsupported_record_kind",
        )

    try:
        if action == "mark_paid":
            if record_kind == "visit":
                result = mark_visit_as_paid(
                    record_id,
                    payment_req=MarkPaidRequest(
                        amount=request.amount,
                        method=request.method,
                    ),
                    db=db,
                    current_user=current_user,
                )
            elif record_kind == "online_queue":
                result = mark_queue_entry_as_paid(
                    record_id,
                    payment_req=MarkPaidRequest(
                        amount=request.amount,
                        method=request.method,
                    ),
                    db=db,
                    current_user=current_user,
                )
            else:
                appointment = crud_appointment.get(db, id=record_id)
                if not appointment:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Appointment not found",
                    )
                if str(appointment.status or "").lower() == "paid":
                    return _registrar_command_item(
                        record_kind=record_kind,
                        record_id=record_id,
                        success=True,
                        skipped=True,
                        status_value=appointment.status,
                        payment_status="paid",
                    )
                appointment = crud_appointment.mark_paid(db, appointment_id=record_id)
                if not appointment:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Appointment not found",
                    )
                result = {
                    "id": appointment.id,
                    "status": appointment.status,
                    "payment_status": "paid",
                }
            return _registrar_command_item(
                record_kind=record_kind,
                record_id=record_id,
                success=True,
                status_value=str(result.get("status") or ""),
                payment_status=str(result.get("payment_status") or "") or None,
                result=result,
            )

        if action == "cancel":
            if record_kind == "visit":
                visit = VisitsApiService(db).set_status(
                    visit_id=record_id,
                    status_new="canceled",
                )
                if request.reason:
                    visit.notes = (visit.notes or "") + f"\nCanceled: {request.reason}"
                    db.commit()
                    db.refresh(visit)
                result = {"id": visit.id, "status": visit.status}
            elif record_kind == "online_queue":
                entry = OnlineQueueNewService(db).cancel_entry(entry_id=record_id)
                result = {"id": entry.id, "status": entry.status}
            else:
                appointment = crud_appointment.cancel_appointment(
                    db,
                    appointment_id=record_id,
                )
                if not appointment:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Appointment not found",
                    )
                result = {"id": appointment.id, "status": appointment.status}
            return _registrar_command_item(
                record_kind=record_kind,
                record_id=record_id,
                success=True,
                status_value=str(result.get("status") or ""),
                result=result,
            )

        if action == "start_visit":
            if record_kind == "appointment":
                appointment = crud_appointment.start_visit(db, appointment_id=record_id)
                if not appointment:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Appointment not found",
                    )
                result = {"id": appointment.id, "status": appointment.status}
            elif record_kind == "visit":
                result = start_visit(record_id, db=db, current_user=current_user)
            else:
                from app.api.v1.endpoints.registrar_integration import start_queue_visit

                result = start_queue_visit(
                    record_id,
                    db=db,
                    current_user=current_user,
                )
            status_value = None
            if isinstance(result, dict):
                status_value = result.get("status") or (
                    result.get("entry") or {}
                ).get("status")
            return _registrar_command_item(
                record_kind=record_kind,
                record_id=record_id,
                success=True,
                status_value=str(status_value or ""),
                result=result if isinstance(result, dict) else None,
            )

        if action == "complete":
            if record_kind == "appointment":
                appointment = crud_appointment.complete_visit(db, appointment_id=record_id)
                if not appointment:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Appointment not found",
                    )
                result = {"id": appointment.id, "status": appointment.status}
            elif record_kind == "visit":
                result = complete_visit(record_id, db=db, current_user=current_user)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Complete is not available for online queue records",
                )
            return _registrar_command_item(
                record_kind=record_kind,
                record_id=record_id,
                success=True,
                status_value=str(result.get("status") or ""),
                result=result if isinstance(result, dict) else None,
            )

    except OnlineQueueNewDomainError as exc:
        return _registrar_command_item(
            record_kind=record_kind,
            record_id=record_id,
            success=False,
            error=exc.detail,
        )
    except HTTPException as exc:
        return _registrar_command_item(
            record_kind=record_kind,
            record_id=record_id,
            success=False,
            error=str(exc.detail),
        )

    return _registrar_command_item(
        record_kind=record_kind,
        record_id=record_id,
        success=False,
        error="unsupported_action",
    )


# ============================================================
# === MARK-PAID ENDPOINTS ===
# ============================================================

@router.post("/registrar/visits/{visit_id}/mark-paid")
def mark_visit_as_paid(
    visit_id: int,
    payment_req: MarkPaidRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Cashier")),
):
    """Отметить запись из таблицы visits как оплаченную и создать платеж (SSOT)"""
    try:
        from app.models.visit import Visit
        from app.services.billing_service import BillingService

        # Логирование для диагностики
        logger.info(
            "mark_visit_as_paid: User: %s, Role: %s, Visit ID: %d",
            current_user.username,
            current_user.role,
            visit_id,
        )

        # Находим запись
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("error.not_found")
            )

        # [OK] ИСПРАВЛЕНО: Проверяем, не создан ли уже платеж для этого визита
        from app.models.payment import Payment

        existing_payment = (
            db.query(Payment)
            .filter(Payment.visit_id == visit_id, Payment.status == "paid")
            .first()
        )

        requested_method = (
            str(payment_req.method).strip().lower()
            if payment_req and payment_req.method
            else "cash"
        )

        if not existing_payment:
            # [OK] ИСПРАВЛЕНО: Создаем платеж через SSOT перед пометкой визита как оплаченного
            billing_service = BillingService(db)

            # Рассчитываем сумму визита через SSOT
            total_info = billing_service.calculate_total(
                visit_id=visit_id, discount_mode=visit.discount_mode or "none"
            )
            payment_amount = float(total_info["total"])

            # [OK] ИСПРАВЛЕНО: Используем прямой SQL для создания платежа, чтобы обойти конфликт моделей
            # (BillingPayment и Payment используют одну таблицу, что вызывает проблемы)
            from sqlalchemy import text

            currency = total_info.get("currency", "UZS")
            note = f"Оплата визита {visit_id} через панель кассира"
            paid_at = datetime.now(UTC)

            # Создаем платеж через прямой SQL
            result = db.execute(  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
                text(
                    """
                    INSERT INTO payments
                    (visit_id, amount, currency, method, status, note, paid_at, created_at)
                    VALUES (:visit_id, :amount, :currency, :method, :status, :note, :paid_at, :created_at)
                """
                ),
                {
                    "visit_id": visit_id,
                    "amount": payment_amount,
                    "currency": currency,
                    "method": requested_method,
                    "status": "paid",
                    "note": note,
                    "paid_at": paid_at,
                    "created_at": paid_at,
                },
            )
            db.commit()

            # Получаем созданный платеж
            payment = (
                db.query(Payment)
                .filter(Payment.visit_id == visit_id)
                .order_by(Payment.created_at.desc())
                .first()
            )

            logger.info(
                "mark_visit_as_paid: Создан платеж ID=%d для визита %d, сумма=%s, method=%s",
                payment.id,
                visit_id,
                payment_amount,
                requested_method,
            )
        else:
            logger.warning(
                "mark_visit_as_paid: Платеж уже существует для визита %d, ID=%d",
                visit_id,
                existing_payment.id,
            )

        # [FIX:PAYMENT_STATUS] Payment must not overwrite the operational visit/queue status.
        changed_at = datetime.now(UTC)
        visit.status = _preserve_operational_status_on_payment(visit.status)
        visit.updated_at = changed_at
        _sync_payment_invoices_for_paid_visit(
            db,
            visit_id=visit.id,
            payment_method=(
                existing_payment.method
                if existing_payment and getattr(existing_payment, "method", None)
                else requested_method
            ),
        )
        logger.info(
            "[FIX:PAYMENT_STATUS] Visit marked paid without changing operational status: visit_id=%d, status=%s",
            visit.id,
            visit.status,
        )
        db.commit()
        db.refresh(visit)

        return {
            "id": visit.id,
            "status": visit.status,
            "payment_status": "paid",
            "payment_type": (
                existing_payment.method
                if existing_payment and getattr(existing_payment, "method", None)
                else requested_method
            ),
            "amount": (
                float(existing_payment.amount)
                if existing_payment and getattr(existing_payment, "amount", None) is not None
                else payment_amount
            ),
            "message": "Запись отмечена как оплаченная",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("mark_visit_as_paid: Error: %s", str(e), exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== ЭНДПОИНТ ДЛЯ ОТМЕТКИ ЗАПИСЕЙ ОНЛАЙН-ОЧЕРЕДИ КАК ОПЛАЧЕННЫХ =====================


@router.post("/registrar/queue/entry/{entry_id}/mark-paid")
def mark_queue_entry_as_paid(
    entry_id: int,
    payment_req: MarkPaidRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Cashier")),
):
    """
    Отметить запись OnlineQueueEntry как оплаченную.

    Находит связанный Visit через visit_id и оплачивает его.
    Если visit_id отсутствует, пытается найти Visit по patient_id и дате.
    """
    try:
        from app.models.online_queue import OnlineQueueEntry
        from app.models.visit import Visit
        from app.services.billing_service import BillingService

        logger.info(
            "mark_queue_entry_as_paid: User: %s, Role: %s, Entry ID: %d",
            current_user.username,
            current_user.role,
            entry_id,
        )

        # Находим запись в очереди
        entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Запись очереди с ID {entry_id} не найдена"
            )

        # Пытаемся найти связанный Visit
        visit = None

        # 1. Через visit_id
        if entry.visit_id:
            visit = db.query(Visit).filter(Visit.id == entry.visit_id).first()
            logger.info(f"mark_queue_entry_as_paid: Найден Visit {entry.visit_id} через entry.visit_id")

        if visit and visit.patient_id != entry.patient_id:
            logger.warning(
                "mark_queue_entry_as_paid: entry visit owner mismatch entry_id=%d visit_id=%d",
                entry.id,
                visit.id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Queue entry visit does not belong to the queue patient",
            )

        requested_method = (
            str(payment_req.method).strip().lower()
            if payment_req and payment_req.method
            else "cash"
        )

        if not visit:
            # Legacy fallback: без Visit нельзя создать Payment SSOT, поэтому оставляем queue marker.
            logger.warning(
                f"mark_queue_entry_as_paid: Visit не найден для entry {entry_id}. "
                f"Обновляем только платежный статус."
            )
            entry.status = _preserve_operational_status_on_payment(entry.status)
            entry.discount_mode = "paid"
            entry.updated_at = datetime.now(UTC)
            logger.info(
                "[FIX:PAYMENT_STATUS] Queue entry marked paid without Visit: entry_id=%d, status=%s",
                entry.id,
                entry.status,
            )
            db.commit()
            db.refresh(entry)

            return {
                "id": entry.id,
                "status": entry.status,
                "payment_status": "paid",
                "payment_type": requested_method,
                "message": "Запись в очереди отмечена как оплаченная (Visit не найден)",
            }

        # Проверяем, не создан ли уже платеж для этого визита
        from app.models.payment import Payment

        existing_payment = (
            db.query(Payment)
            .filter(Payment.visit_id == visit.id, Payment.status == "paid")
            .first()
        )

        if not existing_payment:
            # Создаем платеж через SSOT
            billing_service = BillingService(db)
            total_info = billing_service.calculate_total(
                visit_id=visit.id, discount_mode=visit.discount_mode or "none"
            )
            payment_amount = float(total_info["total"])

            from sqlalchemy import text

            currency = total_info.get("currency", "UZS")
            note = f"Оплата визита {visit.id} через запись очереди {entry_id}"
            paid_at = datetime.now(UTC)

            result = db.execute(  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
                text(
                    """
                    INSERT INTO payments
                    (visit_id, amount, currency, method, status, note, paid_at, created_at)
                    VALUES (:visit_id, :amount, :currency, :method, :status, :note, :paid_at, :created_at)
                """
                ),
                {
                    "visit_id": visit.id,
                    "amount": payment_amount,
                    "currency": currency,
                    "method": requested_method,
                    "status": "paid",
                    "note": note,
                    "paid_at": paid_at,
                    "created_at": paid_at,
                },
            )
            db.commit()

            payment = (
                db.query(Payment)
                .filter(Payment.visit_id == visit.id)
                .order_by(Payment.created_at.desc())
                .first()
            )

            logger.info(
                "mark_queue_entry_as_paid: Создан платеж ID=%d для визита %d (через entry %d), сумма=%s, method=%s",
                payment.id,
                visit.id,
                entry_id,
                payment_amount,
                requested_method,
            )
        else:
            logger.info(
                "mark_queue_entry_as_paid: Платеж уже существует для визита %d, ID=%d",
                visit.id,
                existing_payment.id,
            )

        # [FIX:PAYMENT_STATUS] Payment is stored separately; queue operational status stays intact.
        changed_at = datetime.now(UTC)
        visit.status = _preserve_operational_status_on_payment(visit.status)
        visit.updated_at = changed_at

        entry.status = _preserve_operational_status_on_payment(entry.status)
        entry.updated_at = changed_at
        _sync_payment_invoices_for_paid_visit(
            db,
            visit_id=visit.id,
            payment_method=(
                existing_payment.method
                if existing_payment and getattr(existing_payment, "method", None)
                else requested_method
            ),
        )
        logger.info(
            "[FIX:PAYMENT_STATUS] Queue entry marked paid without changing operational status: entry_id=%d, visit_id=%d, entry_status=%s, visit_status=%s",
            entry.id,
            visit.id,
            entry.status,
            visit.status,
        )

        db.commit()
        db.refresh(visit)
        db.refresh(entry)

        return {
            "id": entry.id,
            "visit_id": visit.id,
            "status": visit.status,
            "payment_status": "paid",
            "payment_type": (
                existing_payment.method
                if existing_payment and getattr(existing_payment, "method", None)
                else requested_method
            ),
            "amount": (
                float(existing_payment.amount)
                if existing_payment and getattr(existing_payment, "amount", None) is not None
                else payment_amount
            ),
            "message": "Запись отмечена как оплаченная",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("mark_queue_entry_as_paid: Error: %s", str(e), exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

@router.post("/registrar/visits/{visit_id}/complete")
def complete_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Registrar", "Cashier", "Receptionist", "Doctor")
    ),
):
    """Завершить запись из таблицы visits"""
    try:
        from app.models.visit import Visit

        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("error.not_found")
            )

        _ensure_visit_doctor_access(db, visit, current_user)

        visit.status = "completed"
        visit.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(visit)

        return {"id": visit.id, "status": visit.status, "message": "Запись завершена"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/registrar/visits/{visit_id}/start-visit")
def start_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """Начать прием (в кабинете) для записи из таблицы visits"""
    try:
        from app.models.visit import Visit

        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("error.not_found")
            )

        visit.status = "in_progress"
        visit.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(visit)

        return {"id": visit.id, "status": visit.status, "message": "Прием начат"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


"""
Эндпоинты подтверждения визитов
Временный файл для добавления в registrar_wizard.py
"""

# ===================== ПОДТВЕРЖДЕНИЕ ВИЗИТОВ =====================


@router.post(
    "/registrar/records/actions",
    response_model=RegistrarRecordActionResponse,
)
def run_registrar_record_action(
    request: RegistrarRecordActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Cashier",
            "Receptionist",
            "Doctor",
            "cardio",
            "cardiology",
            "cardiologist",
            "derma",
            "dermatologist",
            "dentist",
            "Lab",
        )
    ),
) -> RegistrarRecordActionResponse:
    """Run registrar-owned record commands through a single backend contract."""

    action = _normalize_registrar_action(request.action)

    records: list[RegistrarRecordRef] = []
    if request.records:
        records.extend(request.records)
    if request.record_kind and request.record_id is not None:
        records.append(
            RegistrarRecordRef(
                record_kind=request.record_kind,
                record_id=request.record_id,
            )
        )

    unique_records: list[RegistrarRecordRef] = []
    seen: set[tuple[str, int]] = set()
    for record in records:
        record_kind = _normalize_registrar_record_kind(record.record_kind)
        key = (record_kind, record.record_id)
        if record.record_id <= 0 or key in seen:
            continue
        seen.add(key)
        unique_records.append(
            RegistrarRecordRef(record_kind=record_kind, record_id=record.record_id)
        )

    if not unique_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No registrar records provided",
        )

    for record in unique_records:
        _ensure_registrar_command_role(
            current_user,
            action,
            record.record_kind,
        )

    results = [
        _run_single_registrar_record_action(
            db=db,
            current_user=current_user,
            record=record,
            action=action,
            request=request,
        )
        for record in unique_records
    ]

    success_count = len([item for item in results if item.success and not item.skipped])
    skipped_count = len([item for item in results if item.success and item.skipped])
    failed_count = len([item for item in results if not item.success])

    return RegistrarRecordActionResponse(
        action=action,
        success=failed_count == 0,
        success_count=success_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        results=results,
    )


class ConfirmVisitRequest(BaseModel):
    confirmation_method: str = Field(default="phone", pattern="^(phone|manual)$")
    confirmed_by: str | None = None  # Номер телефона или ID сотрудника
    notes: str | None = None


class ConfirmVisitResponse(BaseModel):
    success: bool
    message: str
    visit_id: int
    status: str
    queue_numbers: dict[str, Any] | None = None
    print_tickets: list[dict[str, Any]] | None = None


@router.post(
    "/registrar/visits/{visit_id}/confirm", response_model=ConfirmVisitResponse
)
def confirm_visit_by_registrar(
    visit_id: int,
    request: ConfirmVisitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Подтверждение визита регистратором (по телефону)
    Присваивает номера в очередях если визит на сегодня
    """
    try:
        # Находим визит
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("visit.not_found")
            )

        # Проверяем что визит ожидает подтверждения
        if visit.status != "pending_confirmation":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Визит уже имеет статус: {visit.status}",
            )

        # Проверяем что токен не истек
        if (
            visit.confirmation_expires_at
            and visit.confirmation_expires_at < datetime.now(UTC)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Срок подтверждения истек",
            )

        # Подтверждаем визит
        visit.confirmed_at = datetime.now(UTC)
        visit.confirmed_by = request.confirmed_by or f"registrar_{current_user.id}"
        visit.status = "confirmed"

        queue_numbers = {}
        print_tickets = []

        # Если визит на сегодня - присваиваем номера в очередях
        if visit.visit_date == date.today():
            from app.services.visit_confirmation_service import (
                VisitConfirmationDomainError,
            )

            try:
                queue_numbers, print_tickets = _assign_queue_numbers_on_confirmation(
                    db, visit
                )
            except VisitConfirmationDomainError as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.detail)
            visit.status = "open"  # Ready for appointment

        db.commit()
        db.refresh(visit)

        return ConfirmVisitResponse(
            success=True,
            message=f"Визит подтвержден. {'Номера в очередях присвоены.' if queue_numbers else 'Номера будут присвоены утром в день визита.'}",
            visit_id=visit.id,
            status=visit.status,
            queue_numbers=queue_numbers,
            print_tickets=print_tickets,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


def _assign_queue_numbers_on_confirmation(
    db: Session, visit: Visit
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Assign or reuse queue numbers through VisitConfirmationService."""
    from app.services.visit_confirmation_service import VisitConfirmationService

    service = VisitConfirmationService(db)
    queue_numbers_list, print_tickets = service.assign_queue_numbers_on_confirmation(
        visit
    )
    queue_numbers = {item["queue_tag"]: item for item in queue_numbers_list}
    return queue_numbers, print_tickets
