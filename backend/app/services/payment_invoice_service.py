"""Service layer for payment invoice endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.enums import PaymentStatus
from app.models.payment_invoice import PaymentInvoice
from app.repositories.payment_invoice_repository import PaymentInvoiceRepository


@dataclass
class PaymentInvoiceDomainError(Exception):
    status_code: int
    detail: str


class PaymentInvoiceService:
    """Creates and lists payment invoices."""

    def __init__(self, db):  # type: ignore[no-untyped-def]
        self.repository = PaymentInvoiceRepository(db)

    def create_invoice(
        self,
        *,
        amount: float,
        currency: str,
        provider: str,
        description: str | None,
        patient_info: dict[str, Any] | None,
        created_by_id: int | None,
    ) -> dict[str, Any]:
        try:
            patient_id = self._resolve_patient_id(patient_info)
            provider_data = dict(patient_info or {})
            if created_by_id is not None:
                provider_data["created_by_id"] = created_by_id

            invoice = PaymentInvoice(
                patient_id=patient_id,
                total_amount=amount,
                currency=currency,
                provider=provider,
                status=PaymentStatus.PENDING.value,
                payment_method=provider,
                notes=description,
                provider_data=provider_data or None,
            )

            self.repository.add(invoice)
            self.repository.commit()
            self.repository.refresh(invoice)

            return self._serialize_invoice(invoice)
        except PaymentInvoiceDomainError:
            raise
        except Exception as exc:
            self.repository.rollback()
            raise PaymentInvoiceDomainError(
                status_code=500, detail=f"Ошибка создания счета: {exc}"
            )

    def list_pending_invoices(self, *, limit: int = 50) -> list[dict[str, Any]]:
        try:
            invoices = self.repository.list_pending(limit=limit)
            return [self._serialize_invoice(invoice) for invoice in invoices]
        except Exception as exc:
            raise PaymentInvoiceDomainError(
                status_code=500, detail=f"Ошибка получения счетов: {exc}"
            )

    @staticmethod
    def _resolve_patient_id(patient_info: dict[str, Any] | None) -> int:
        if not patient_info:
            return 0

        for key in ("patient_id", "id"):
            value = patient_info.get(key)
            if value is None:
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                raise PaymentInvoiceDomainError(
                    status_code=400, detail=f"Некорректный patient_id: {value}"
                )
        return 0

    @staticmethod
    def _serialize_invoice(invoice: PaymentInvoice) -> dict[str, Any]:
        return {
            "invoice_id": invoice.id,
            "amount": float(invoice.total_amount),
            "currency": invoice.currency,
            "provider": invoice.provider,
            "status": invoice.status,
            "description": invoice.notes,
            "created_at": invoice.created_at,
        }
