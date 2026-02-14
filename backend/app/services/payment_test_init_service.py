"""Service layer for test payment initialization endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.enums import PaymentStatus
from app.repositories.payment_test_init_repository import PaymentTestInitRepository
from app.services.billing_service import BillingService


@dataclass
class PaymentTestInitDomainError(Exception):
    status_code: int
    detail: str


class PaymentTestInitService:
    """Creates test online payments without auth."""

    def __init__(self, db, payment_manager):  # type: ignore[no-untyped-def]
        self.repository = PaymentTestInitRepository(db)
        self.billing_service = BillingService(db)
        self.payment_manager = payment_manager

    def init_test_payment(
        self,
        *,
        visit_id: int,
        provider: str,
        amount: float,
        currency: str,
        description: str | None,
        return_url: str | None,
        cancel_url: str | None,
    ) -> dict[str, Any]:
        try:
            payment = self.billing_service.create_payment(
                visit_id=visit_id,
                amount=float(amount),
                currency=currency,
                method="online",
                status=PaymentStatus.PENDING.value,
                provider=provider,
                commit=False,
            )

            result = self.payment_manager.create_payment(
                provider_name=provider,
                amount=amount,
                currency=currency,
                order_id=str(payment.id),
                description=description or f"Тестовый платеж #{payment.id}",
                return_url=return_url or "http://localhost:5173/payment/success",
                cancel_url=cancel_url or "http://localhost:5173/payment/cancel",
            )

            if result.success:
                payment.provider_payment_id = result.payment_id
                payment.payment_url = result.payment_url
                self.billing_service.update_payment_status(
                    payment_id=payment.id,
                    new_status=PaymentStatus.PROCESSING.value,
                )
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "provider_payment_id": result.payment_id,
                    "payment_url": result.payment_url,
                    "status": "initialized",
                }

            self.billing_service.update_payment_status(
                payment_id=payment.id,
                new_status=PaymentStatus.FAILED.value,
                meta={"error": result.error_message},
            )
            raise PaymentTestInitDomainError(
                status_code=400,
                detail=f"Ошибка инициализации платежа: {result.error_message}",
            )
        except PaymentTestInitDomainError:
            raise
        except Exception as exc:
            self.repository.rollback()
            raise PaymentTestInitDomainError(
                status_code=500, detail=f"Ошибка инициализации платежа: {exc}"
            )
