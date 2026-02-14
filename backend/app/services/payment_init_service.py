"""Service layer for payment initialization endpoint."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.core.audit import extract_model_changes, log_critical_change
from app.core.config import settings
from app.models.enums import PaymentStatus
from app.repositories.payment_init_repository import PaymentInitRepository
from app.services.billing_service import BillingService
from app.services.queue_service import queue_service


@dataclass
class PaymentInitDomainError(Exception):
    status_code: int
    detail: str


class PaymentInitService:
    """Orchestrates provider init flow and persistence."""

    def __init__(self, db, payment_manager):  # type: ignore[no-untyped-def]
        self.repository = PaymentInitRepository(db)
        self.payment_manager = payment_manager

    def init_payment(
        self,
        *,
        request: Request,
        current_user_id: int,
        visit_id: int,
        provider: str,
        amount: float,
        currency: str,
        description: str | None,
        return_url: str | None,
        cancel_url: str | None,
    ) -> dict:
        payment = None
        try:
            visit = self.repository.get_visit(visit_id)
            if not visit:
                raise PaymentInitDomainError(status_code=404, detail="Визит не найден")

            supported_providers = self.payment_manager.get_providers_for_currency(currency)
            if provider not in supported_providers:
                return {
                    "success": False,
                    "error_message": (
                        f"Провайдер {provider} не поддерживает валюту {currency}"
                    ),
                }

            billing_service = BillingService(self.repository.db)
            payment = billing_service.create_payment(
                visit_id=visit_id,
                amount=float(amount),
                currency=currency,
                method="online",
                status=PaymentStatus.PENDING.value,
                provider=provider,
                commit=False,
            )

            self.repository.flush()
            _, new_data = extract_model_changes(None, payment)
            log_critical_change(
                db=self.repository.db,
                user_id=current_user_id,
                action="CREATE",
                table_name="payments",
                row_id=payment.id,
                old_data=None,
                new_data=new_data,
                request=request,
                description=(
                    f"Инициализирован платеж ID={payment.id}, провайдер={provider}"
                ),
            )

            now = queue_service.get_local_timestamp(self.repository.db)
            order_id = f"clinic_{payment.id}_{int(now.timestamp())}"

            base_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            final_return_url = return_url or f"{base_url}/payment/success?payment_id={payment.id}"
            final_cancel_url = cancel_url or f"{base_url}/payment/cancel?payment_id={payment.id}"

            result = self.payment_manager.create_payment(
                provider_name=provider,
                amount=amount,
                currency=currency,
                order_id=order_id,
                description=description or f"Оплата визита #{visit.id}",
                return_url=final_return_url,
                cancel_url=final_cancel_url,
            )

            billing_service = BillingService(self.repository.db)
            if result.success:
                payment.provider_payment_id = result.payment_id
                payment.payment_url = result.payment_url
                payment.provider_data = result.provider_data
                billing_service.update_payment_status(
                    payment_id=payment.id,
                    new_status=result.status or "pending",
                    meta=result.provider_data,
                    commit=False,
                )
                self.repository.commit()
                self.repository.refresh(payment)
                return {
                    "success": True,
                    "payment_id": payment.id,
                    "provider_payment_id": result.payment_id,
                    "payment_url": result.payment_url,
                    "status": result.status,
                }

            billing_service.update_payment_status(
                payment_id=payment.id,
                new_status="failed",
                meta={"error": result.error_message},
                commit=False,
            )
            self.repository.commit()
            self.repository.refresh(payment)
            return {
                "success": False,
                "payment_id": payment.id,
                "error_message": result.error_message,
            }
        except PaymentInitDomainError:
            self.repository.rollback()
            raise
        except Exception as exc:
            self.repository.rollback()
            if payment is not None and getattr(payment, "id", None):
                return {
                    "success": False,
                    "payment_id": payment.id,
                    "error_message": f"Ошибка инициализации платежа: {exc}",
                }
            return {
                "success": False,
                "error_message": f"Ошибка инициализации платежа: {exc}",
            }

