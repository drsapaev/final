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
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.refund_deposit import (
    DepositTransaction,
    PatientDeposit,
    RefundRequest,
    RefundRequestStatus,
    RefundType,
    DepositTransactionType
)
from app.models.user import User
from app.services.force_majeure_service import (
    ForceMajeureService,
    get_force_majeure_service
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
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Массовый перенос очереди на завтра (форс-мажор)
    
    Все перенесённые записи получают высокий приоритет и будут
    первыми в очереди на следующий день.
    
    Доступно: Admin, Registrar
    """
    service = get_force_majeure_service(db)
    
    # Получаем записи для переноса
    if request.entry_ids:
        entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.id.in_(request.entry_ids),
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).all()
    else:
        entries = service.get_pending_entries(
            specialist_id=request.specialist_id,
            target_date=request.target_date
        )
    
    if not entries:
        return {
            "success": True,
            "transferred": 0,
            "message": "Нет записей для переноса"
        }
    
    # Выполняем перенос
    result = service.transfer_entries_to_tomorrow(
        entries=entries,
        specialist_id=request.specialist_id,
        reason=request.reason,
        performed_by_id=current_user.id,
        send_notifications=request.send_notifications
    )
    
    return result


@router.post("/cancel-with-refund", response_model=Dict[str, Any])
async def cancel_queue_with_refund(
    request: ForceMajeureCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Массовая отмена очереди с возвратом средств (форс-мажор)
    
    Создаёт заявки на возврат или зачисляет на депозит в зависимости
    от выбранного типа возврата.
    
    Доступно: Admin, Registrar
    """
    service = get_force_majeure_service(db)
    
    # Преобразуем тип возврата
    try:
        refund_type = RefundType(request.refund_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неверный тип возврата: {request.refund_type}"
        )
    
    # Получаем записи для отмены
    if request.entry_ids:
        entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.id.in_(request.entry_ids),
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).all()
    else:
        entries = service.get_pending_entries(
            specialist_id=request.specialist_id,
            target_date=request.target_date
        )
    
    if not entries:
        return {
            "success": True,
            "cancelled": 0,
            "message": "Нет записей для отмены"
        }
    
    # Выполняем отмену
    result = service.cancel_entries_with_refund(
        entries=entries,
        reason=request.reason,
        refund_type=refund_type,
        performed_by_id=current_user.id,
        send_notifications=request.send_notifications
    )
    
    return result


