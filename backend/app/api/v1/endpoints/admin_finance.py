from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud.finance import finance_transaction
from app.models.finance import FinanceTransaction
from app.models.user import User
from app.schemas.finance import (
    FinanceTransactionCreate,
    FinanceTransactionOut,
    FinanceTransactionUpdate,
)

router = APIRouter()


def _serialize_transaction(transaction: FinanceTransaction) -> FinanceTransactionOut:
    patient_name = None
    if transaction.patient:
        patient_name = transaction.patient.short_name()

    doctor_name = None
    if transaction.doctor:
        if transaction.doctor.user:
            doctor_name = transaction.doctor.user.full_name or transaction.doctor.user.username
        if not doctor_name:
            doctor_name = f"Врач #{transaction.doctor.id}"

    return FinanceTransactionOut(
        id=transaction.id,
        type=transaction.type,
        category=transaction.category,
        amount=float(transaction.amount),
        description=transaction.description,
        patient_id=transaction.patient_id,
        doctor_id=transaction.doctor_id,
        patient_name=patient_name,
        doctor_name=doctor_name,
        payment_method=transaction.payment_method,
        status=transaction.status,
        transaction_date=transaction.transaction_date,
        notes=transaction.notes,
        reference=transaction.reference,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
    )


@router.get("/admin/finance/transactions", response_model=list[FinanceTransactionOut])
def list_finance_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=5000),
    type: str | None = Query(None, description="Фильтр по типу операции"),
    status: str | None = Query(None, description="Фильтр по статусу"),
    category: str | None = Query(None, description="Фильтр по категории"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    transactions = finance_transaction.get_multi(
        db,
        skip=skip,
        limit=limit,
        type=type,
        status=status,
        category=category,
    )
    return [_serialize_transaction(transaction) for transaction in transactions]


@router.post("/admin/finance/transactions", response_model=FinanceTransactionOut)
def create_finance_transaction(
    transaction_in: FinanceTransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    try:
        transaction = finance_transaction.create(db, obj_in=transaction_in)
        return _serialize_transaction(transaction)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("/admin/finance/transactions/{transaction_id}", response_model=FinanceTransactionOut)
def get_finance_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    transaction = finance_transaction.get(db, transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Транзакция с ID {transaction_id} не найдена",
        )
    return _serialize_transaction(transaction)


@router.put("/admin/finance/transactions/{transaction_id}", response_model=FinanceTransactionOut)
def update_finance_transaction(
    transaction_id: int,
    transaction_in: FinanceTransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    transaction = finance_transaction.get(db, transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Транзакция с ID {transaction_id} не найдена",
        )
    try:
        updated = finance_transaction.update(db, db_obj=transaction, obj_in=transaction_in)
        return _serialize_transaction(updated)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.delete("/admin/finance/transactions/{transaction_id}", response_model=dict[str, Any])
def delete_finance_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    transaction = finance_transaction.get(db, transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Транзакция с ID {transaction_id} не найдена",
        )

    removed = finance_transaction.remove(db, id=transaction_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось удалить финансовую транзакцию",
        )

    return {"success": True, "message": f"Транзакция {transaction_id} удалена"}
