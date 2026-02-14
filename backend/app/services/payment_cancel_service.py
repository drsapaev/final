"""Service layer for payment cancellation endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.enums import PaymentStatus
from app.repositories.payment_cancel_repository import PaymentCancelRepository
from app.services.billing_service import BillingService


@dataclass
class PaymentCancelDomainError(Exception):
    status_code: int
    detail: str


class PaymentCancelService:
    """Orchestrates payment cancellation and status updates."""

    def __init__(self, db, payment_manager):  # type: ignore[no-untyped-def]
        self.repository = PaymentCancelRepository(db)
        self.billing_service = BillingService(db)
        self.payment_manager = payment_manager

    def cancel_payment(self, *, payment_id: int) -> dict[str, Any]:
        payment = self.repository.get_payment(payment_id)
        if not payment:
            raise PaymentCancelDomainError(status_code=404, detail="Платеж не найден")

        if payment.status not in [
            PaymentStatus.PENDING.value,
            PaymentStatus.PROCESSING.value,
        ]:
            raise PaymentCancelDomainError(
                status_code=400,
                detail=f"Платеж со статусом {payment.status} нельзя отменить",
            )

        if payment.provider and payment.provider_payment_id:
            result = self.payment_manager.cancel_payment(
                payment.provider, payment.provider_payment_id
            )
            if result.success:
                self.billing_service.update_payment_status(
                    payment_id=payment.id,
                    new_status=PaymentStatus.CANCELLED.value,
                    meta={**(payment.provider_data or {}), **result.provider_data},
                )
            else:
                self.billing_service.update_payment_status(
                    payment_id=payment.id,
                    new_status=PaymentStatus.CANCELLED.value,
                    meta={
                        **(payment.provider_data or {}),
                        "cancel_error": result.error_message,
                    },
                )
        else:
            self.billing_service.update_payment_status(
                payment_id=payment.id, new_status=PaymentStatus.CANCELLED.value
            )

        payment = self.repository.get_payment(payment_id)
        if not payment:
            raise PaymentCancelDomainError(
                status_code=500, detail="Платеж не найден после отмены"
            )

        return {
            "success": True,
            "payment_id": payment.id,
            "status": payment.status,
            "message": "Платеж отменен",
        }
