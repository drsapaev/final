"""
API endpoints для кассира
Специальный модуль для работы с платежами и оплатами через CashierPanel
"""

import logging
from datetime import date, datetime, UTC
from decimal import Decimal
from typing import Any, Generic, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api import deps
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.user import User
from app.models.visit import Visit
from app.services.canonical_visit_service import (
    CanonicalVisitResolutionError,
    CanonicalVisitService,
)
from app.services.notifications import notification_sender_service
from app.services.payment_read_service import PaymentReadService

logger = logging.getLogger(__name__)

class CashierStatsResponse(BaseModel):
    """Агрегированная статистика для кассира"""
    total_amount: Decimal
    cash_amount: Decimal
    card_amount: Decimal
    pending_count: int
    pending_amount: Decimal
    paid_count: int
    cancelled_count: int


class HourlyStatItem(BaseModel):
    hour: int
    count: int
    amount: Decimal


router = APIRouter()


CASHIER_PENDING_EXCLUDED_VISIT_STATUSES = (
    "canceled",
    "cancelled",
    "paid",
    "completed",
    "done",
    "closed",
)


def _preserve_cashier_visit_status(raw_status: str | None) -> str:
    """Payment belongs to Payment/discount_mode; legacy visit.status='paid' becomes operational waiting."""
    if not raw_status or raw_status == "paid":
        return "waiting"
    return raw_status


def _cashier_payment_status(payment: Payment) -> str:
    return str(payment.status or "").strip().lower()


def _cashier_payment_available_amount(payment: Payment) -> Decimal:
    return Decimal(str(payment.amount or 0)) - Decimal(str(payment.refunded_amount or 0))


def _cashier_payment_action_contract(payment: Payment) -> dict[str, Any]:
    payment_status = _cashier_payment_status(payment)
    can_confirm = payment_status not in {"paid", "completed", "cancelled", "refunded", "void"}
    can_cancel = payment_status not in {"cancelled", "refunded", "void"}
    can_refund = payment_status in {"paid", "completed"} and _cashier_payment_available_amount(payment) > 0
    can_print_receipt = True

    action_flags = {
        "confirm": can_confirm,
        "cancel": can_cancel,
        "refund": can_refund,
        "print_receipt": can_print_receipt,
    }
    return {
        "available_actions": [
            action for action, allowed in action_flags.items() if allowed
        ],
        "can_confirm": can_confirm,
        "can_cancel": can_cancel,
        "can_refund": can_refund,
        "can_print_receipt": can_print_receipt,
    }


# ===================== МОДЕЛИ ДЛЯ КАССИРА =====================

class PendingPaymentItem(BaseModel):
    """Элемент ожидающий оплаты (сгруппированный по пациенту)"""
    id: int
    patient_id: int
    patient_name: str
    patient_iin: str | None = None
    visit_id: int | None = None  # Первый visit_id (для совместимости)
    visit_ids: list[int] = []  # Все visit_id этого пациента
    appointment_id: int | None = None
    services: list[dict[str, Any]] = []
    total_amount: Decimal
    paid_amount: Decimal = Decimal("0")
    remaining_amount: Decimal
    status: str
    created_at: datetime
    queue_number: str | None = None
    department: str | None = None
    payment_contract: str = "single_visit"
    payment_visit_id: int | None = None
    payment_visit_ids: list[int] = Field(default_factory=list)
    can_create_direct_payment: bool = True
    can_create_grouped_payment: bool = False

    model_config = ConfigDict(from_attributes=True)


class PaymentHistoryItem(BaseModel):
    """Элемент истории платежей"""
    id: int
    patient_id: int
    patient_name: str
    visit_id: int | None = None
    amount: Decimal
    method: str
    status: str
    created_at: datetime
    paid_at: datetime | None = None
    note: str | None = None
    cashier_name: str | None = None
    available_actions: list[str] = Field(default_factory=list)
    can_confirm: bool = False
    can_cancel: bool = False
    can_refund: bool = False
    can_print_receipt: bool = False

    model_config = ConfigDict(from_attributes=True)


