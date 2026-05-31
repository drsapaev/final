"""Repository helpers for force majeure endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.refund_deposit import (
    DepositTransaction,
    PatientDeposit,
    RefundRequest,
)


class ForceMajeureApiRepository:
    """Encapsulates ORM operations for force majeure API service."""

    def __init__(self, db: Session):
        self.db = db

    def list_pending_entries_by_ids(
        self,
        entry_ids: list[int],
        *,
        specialist_id: int,
        target_date: date | None,
    ) -> list[OnlineQueueEntry]:
        queue_day = target_date or date.today()
        return (
            self.db.query(OnlineQueueEntry)
            .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
            .filter(
                OnlineQueueEntry.id.in_(entry_ids),
                OnlineQueueEntry.status.in_(["waiting", "called"]),
                DailyQueue.specialist_id == specialist_id,
                DailyQueue.day == queue_day,
            )
            .all()
        )

    def list_refund_requests(
        self,
        *,
        status_filter: str | None,
        patient_id: int | None,
        limit: int,
        offset: int,
    ) -> list[RefundRequest]:
        query = self.db.query(RefundRequest)
        if status_filter:
            query = query.filter(RefundRequest.status == status_filter)
        if patient_id:
            query = query.filter(RefundRequest.patient_id == patient_id)
        return query.order_by(RefundRequest.created_at.desc()).offset(offset).limit(limit).all()

    def get_refund_request(self, request_id: int) -> RefundRequest | None:
        return self.db.query(RefundRequest).filter(RefundRequest.id == request_id).first()

    def list_deposits(
        self,
        *,
        active_only: bool,
        min_balance: float | None,
        limit: int,
        offset: int,
    ) -> list[PatientDeposit]:
        query = self.db.query(PatientDeposit)
        if active_only:
            query = query.filter(PatientDeposit.is_active.is_(True))
        if min_balance:
            query = query.filter(PatientDeposit.balance >= min_balance)
        return query.order_by(PatientDeposit.balance.desc()).offset(offset).limit(limit).all()

    def get_patient_deposit(self, *, patient_id: int) -> PatientDeposit | None:
        return self.db.query(PatientDeposit).filter(PatientDeposit.patient_id == patient_id).first()

    def list_deposit_transactions(
        self,
        *,
        deposit_id: int,
        limit: int,
        offset: int,
    ) -> list[DepositTransaction]:
        return (
            self.db.query(DepositTransaction)
            .filter(DepositTransaction.deposit_id == deposit_id)
            .order_by(DepositTransaction.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def add(self, obj) -> None:
        self.db.add(obj)

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def rollback(self) -> None:
        self.db.rollback()
