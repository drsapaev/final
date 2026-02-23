"""Service layer for force majeure endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.refund_deposit import (
    DepositTransaction,
    DepositTransactionType,
    PatientDeposit,
    RefundRequestStatus,
    RefundType,
)
from app.repositories.force_majeure_api_repository import ForceMajeureApiRepository
from app.services.force_majeure_service import get_force_majeure_service


@dataclass
class ForceMajeureApiDomainError(Exception):
    status_code: int
    detail: str


class ForceMajeureApiService:
    """Coordinates force majeure domain service and endpoint payload logic."""

    def __init__(
        self,
        db: Session,
        repository: ForceMajeureApiRepository | None = None,
    ):
        self.repository = repository or ForceMajeureApiRepository(db)

    def transfer_queue_to_tomorrow(self, *, request, current_user_id: int) -> dict[str, Any]:
        service = get_force_majeure_service(self.repository.db)
        if request.entry_ids:
            entries = self.repository.list_pending_entries_by_ids(request.entry_ids)
        else:
            entries = service.get_pending_entries(
                specialist_id=request.specialist_id,
                target_date=request.target_date,
            )

        if not entries:
            return {"success": True, "transferred": 0, "message": "Нет записей для переноса"}

        return service.transfer_entries_to_tomorrow(
            entries=entries,
            specialist_id=request.specialist_id,
            reason=request.reason,
            performed_by_id=current_user_id,
            send_notifications=request.send_notifications,
        )

    def cancel_queue_with_refund(self, *, request, current_user_id: int) -> dict[str, Any]:
        service = get_force_majeure_service(self.repository.db)
        try:
            refund_type = RefundType(request.refund_type)
        except ValueError as exc:
            raise ForceMajeureApiDomainError(
                400,
                f"Неверный тип возврата: {request.refund_type}",
            ) from exc

        if request.entry_ids:
            entries = self.repository.list_pending_entries_by_ids(request.entry_ids)
        else:
            entries = service.get_pending_entries(
                specialist_id=request.specialist_id,
                target_date=request.target_date,
            )

        if not entries:
            return {"success": True, "cancelled": 0, "message": "Нет записей для отмены"}

        return service.cancel_entries_with_refund(
            entries=entries,
            reason=request.reason,
            refund_type=refund_type,
            performed_by_id=current_user_id,
            send_notifications=request.send_notifications,
        )

    def get_pending_entries(
        self,
        *,
        specialist_id: int,
        target_date,
    ) -> list[dict[str, Any]]:
        service = get_force_majeure_service(self.repository.db)
        entries = service.get_pending_entries(
            specialist_id=specialist_id,
            target_date=target_date,
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
                "queue_time": entry.queue_time.isoformat() if entry.queue_time else None,
            }
            for entry in entries
        ]

    @staticmethod
    def _patient_short_name(patient) -> str | None:
        if not patient:
            return None
        return patient.short_name() if hasattr(patient, "short_name") else None

    def get_refund_requests(
        self,
        *,
        status_filter: str | None,
        patient_id: int | None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        requests = self.repository.list_refund_requests(
            status_filter=status_filter,
            patient_id=patient_id,
            limit=limit,
            offset=offset,
        )
        return [self._serialize_refund_request(item) for item in requests]

    def get_refund_request(self, *, request_id: int) -> dict[str, Any]:
        req = self.repository.get_refund_request(request_id)
        if not req:
            raise ForceMajeureApiDomainError(404, "Заявка на возврат не найдена")
        return self._serialize_refund_request(req)

    def process_refund_request(
        self,
        *,
        request_id: int,
        process_request,
        current_user,
    ) -> dict[str, Any]:
        req = self.repository.get_refund_request(request_id)
        if not req:
            raise ForceMajeureApiDomainError(404, "Заявка на возврат не найдена")

        action = process_request.action.lower()
        if action == "approve":
            if req.status != RefundRequestStatus.PENDING.value:
                raise ForceMajeureApiDomainError(
                    400,
                    "Можно одобрить только заявки со статусом pending",
                )
            req.status = RefundRequestStatus.APPROVED.value
        elif action == "reject":
            if req.status not in [
                RefundRequestStatus.PENDING.value,
                RefundRequestStatus.APPROVED.value,
            ]:
                raise ForceMajeureApiDomainError(
                    400,
                    "Нельзя отклонить заявку с текущим статусом",
                )
            if not process_request.rejection_reason:
                raise ForceMajeureApiDomainError(400, "Укажите причину отклонения")
            req.status = RefundRequestStatus.REJECTED.value
            req.rejection_reason = process_request.rejection_reason
        elif action == "complete":
            if req.status != RefundRequestStatus.APPROVED.value:
                raise ForceMajeureApiDomainError(
                    400,
                    "Можно завершить только одобренные заявки",
                )
            req.status = RefundRequestStatus.COMPLETED.value
        else:
            raise ForceMajeureApiDomainError(400, f"Неизвестное действие: {action}")

        req.processed_by = current_user.id
        req.processed_at = datetime.utcnow()
        if process_request.bank_card_number:
            req.bank_card_number = process_request.bank_card_number
        if process_request.manager_notes:
            req.manager_notes = process_request.manager_notes

        self.repository.commit()
        self.repository.refresh(req)
        payload = self._serialize_refund_request(req)
        payload["processed_by_name"] = current_user.full_name
        return payload

    def get_deposits(
        self,
        *,
        active_only: bool,
        min_balance: float | None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        deposits = self.repository.list_deposits(
            active_only=active_only,
            min_balance=min_balance,
            limit=limit,
            offset=offset,
        )
        return [self._serialize_deposit(deposit) for deposit in deposits]

    def get_patient_deposit(self, *, patient_id: int) -> dict[str, Any]:
        deposit = self.repository.get_patient_deposit(patient_id=patient_id)
        if not deposit:
            raise ForceMajeureApiDomainError(404, "Депозит пациента не найден")
        return self._serialize_deposit(deposit)

    def get_deposit_transactions(
        self,
        *,
        deposit_id: int,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        transactions = self.repository.list_deposit_transactions(
            deposit_id=deposit_id,
            limit=limit,
            offset=offset,
        )
        return [
            {
                "id": tx.id,
                "deposit_id": tx.deposit_id,
                "transaction_type": tx.transaction_type,
                "amount": float(tx.amount),
                "balance_after": float(tx.balance_after),
                "description": tx.description,
                "created_at": tx.created_at,
            }
            for tx in transactions
        ]

    def add_to_deposit(self, *, request, current_user_id: int) -> dict[str, Any]:
        amount = Decimal(str(request.amount))
        deposit = self.repository.get_patient_deposit(patient_id=request.patient_id)

        if not deposit:
            deposit = PatientDeposit(patient_id=request.patient_id, balance=amount)
            self.repository.add(deposit)
        else:
            deposit.balance += amount

        self.repository.flush()

        transaction = DepositTransaction(
            deposit_id=deposit.id,
            transaction_type=DepositTransactionType.CREDIT.value,
            amount=amount,
            balance_after=deposit.balance,
            description=request.description or "Пополнение депозита",
            performed_by=current_user_id,
        )
        self.repository.add(transaction)
        self.repository.commit()
        self.repository.refresh(deposit)
        return self._serialize_deposit(deposit)

    def use_deposit_for_payment(self, *, request, current_user_id: int) -> dict[str, Any]:
        amount = Decimal(str(request.amount))
        deposit = self.repository.get_patient_deposit(patient_id=request.patient_id)
        if not deposit:
            raise ForceMajeureApiDomainError(404, "Депозит пациента не найден")
        if deposit.balance < amount:
            raise ForceMajeureApiDomainError(
                400,
                f"Недостаточно средств на депозите. Баланс: {deposit.balance}, запрошено: {amount}",
            )
        if not deposit.is_active:
            raise ForceMajeureApiDomainError(400, "Депозит деактивирован")

        deposit.balance -= amount
        self.repository.flush()

        transaction = DepositTransaction(
            deposit_id=deposit.id,
            transaction_type=DepositTransactionType.DEBIT.value,
            amount=amount,
            balance_after=deposit.balance,
            description=request.description or "Оплата визита с депозита",
            visit_id=request.visit_id,
            performed_by=current_user_id,
        )
        self.repository.add(transaction)
        self.repository.commit()
        self.repository.refresh(deposit)
        return self._serialize_deposit(deposit)

    def _serialize_refund_request(self, req) -> dict[str, Any]:
        processed_by_name = req.processor.full_name if req.processor else None
        return {
            "id": req.id,
            "patient_id": req.patient_id,
            "patient_name": self._patient_short_name(req.patient),
            "payment_id": req.payment_id,
            "original_amount": float(req.original_amount),
            "refund_amount": float(req.refund_amount),
            "commission_amount": float(req.commission_amount),
            "refund_type": req.refund_type,
            "status": req.status,
            "reason": req.reason,
            "is_automatic": req.is_automatic,
            "bank_card_number": req.bank_card_number,
            "created_at": req.created_at,
            "processed_at": req.processed_at,
            "processed_by_name": processed_by_name,
        }

    def _serialize_deposit(self, deposit) -> dict[str, Any]:
        return {
            "id": deposit.id,
            "patient_id": deposit.patient_id,
            "patient_name": self._patient_short_name(deposit.patient),
            "balance": float(deposit.balance),
            "currency": deposit.currency,
            "is_active": deposit.is_active,
            "created_at": deposit.created_at,
        }

    def rollback(self) -> None:
        self.repository.rollback()
