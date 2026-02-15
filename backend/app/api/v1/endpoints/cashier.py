"""Cashier API endpoints."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Generic, List, Optional, TypeVar

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.services.cashier_api_service import CashierApiService

router = APIRouter()


class PendingPaymentItem(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_iin: Optional[str] = None
    visit_id: Optional[int] = None
    visit_ids: List[int] = []
    appointment_id: Optional[int] = None
    services: List[dict[str, Any]] = []
    total_amount: Decimal
    paid_amount: Decimal = Decimal("0")
    remaining_amount: Decimal
    status: str
    created_at: datetime
    queue_number: Optional[str] = None
    department: Optional[str] = None

    class Config:
        from_attributes = True


class PaymentHistoryItem(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    visit_id: Optional[int] = None
    amount: Decimal
    method: str
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None
    note: Optional[str] = None
    cashier_name: Optional[str] = None

    class Config:
        from_attributes = True


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int


class CreatePaymentRequest(BaseModel):
    visit_id: Optional[int] = Field(None, description="ID визита")
    appointment_id: Optional[int] = Field(None, description="ID записи")
    patient_id: Optional[int] = Field(None, description="ID пациента")
    amount: Decimal = Field(..., gt=0, description="Сумма платежа")
    method: str = Field(default="cash", description="Метод оплаты (cash, card)")
    note: Optional[str] = Field(None, description="Примечание")


class PaymentResponse(BaseModel):
    id: int
    visit_id: Optional[int] = None
    patient_id: Optional[int] = None
    amount: Decimal
    method: str
    status: str
    created_at: datetime
    paid_at: Optional[datetime] = None
    note: Optional[str] = None

    class Config:
        from_attributes = True


class CancelPaymentRequest(BaseModel):
    reason: Optional[str] = None


class RefundRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Сумма возврата")
    reason: str = Field(..., min_length=3, description="Причина возврата")


class RefundResponse(BaseModel):
    id: int
    original_amount: Decimal
    refunded_amount: Decimal
    remaining_amount: Decimal
    reason: str
    refunded_at: datetime
    status: str


class CashierStatsResponse(BaseModel):
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


def _service(db: Session) -> CashierApiService:
    return CashierApiService(db)


@router.get("/pending-payments")
async def get_pending_payments(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
    date_from: Optional[date] = Query(None, description="Дата начала"),
    date_to: Optional[date] = Query(None, description="Дата окончания"),
    search: Optional[str] = Query(None, description="Поиск по ФИО пациента"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(20, ge=1, le=100, description="Размер страницы"),
):
    del current_user
    return _service(db).get_pending_payments(
        date_from=date_from,
        date_to=date_to,
        search=search,
        page=page,
        size=size,
    )


@router.get("/stats", response_model=CashierStatsResponse)
async def get_cashier_stats(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
    date_from: Optional[date] = Query(None, description="Дата начала"),
    date_to: Optional[date] = Query(None, description="Дата окончания"),
):
    del current_user
    return _service(db).get_cashier_stats(date_from=date_from, date_to=date_to)


@router.get("/payments/export")
async def export_payments(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
    date_from: Optional[date] = Query(None, description="Дата начала"),
    date_to: Optional[date] = Query(None, description="Дата окончания"),
):
    del current_user
    return _service(db).export_payments(date_from=date_from, date_to=date_to)


@router.get("/payments", response_model=PaginatedResponse[PaymentHistoryItem])
async def get_payments(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
    date_from: Optional[date] = Query(None, description="Дата начала"),
    date_to: Optional[date] = Query(None, description="Дата окончания"),
    search: Optional[str] = Query(None, description="Поиск по пациенту"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Фильтр по статусу (paid/pending/cancelled)",
    ),
    method: Optional[str] = Query(None, description="Фильтр по методу оплаты (cash/card)"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    size: int = Query(20, ge=1, le=100, description="Размер страницы"),
):
    del current_user
    return _service(db).get_payments(
        date_from=date_from,
        date_to=date_to,
        search=search,
        status_filter=status_filter,
        method=method,
        page=page,
        size=size,
    )


@router.post("/payments", response_model=PaymentResponse)
async def create_payment(
    payment_data: CreatePaymentRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
):
    return _service(db).create_payment(payment_data=payment_data, current_user=current_user)


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment_by_id(
    payment_id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
):
    del current_user
    return _service(db).get_payment_by_id(payment_id=payment_id)


@router.post("/payments/{payment_id}/cancel")
async def cancel_payment(
    payment_id: int,
    cancel_data: CancelPaymentRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
):
    del current_user
    return _service(db).cancel_payment(payment_id=payment_id, cancel_data=cancel_data)


@router.post("/visits/{visit_id}/mark-paid")
async def mark_visit_as_paid(
    visit_id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
):
    del current_user
    return _service(db).mark_visit_as_paid(visit_id=visit_id)


@router.post("/payments/{payment_id}/confirm")
async def confirm_payment(
    payment_id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
):
    del current_user
    return _service(db).confirm_payment(payment_id=payment_id)


@router.post("/payments/{payment_id}/refund", response_model=RefundResponse)
async def refund_payment(
    payment_id: int,
    refund_data: RefundRequest,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
):
    return _service(db).refund_payment(
        payment_id=payment_id,
        refund_data=refund_data,
        current_user=current_user,
    )


@router.get("/payments/{payment_id}/receipt")
async def get_payment_receipt(
    payment_id: int,
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
):
    del current_user
    return _service(db).get_payment_receipt(payment_id=payment_id)


@router.get("/stats/hourly", response_model=List[HourlyStatItem])
async def get_hourly_stats(
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.require_roles("Admin", "Cashier")),
    target_date: Optional[date] = Query(
        None,
        description="Дата для статистики (по умолчанию сегодня)",
    ),
):
    del current_user
    rows = _service(db).get_hourly_stats(target_date=target_date)
    return [HourlyStatItem(**row) for row in rows]