@router.get("/pending-entries", response_model=List[Dict[str, Any]])
async def get_pending_entries_for_force_majeure(
    specialist_id: int = Query(..., description="ID специалиста"),
    target_date: Optional[date] = Query(None, description="Дата очереди"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Получить записи в ожидании для форс-мажорного переноса/отмены
    
    Возвращает записи со статусами waiting и called.
    
    Доступно: Admin, Registrar
    """
    service = get_force_majeure_service(db)
    entries = service.get_pending_entries(
        specialist_id=specialist_id,
        target_date=target_date
    )
    
    return [
        {
            "id": entry.id,
            "number": entry.number,
            "patient_name": entry.patient_name,
            "phone": entry.phone,
            "status": entry.status,
            "services": entry.services,
            "total_amount": entry.total_amount,
            "queue_time": entry.queue_time.isoformat() if entry.queue_time else None
        }
        for entry in entries
    ]


# ========================= ЗАЯВКИ НА ВОЗВРАТ =========================

@router.get("/refund-requests", response_model=List[RefundRequestResponse])
async def get_refund_requests(
    status_filter: Optional[str] = Query(None, description="Фильтр по статусу"),
    patient_id: Optional[int] = Query(None, description="Фильтр по пациенту"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier", "Manager"))
):
    """
    Получить список заявок на возврат
    
    Доступно: Admin, Cashier, Manager
    """
    query = db.query(RefundRequest)
    
    if status_filter:
        query = query.filter(RefundRequest.status == status_filter)
    
    if patient_id:
        query = query.filter(RefundRequest.patient_id == patient_id)
    
    query = query.order_by(RefundRequest.created_at.desc())
    requests = query.offset(offset).limit(limit).all()
    
    result = []
    for req in requests:
        patient_name = None
        if req.patient:
            patient_name = req.patient.short_name() if hasattr(req.patient, 'short_name') else None
        
        processed_by_name = None
        if req.processor:
            processed_by_name = req.processor.full_name
        
        result.append(RefundRequestResponse(
            id=req.id,
            patient_id=req.patient_id,
            patient_name=patient_name,
            payment_id=req.payment_id,
            original_amount=float(req.original_amount),
            refund_amount=float(req.refund_amount),
            commission_amount=float(req.commission_amount),
            refund_type=req.refund_type,
            status=req.status,
            reason=req.reason,
            is_automatic=req.is_automatic,
            bank_card_number=req.bank_card_number,
            created_at=req.created_at,
            processed_at=req.processed_at,
            processed_by_name=processed_by_name
        ))
    
    return result


@router.get("/refund-requests/{request_id}", response_model=RefundRequestResponse)
async def get_refund_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier", "Manager"))
):
    """
    Получить заявку на возврат по ID
    
    Доступно: Admin, Cashier, Manager
    """
    req = db.query(RefundRequest).filter(RefundRequest.id == request_id).first()
    
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка на возврат не найдена"
        )
    
    patient_name = None
    if req.patient:
        patient_name = req.patient.short_name() if hasattr(req.patient, 'short_name') else None
    
    processed_by_name = None
    if req.processor:
        processed_by_name = req.processor.full_name
    
    return RefundRequestResponse(
        id=req.id,
        patient_id=req.patient_id,
        patient_name=patient_name,
        payment_id=req.payment_id,
        original_amount=float(req.original_amount),
        refund_amount=float(req.refund_amount),
        commission_amount=float(req.commission_amount),
        refund_type=req.refund_type,
        status=req.status,
        reason=req.reason,
        is_automatic=req.is_automatic,
        bank_card_number=req.bank_card_number,
        created_at=req.created_at,
        processed_at=req.processed_at,
        processed_by_name=processed_by_name
    )


@router.post("/refund-requests/{request_id}/process", response_model=RefundRequestResponse)
async def process_refund_request(
    request_id: int,
    process_request: ProcessRefundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier", "Manager"))
):
    """
    Обработать заявку на возврат
    
    Действия:
    - approve: Одобрить заявку
    - reject: Отклонить заявку
    - complete: Завершить (деньги возвращены)
    
    Доступно: Admin, Cashier, Manager
    """
    req = db.query(RefundRequest).filter(RefundRequest.id == request_id).first()
    
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заявка на возврат не найдена"
        )
    
    action = process_request.action.lower()
    
    if action == "approve":
        if req.status != RefundRequestStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Можно одобрить только заявки со статусом pending"
            )
        req.status = RefundRequestStatus.APPROVED.value
        
    elif action == "reject":
        if req.status not in [RefundRequestStatus.PENDING.value, RefundRequestStatus.APPROVED.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя отклонить заявку с текущим статусом"
            )
        if not process_request.rejection_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите причину отклонения"
            )
        req.status = RefundRequestStatus.REJECTED.value
        req.rejection_reason = process_request.rejection_reason
        
    elif action == "complete":
        if req.status != RefundRequestStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Можно завершить только одобренные заявки"
            )
        req.status = RefundRequestStatus.COMPLETED.value
        
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неизвестное действие: {action}"
        )
    
    # Обновляем общие поля
    req.processed_by = current_user.id
    req.processed_at = datetime.utcnow()
    
    if process_request.bank_card_number:
        req.bank_card_number = process_request.bank_card_number
    
    if process_request.manager_notes:
        req.manager_notes = process_request.manager_notes
    
    db.commit()
    db.refresh(req)
    
    patient_name = None
    if req.patient:
        patient_name = req.patient.short_name() if hasattr(req.patient, 'short_name') else None
    
    return RefundRequestResponse(
        id=req.id,
        patient_id=req.patient_id,
        patient_name=patient_name,
        payment_id=req.payment_id,
        original_amount=float(req.original_amount),
        refund_amount=float(req.refund_amount),
        commission_amount=float(req.commission_amount),
        refund_type=req.refund_type,
        status=req.status,
        reason=req.reason,
        is_automatic=req.is_automatic,
        bank_card_number=req.bank_card_number,
        created_at=req.created_at,
        processed_at=req.processed_at,
        processed_by_name=current_user.full_name
    )


# ========================= ДЕПОЗИТЫ =========================

@router.get("/deposits", response_model=List[DepositResponse])
async def get_deposits(
    active_only: bool = Query(True, description="Только активные"),
    min_balance: Optional[float] = Query(None, description="Минимальный баланс"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier"))
):
    """
    Получить список депозитов пациентов
    
    Доступно: Admin, Cashier
    """
    query = db.query(PatientDeposit)
    
    if active_only:
        query = query.filter(PatientDeposit.is_active == True)
    
    if min_balance:
        query = query.filter(PatientDeposit.balance >= min_balance)
    
    query = query.order_by(PatientDeposit.balance.desc())
    deposits = query.offset(offset).limit(limit).all()
    
    result = []
    for deposit in deposits:
        patient_name = None
        if deposit.patient:
            patient_name = deposit.patient.short_name() if hasattr(deposit.patient, 'short_name') else None
        
        result.append(DepositResponse(
            id=deposit.id,
            patient_id=deposit.patient_id,
            patient_name=patient_name,
            balance=float(deposit.balance),
            currency=deposit.currency,
            is_active=deposit.is_active,
            created_at=deposit.created_at
        ))
    
    return result


@router.get("/deposits/patient/{patient_id}", response_model=DepositResponse)
async def get_patient_deposit(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier", "Registrar"))
):
    """
    Получить депозит пациента
    
    Доступно: Admin, Cashier, Registrar
    """
    deposit = db.query(PatientDeposit).filter(
        PatientDeposit.patient_id == patient_id
    ).first()
    
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Депозит пациента не найден"
        )
    
    patient_name = None
    if deposit.patient:
        patient_name = deposit.patient.short_name() if hasattr(deposit.patient, 'short_name') else None
    
    return DepositResponse(
        id=deposit.id,
        patient_id=deposit.patient_id,
        patient_name=patient_name,
        balance=float(deposit.balance),
        currency=deposit.currency,
        is_active=deposit.is_active,
        created_at=deposit.created_at
    )


@router.get("/deposits/{deposit_id}/transactions", response_model=List[DepositTransactionResponse])
async def get_deposit_transactions(
    deposit_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier"))
):
    """
    Получить историю транзакций депозита
    
    Доступно: Admin, Cashier
    """
    transactions = db.query(DepositTransaction).filter(
        DepositTransaction.deposit_id == deposit_id
    ).order_by(
        DepositTransaction.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    return [
        DepositTransactionResponse(
            id=t.id,
            deposit_id=t.deposit_id,
            transaction_type=t.transaction_type,
            amount=float(t.amount),
            balance_after=float(t.balance_after),
            description=t.description,
            created_at=t.created_at
        )
        for t in transactions
    ]


@router.post("/deposits/add", response_model=DepositResponse)
async def add_to_deposit(
    request: AddDepositRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier"))
):
    """
    Пополнить депозит пациента
    
    Используется для ручного пополнения или возврата средств на депозит.
    
    Доступно: Admin, Cashier
    """
    amount = Decimal(str(request.amount))
    
    # Получаем или создаём депозит
    deposit = db.query(PatientDeposit).filter(
        PatientDeposit.patient_id == request.patient_id
    ).first()
    
    if not deposit:
        deposit = PatientDeposit(
            patient_id=request.patient_id,
            balance=amount
        )
        db.add(deposit)
    else:
        deposit.balance += amount
    
    db.flush()
    
    # Создаём транзакцию
    transaction = DepositTransaction(
        deposit_id=deposit.id,
        transaction_type=DepositTransactionType.CREDIT.value,
        amount=amount,
        balance_after=deposit.balance,
        description=request.description or "Пополнение депозита",
        performed_by=current_user.id
    )
    db.add(transaction)
    db.commit()
    db.refresh(deposit)
    
    patient_name = None
    if deposit.patient:
        patient_name = deposit.patient.short_name() if hasattr(deposit.patient, 'short_name') else None
    
    return DepositResponse(
        id=deposit.id,
        patient_id=deposit.patient_id,
        patient_name=patient_name,
        balance=float(deposit.balance),
        currency=deposit.currency,
        is_active=deposit.is_active,
        created_at=deposit.created_at
    )


@router.post("/deposits/use", response_model=DepositResponse)
async def use_deposit_for_payment(
    request: UseDepositRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier"))
):
    """
    Использовать депозит для оплаты
    
    Списывает средства с депозита для оплаты визита.
    
    Доступно: Admin, Cashier
    """
    amount = Decimal(str(request.amount))
    
    deposit = db.query(PatientDeposit).filter(
        PatientDeposit.patient_id == request.patient_id
    ).first()
    
    if not deposit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Депозит пациента не найден"
        )
    
    if deposit.balance < amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недостаточно средств на депозите. Баланс: {deposit.balance}, запрошено: {amount}"
        )
    
    if not deposit.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Депозит деактивирован"
        )
    
    deposit.balance -= amount
    db.flush()
    
    # Создаём транзакцию
    transaction = DepositTransaction(
        deposit_id=deposit.id,
        transaction_type=DepositTransactionType.DEBIT.value,
        amount=amount,
        balance_after=deposit.balance,
        description=request.description or "Оплата визита с депозита",
        visit_id=request.visit_id,
        performed_by=current_user.id
    )
    db.add(transaction)
    db.commit()
    db.refresh(deposit)
    
    patient_name = None
    if deposit.patient:
        patient_name = deposit.patient.short_name() if hasattr(deposit.patient, 'short_name') else None
    
    return DepositResponse(
        id=deposit.id,
        patient_id=deposit.patient_id,
        patient_name=patient_name,
        balance=float(deposit.balance),
        currency=deposit.currency,
        is_active=deposit.is_active,
        created_at=deposit.created_at
    )
