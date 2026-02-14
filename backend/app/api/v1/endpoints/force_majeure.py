"""
API endpoints для системы форс-мажора и возвратов
согласно ONLINE_QUEUE_SYSTEM_V2.md разделы 20.3, 20.4

Реализует:
1. Массовый перенос очереди на завтра
2. Массовая отмена с возвратом
3. Управление заявками на возврат
4. Управление депозитами пациентов
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.services.force_majeure_api_service import (
    ForceMajeureApiDomainError,
    ForceMajeureApiService,
)

router = APIRouter()


# ========================= СХЕМЫ =========================


class ForceMajeureTransferRequest(BaseModel):
    """Запрос на массовый перенос очереди"""

    specialist_id: int = Field(..., description="ID специалиста")
    target_date: Optional[date] = Field(None, description="Дата очереди (по умолчанию сегодня)")
    reason: str = Field(..., min_length=5, description="Причина переноса")
    entry_ids: Optional[List[int]] = Field(None, description="ID конкретных записей (все если не указано)")
    send_notifications: bool = Field(True, description="Отправить уведомления пациентам")


class ForceMajeureCancelRequest(BaseModel):
    """Запрос на массовую отмену с возвратом"""

    specialist_id: int = Field(..., description="ID специалиста")
    target_date: Optional[date] = Field(None, description="Дата очереди (по умолчанию сегодня)")
    reason: str = Field(..., min_length=5, description="Причина отмены")
    refund_type: str = Field("deposit", description="Тип возврата: deposit или bank_transfer")
    entry_ids: Optional[List[int]] = Field(None, description="ID конкретных записей (все если не указано)")
    send_notifications: bool = Field(True, description="Отправить уведомления пациентам")


class RefundRequestResponse(BaseModel):
    """Ответ заявки на возврат"""

    id: int
    patient_id: int
    patient_name: Optional[str] = None
    payment_id: int
    original_amount: float
    refund_amount: float
    commission_amount: float
    refund_type: str
    status: str
    reason: Optional[str] = None
    is_automatic: bool
    bank_card_number: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    processed_by_name: Optional[str] = None

    class Config:
        from_attributes = True


class ProcessRefundRequest(BaseModel):
    """Запрос на обработку заявки на возврат"""

    action: str = Field(..., description="Действие: approve, reject, complete")
    rejection_reason: Optional[str] = Field(None, description="Причина отклонения")
    bank_card_number: Optional[str] = Field(None, description="Номер карты для возврата")
    manager_notes: Optional[str] = Field(None, description="Примечания менеджера")


class DepositResponse(BaseModel):
    """Ответ баланса депозита"""

    id: int
    patient_id: int
    patient_name: Optional[str] = None
    balance: float
    currency: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DepositTransactionResponse(BaseModel):
    """Ответ транзакции депозита"""

    id: int
    deposit_id: int
    transaction_type: str
    amount: float
    balance_after: float
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AddDepositRequest(BaseModel):
    """Запрос на пополнение депозита"""

    patient_id: int
    amount: float = Field(..., gt=0)
    description: Optional[str] = None


class UseDepositRequest(BaseModel):
    """Запрос на использование депозита для оплаты"""

    patient_id: int
    amount: float = Field(..., gt=0)
    visit_id: Optional[int] = None
    description: Optional[str] = None


# ========================= ФОРС-МАЖОР =========================


@router.post("/transfer", response_model=Dict[str, Any])
async def transfer_queue_to_tomorrow(
    request: ForceMajeureTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Массовый перенос очереди на завтра (форс-мажор)

    Все перенесённые записи получают высокий приоритет и будут
    первыми в очереди на следующий день.

    Доступно: Admin, Registrar
    """
    try:
        return ForceMajeureApiService(db).transfer_queue_to_tomorrow(
            request=request,
            current_user_id=current_user.id,
        )
    except ForceMajeureApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/cancel-with-refund", response_model=Dict[str, Any])