T = TypeVar("T")

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int


class CreatePaymentRequest(BaseModel):
    """Запрос на создание платежа"""
    visit_id: int | None = Field(None, description="ID визита")
    appointment_id: int | None = Field(None, description="ID записи")
    patient_id: int | None = Field(None, description="ID пациента")
    amount: Decimal = Field(..., gt=0, description="Сумма платежа")
    method: str = Field(default="cash", description="Метод оплаты (cash, card)")
    note: str | None = Field(None, description="Примечание")


class PaymentResponse(BaseModel):
    """Ответ при создании/получении платежа"""
    id: int
    visit_id: int | None = None
    patient_id: int | None = None
    amount: Decimal
    method: str
    status: str
    created_at: datetime
    paid_at: datetime | None = None
    note: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CreateGroupedPaymentRequest(BaseModel):
    """Backend-owned allocation request for grouped cashier payment rows."""
    visit_ids: list[int] = Field(..., min_length=1, description="Visit ids from a cashier grouped pending-payment row")
    patient_id: int | None = Field(None, description="Expected patient id for all grouped visits")
    amount: Decimal = Field(..., gt=0, description="Total payment amount to allocate")
    method: str = Field(default="cash", description="Payment method (cash, card)")
    note: str | None = Field(None, description="Payment note")


class GroupedPaymentAllocationItem(BaseModel):
    """One backend-owned payment allocation leg."""
    visit_id: int
    payment_id: int
    amount: Decimal
    remaining_before: Decimal
    remaining_after: Decimal


class GroupedPaymentResponse(BaseModel):
    """Response for backend-owned grouped cashier payment allocation."""
    patient_id: int
    amount: Decimal
    method: str
    status: str
    created_at: datetime
    payments: list[PaymentResponse]
    allocations: list[GroupedPaymentAllocationItem]


class CancelPaymentRequest(BaseModel):
    """Запрос на отмену платежа"""
    reason: str | None = None


class RefundRequest(BaseModel):
    """Запрос на возврат средств"""
    amount: Decimal = Field(..., gt=0, description="Сумма возврата")
    reason: str = Field(..., min_length=3, description="Причина возврата")


class RefundResponse(BaseModel):
    """Ответ на запрос возврата"""
    id: int
    original_amount: Decimal
    refunded_amount: Decimal
    remaining_amount: Decimal
    reason: str
    refunded_at: datetime
    status: str


# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================

def get_patient_name(patient: Patient | None, patient_id: int) -> str:
    """Получить имя пациента"""
    if patient:
        if hasattr(patient, 'short_name') and callable(patient.short_name):
            return patient.short_name()
        elif hasattr(patient, 'fio') and patient.fio:
            return patient.fio
        else:
            # Собираем из полей
            parts = []
            if hasattr(patient, 'last_name') and patient.last_name:
                parts.append(patient.last_name)
            if hasattr(patient, 'first_name') and patient.first_name:
                parts.append(patient.first_name)
            if hasattr(patient, 'middle_name') and patient.middle_name:
                parts.append(patient.middle_name)
            if parts:
                return " ".join(parts)
    return f"Пациент #{patient_id}"


def _decimal_to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cashier_visit_total_amount(visit: Visit) -> Decimal:
    total_cost = Decimal("0")
    if hasattr(visit, "services") and visit.services:
        for visit_service in visit.services:
            price = (
                Decimal(str(visit_service.price))
                if hasattr(visit_service, "price") and visit_service.price
                else Decimal("0")
            )
            quantity = (
                Decimal(str(visit_service.qty))
                if hasattr(visit_service, "qty") and visit_service.qty
                else Decimal("1")
            )
            total_cost += price * quantity

    if total_cost == Decimal("0"):
        if hasattr(visit, "total_price") and visit.total_price:
            total_cost = Decimal(str(visit.total_price))
        elif hasattr(visit, "total_amount") and visit.total_amount:
            total_cost = Decimal(str(visit.total_amount))

    return total_cost


