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

    def get_available_providers(self) -> dict[str, Any]:
        if self.payment_manager is None:
            raise PaymentReadDomainError(
                status_code=500, detail="Менеджер платежных провайдеров не настроен"
            )

        provider_info = self.payment_manager.get_provider_info()
        providers = []
        for code, info in provider_info.items():
            providers.append(
                {
                    "name": info["name"],
                    "code": code,
                    "supported_currencies": info["supported_currencies"],
                    "is_active": True,
                    "features": info["features"],
                }
            )
        return {"providers": providers}

    def list_payments(
        self,
        *,
        visit_id: int | None,
        date_from: str | None,
        date_to: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        payment_responses = self.billing_service.get_payments_list(
            visit_id=visit_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
        return {"payments": payment_responses, "total": len(payment_responses)}

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

    def generate_receipt(self, *, payment_id: int, format_type: str) -> dict[str, Any]:
        payment = self.repository.get_payment(payment_id)
        if not payment:
            raise PaymentReadDomainError(status_code=404, detail="Платеж не найден")

        receipt_data = {
            "payment_id": payment.id,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "status": payment.status,
            "provider": payment.provider,
            "created_at": payment.created_at.isoformat() if payment.created_at else None,
            "description": "Оплата медицинских услуг",
        }
        return {
            "success": True,
            "receipt_data": receipt_data,
            "receipt_url": f"/api/v1/payments/{payment_id}/receipt/download",
            "format": format_type,
        }

    def build_receipt_content(self, *, payment_id: int) -> str:
        payment = self.repository.get_payment(payment_id)
        if not payment:
            raise PaymentReadDomainError(status_code=404, detail="Платеж не найден")

        provider = payment.provider.title() if payment.provider else "—"
        created_at = payment.created_at.strftime("%d.%m.%Y %H:%M") if payment.created_at else "—"
        return f"""
КВИТАНЦИЯ ОБ ОПЛАТЕ
===================

Номер платежа: {payment.id}
Дата: {created_at}
Сумма: {payment.amount} {payment.currency}
Провайдер: {provider}
Статус: {payment.status.title()}

Описание: Оплата медицинских услуг

Спасибо за использование наших услуг!
        """.strip()