async def cancel_queue_with_refund(
    request: ForceMajeureCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Массовая отмена очереди с возвратом средств (форс-мажор)

    Создаёт заявки на возврат или зачисляет на депозит в зависимости
    от выбранного типа возврата.

    Доступно: Admin, Registrar
    """
    try:
        return ForceMajeureApiService(db).cancel_queue_with_refund(
            request=request,
            current_user_id=current_user.id,
        )
    except ForceMajeureApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/pending-entries", response_model=List[Dict[str, Any]])
async def get_pending_entries_for_force_majeure(
    specialist_id: int = Query(..., description="ID специалиста"),
    target_date: Optional[date] = Query(None, description="Дата очереди"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Получить записи в ожидании для форс-мажорного переноса/отмены

    Возвращает записи со статусами waiting и called.

    Доступно: Admin, Registrar
    """
    return ForceMajeureApiService(db).get_pending_entries(
        specialist_id=specialist_id,
        target_date=target_date,
    )


# ========================= ЗАЯВКИ НА ВОЗВРАТ =========================


@router.get("/refund-requests", response_model=List[RefundRequestResponse])
async def get_refund_requests(
    status_filter: Optional[str] = Query(None, description="Фильтр по статусу"),
    patient_id: Optional[int] = Query(None, description="Фильтр по пациенту"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier", "Manager")),
):
    """
    Получить список заявок на возврат

    Доступно: Admin, Cashier, Manager
    """
    payload = ForceMajeureApiService(db).get_refund_requests(
        status_filter=status_filter,
        patient_id=patient_id,
        limit=limit,
        offset=offset,
    )
    return [RefundRequestResponse(**item) for item in payload]


@router.get("/refund-requests/{request_id}", response_model=RefundRequestResponse)
async def get_refund_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier", "Manager")),
):
    """
    Получить заявку на возврат по ID

    Доступно: Admin, Cashier, Manager
    """
    try:
        payload = ForceMajeureApiService(db).get_refund_request(request_id=request_id)
        return RefundRequestResponse(**payload)
    except ForceMajeureApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/refund-requests/{request_id}/process", response_model=RefundRequestResponse)
async def process_refund_request(
    request_id: int,
    process_request: ProcessRefundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier", "Manager")),
):
    """
    Обработать заявку на возврат

    Действия:
    - approve: Одобрить заявку
    - reject: Отклонить заявку
    - complete: Завершить (деньги возвращены)

    Доступно: Admin, Cashier, Manager
    """
    service = ForceMajeureApiService(db)
    try:
        payload = service.process_refund_request(
            request_id=request_id,
            process_request=process_request,
            current_user=current_user,
        )
        return RefundRequestResponse(**payload)
    except ForceMajeureApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception:
        service.rollback()
        raise


# ========================= ДЕПОЗИТЫ =========================


@router.get("/deposits", response_model=List[DepositResponse])
async def get_deposits(
    active_only: bool = Query(True, description="Только активные"),
    min_balance: Optional[float] = Query(None, description="Минимальный баланс"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier")),
):
    """
    Получить список депозитов пациентов

    Доступно: Admin, Cashier
    """
    payload = ForceMajeureApiService(db).get_deposits(
        active_only=active_only,
        min_balance=min_balance,
        limit=limit,
        offset=offset,
    )
    return [DepositResponse(**item) for item in payload]


@router.get("/deposits/patient/{patient_id}", response_model=DepositResponse)
async def get_patient_deposit(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier", "Registrar")),
):
    """
    Получить депозит пациента

    Доступно: Admin, Cashier, Registrar
    """
    try:
        payload = ForceMajeureApiService(db).get_patient_deposit(patient_id=patient_id)
        return DepositResponse(**payload)
    except ForceMajeureApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/deposits/{deposit_id}/transactions", response_model=List[DepositTransactionResponse])
async def get_deposit_transactions(
    deposit_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier")),
):
    """
    Получить историю транзакций депозита

    Доступно: Admin, Cashier
    """
    payload = ForceMajeureApiService(db).get_deposit_transactions(
        deposit_id=deposit_id,
        limit=limit,
        offset=offset,
    )
    return [DepositTransactionResponse(**item) for item in payload]


@router.post("/deposits/add", response_model=DepositResponse)
async def add_to_deposit(
    request: AddDepositRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier")),
):
    """
    Пополнить депозит пациента

    Используется для ручного пополнения или возврата средств на депозит.

    Доступно: Admin, Cashier
    """
    service = ForceMajeureApiService(db)
    try:
        payload = service.add_to_deposit(request=request, current_user_id=current_user.id)
        return DepositResponse(**payload)
    except Exception:
        service.rollback()
        raise


@router.post("/deposits/use", response_model=DepositResponse)
async def use_deposit_for_payment(
    request: UseDepositRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier")),
):
    """
    Использовать депозит для оплаты

    Списывает средства с депозита для оплаты визита.

    Доступно: Admin, Cashier
    """
    service = ForceMajeureApiService(db)
    try:
        payload = service.use_deposit_for_payment(
            request=request,
            current_user_id=current_user.id,
        )
        return DepositResponse(**payload)
    except ForceMajeureApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception:
        service.rollback()
        raise
