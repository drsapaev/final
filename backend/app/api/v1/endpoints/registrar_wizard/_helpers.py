"""Registrar wizard helpers, schemas, and utilities.

Split from registrar_wizard.py (3533 LOC → modular).
"""
from __future__ import annotations

"""
API endpoints для мастера регистрации с поддержкой корзины
Расширение существующего registrar_integration.py
"""

import asyncio  # noqa: F401
import logging  # noqa: F401
from datetime import UTC, date, datetime, timedelta  # noqa: F401
from decimal import Decimal  # noqa: F401
from typing import Any  # noqa: F401

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status  # noqa: F401
from pydantic import BaseModel, Field  # noqa: F401
from sqlalchemy import String, literal  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.api.deps import get_db, require_roles  # noqa: F401
from app.crud import clinic as crud_clinic  # noqa: F401
from app.crud import online_queue as crud_queue  # noqa: F401
from app.crud.appointment import appointment as crud_appointment  # noqa: F401
from app.models.clinic import ClinicSettings, Doctor  # noqa: F401
from app.models.doctor_price_override import DoctorPriceOverride  # noqa: F401
from app.models.patient import Patient  # noqa: F401
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit  # noqa: F401
from app.models.service import Service  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.visit import Visit, VisitService  # noqa: F401
from app.services.notifications import notification_sender_service  # noqa: F401
from app.services.online_queue_new_service import (  # noqa: F401
    OnlineQueueNewDomainError,
    OnlineQueueNewService,
)
from app.services.payment_provider_manager_factory import (
    get_payment_manager,  # noqa: F401
)
from app.services.queue_service import queue_service  # noqa: F401
from app.services.registrar_edit_delta_service import (  # noqa: F401
    RegistrarEditDeltaItem,
    RegistrarEditDeltaService,
)
from app.services.registrar_wizard_queue_assignment_service import (  # noqa: F401
    RegistrarWizardQueueAssignmentService,
)
from app.services.service_mapping import (  # noqa: F401
    get_service_code,
    normalize_service_code,
)
from app.services.visits_api_service import VisitsApiService  # noqa: F401

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

