"""Service layer for payment read endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.enums import PaymentStatus
from app.repositories.payment_read_repository import PaymentReadRepository
from app.services.billing_service import BillingService


@dataclass
class PaymentReadDomainError(Exception):
    status_code: int
    detail: str


class PaymentReadService:
    """Provides payment status and visit payment listing queries."""

    def __init__(self, db, payment_manager=None):  # type: ignore[no-untyped-def]
        self.repository = PaymentReadRepository(db)
        self.billing_service = BillingService(db)
        self.payment_manager = payment_manager

    def get_payment_status(self, *, payment_id: int) -> dict[str, Any]:
        payment = self.repository.get_payment(payment_id)
        if not payment:
            raise PaymentReadDomainError(status_code=404, detail="Платеж не найден")

        if (
            self.payment_manager
            and payment.provider
            and payment.provider_payment_id
            and payment.status
            in [PaymentStatus.PENDING.value, PaymentStatus.PROCESSING.value]
        ):
            result = self.payment_manager.check_payment_status(
                payment.provider, payment.provider_payment_id
            )

            if result.success and result.status and result.status != payment.status:
                meta = {**(payment.provider_data or {}), **(result.provider_data or {})}
                self.billing_service.update_payment_status(
                    payment_id=payment.id, new_status=result.status, meta=meta
                )
                payment = self.repository.get_payment(payment_id)
                if not payment:
                    raise PaymentReadDomainError(
                        status_code=500, detail="Платеж не найден после обновления статуса"
                    )

        return {
            "payment_id": payment.id,
            "status": payment.status,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "provider": payment.provider,
            "provider_payment_id": payment.provider_payment_id,
            "created_at": payment.created_at,
            "paid_at": payment.paid_at,
            "provider_data": payment.provider_data,
        }

    def get_visit_payments(self, *, visit_id: int) -> dict[str, Any]:
        payments = self.repository.list_payments_by_visit(visit_id)
        payment_responses = []
        for payment in payments:
            payment_responses.append(
                {
                    "payment_id": payment.id,
                    "id": payment.id,
                    "status": payment.status,
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "provider": payment.provider,
                    "provider_payment_id": payment.provider_payment_id,
                    "created_at": (
                        payment.created_at.isoformat() if payment.created_at else None
                    ),
                    "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                    "provider_data": payment.provider_data,
                }
            )
        return {"payments": payment_responses, "total": len(payment_responses)}
