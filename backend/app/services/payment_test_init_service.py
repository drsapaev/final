"""Service layer for test payment initialization endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.models.enums import PaymentStatus
from app.repositories.payment_test_init_repository import PaymentTestInitRepository
from app.services.billing_service import BillingService
from app.services.payment_invariant_service import PaymentInvariantService


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
        self.db = db

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
        current_user: Any = None,
    ) -> dict[str, Any]:
        """Initialize a test online payment.

        Delegates payment creation to
        ``PaymentInvariantService.create_pending_payment(commit=False)``.

        This provides:
        - ``with_for_update()`` lock on Visit row (serializes concurrent inits)
        - Duplicate pending payment check (B1/B4 coordination)
        - ``IntegrityError`` defense-in-depth (degrades to 409)

        The provider redirect flow (payment_url, provider_payment_id) and
        status transitions (pending → processing/failed) are preserved.
        """
        try:
            # Use PaymentInvariantService for race-condition protection.
            # create_pending_payment() acquires with_for_update() on Visit,
            # checks for duplicate pending payments with the same provider,
            # and wraps the insert in IntegrityError defense-in-depth.
            #
            # commit=False because we need to:
            # 1. Set provider_payment_id and payment_url after creation
            # 2. Update payment status to processing/failed
            # 3. Commit everything in one transaction
            payment_service = PaymentInvariantService(self.db)

            # Build current_user if not provided (backward compatibility)
            # — the endpoint always has current_user, but tests may not.
            if current_user is None:
                current_user = type("UserRef", (), {"id": None})()

            payment = payment_service.create_pending_payment(
                visit_id=visit_id,
                amount=Decimal(str(amount)),
                currency=currency,
                method="online",
                provider=provider,
                note=description,
                current_user=current_user,
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