def _cashier_paid_amounts_by_visit_id(db: Session, visit_ids: list[int]) -> dict[int, Decimal]:
    if not visit_ids:
        return {}

    paid_amounts = {visit_id: Decimal("0") for visit_id in visit_ids}
    payments = db.query(Payment).filter(
        Payment.visit_id.in_(visit_ids),
        Payment.status.in_(["paid", "completed"]),
    ).all()
    for payment in payments:
        paid_amounts[payment.visit_id] = paid_amounts.get(payment.visit_id, Decimal("0")) + Decimal(str(payment.amount or 0))
    return paid_amounts


async def _emit_payment_notification(
    *,
    db: Session,
    payment: Payment,
    current_user: Any,
    change_type: str,
    patient_id: int | None = None,
    visit: Visit | None = None,
    reason: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> None:
    """Emit canonical payment_notification for patient inbox without breaking cashier flow."""
    try:
        resolved_visit = visit
        if resolved_visit is None and payment.visit_id:
            resolved_visit = db.query(Visit).filter(Visit.id == payment.visit_id).first()

        resolved_patient_id = patient_id or (resolved_visit.patient_id if resolved_visit else None)
        if not resolved_patient_id:
            return

        patient = db.query(Patient).filter(Patient.id == resolved_patient_id).first()
        if not patient or not patient.user_id:
            return

        recipient = (
            db.query(User)
            .filter(User.id == patient.user_id, User.is_active.is_(True))
            .first()
        )
        if not recipient:
            return

        amount_value = _decimal_to_float(getattr(payment, "amount", None))
        metadata: dict[str, Any] = {
            "payment_id": payment.id,
            "visit_id": payment.visit_id,
            "patient_id": resolved_patient_id,
            "payment_status": payment.status,
            "payment_method": getattr(payment, "method", None),
            "change_type": change_type,
        }
        if amount_value is not None:
            metadata["amount"] = amount_value
        if reason:
            metadata["reason"] = reason
        if extra_metadata:
            metadata.update(extra_metadata)

        title_map = {
            "paid": "Оплата подтверждена",
            "paid_manual": "Оплата подтверждена",
            "cancelled": "Платеж отменен",
            "partial_refund": "Частичный возврат выполнен",
            "full_refund": "Возврат выполнен",
            "failed": "Платеж не выполнен",
        }
        message_map = {
            "paid": "Ваш платеж успешно проведен.",
            "paid_manual": "Ваш платеж подтвержден кассиром.",
            "cancelled": "Платеж был отменен.",
            "partial_refund": "Выполнен частичный возврат по вашему платежу.",
            "full_refund": "Средства по вашему платежу полностью возвращены.",
            "failed": "Не удалось завершить платеж.",
        }
        title = title_map.get(change_type, "Обновление статуса платежа")
        message = message_map.get(change_type, "Статус платежа обновлен.")
        if amount_value is not None:
            message = f"{message} Сумма: {amount_value:,.2f} UZS."

        await notification_sender_service.send_canonical_notification_to_user(
            db=db,
            recipient=recipient,
            event_type="payment_notification",
            title=title,
            message=message,
            source_module="cashier",
            metadata=metadata,
            deep_link="/patient",
            severity="warning" if change_type in {"cancelled", "failed", "full_refund"} else "info",
            priority="high" if change_type in {"cancelled", "failed", "full_refund"} else "normal",
            actor_id=getattr(current_user, "id", None),
            actor_role=getattr(current_user, "role", None),
            entity_type="payment",
            entity_id=str(payment.id),
        )
    except Exception as notify_error:
        logger.warning(
            "[FIX:NOTIFICATIONS] failed to emit payment_notification",
            extra={
                "payment_id": getattr(payment, "id", None),
                "visit_id": getattr(payment, "visit_id", None),
                "change_type": change_type,
                "error": str(notify_error),
            },
        )


# ===================== API ENDPOINTS =====================

