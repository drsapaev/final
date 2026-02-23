"""Service layer for billing endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from sqlalchemy.orm import Session

from app.models.billing import InvoiceStatus
from app.repositories.billing_api_repository import BillingApiRepository


@dataclass
class BillingApiDomainError(Exception):
    status_code: int
    detail: str


class BillingApiService:
    """Handles endpoint-level DB logic for billing APIs."""

    def __init__(
        self,
        db: Session,
        repository: BillingApiRepository | None = None,
    ):
        self.repository = repository or BillingApiRepository(db)

    def configure_recurring_invoice(
        self,
        *,
        invoice,
        recurrence_type,
        recurrence_interval: int,
        next_date_calculator: Callable,
    ) -> None:
        invoice.is_recurring = True
        invoice.recurrence_type = recurrence_type
        invoice.recurrence_interval = recurrence_interval
        invoice.next_invoice_date = next_date_calculator(
            invoice.issue_date,
            recurrence_type,
            recurrence_interval,
        )
        self.repository.commit()

    def list_invoices(
        self,
        *,
        skip: int,
        limit: int,
        patient_id: int | None,
        status,
        invoice_type,
        date_from: date | None,
        date_to: date | None,
    ):
        return self.repository.list_invoices(
            skip=skip,
            limit=limit,
            patient_id=patient_id,
            status=status,
            invoice_type=invoice_type,
            date_from=date_from,
            date_to=date_to,
        )

    def get_invoice_or_error(self, *, invoice_id: int):
        invoice = self.repository.get_invoice(invoice_id)
        if not invoice:
            raise BillingApiDomainError(404, "Счет не найден")
        return invoice

    def update_invoice(self, *, invoice_id: int, update_data: dict):
        invoice = self.get_invoice_or_error(invoice_id=invoice_id)
        for field, value in update_data.items():
            setattr(invoice, field, value)
        self.repository.commit()
        self.repository.refresh(invoice)
        return invoice

    def delete_invoice(self, *, invoice_id: int) -> None:
        invoice = self.get_invoice_or_error(invoice_id=invoice_id)
        if invoice.status != InvoiceStatus.DRAFT:
            raise BillingApiDomainError(400, "Можно удалять только черновики")
        self.repository.delete(invoice)

    def list_payments(
        self,
        *,
        skip: int,
        limit: int,
        date_from: date | None,
        date_to: date | None,
    ):
        return self.repository.list_payments(
            skip=skip,
            limit=limit,
            date_from=date_from,
            date_to=date_to,
        )

    @staticmethod
    def serialize_payments(payments) -> list[dict]:
        return [
            {
                "id": payment.id,
                "visit_id": payment.visit_id,
                "amount": float(payment.amount),
                "method": payment.method,
                "status": payment.status,
                "receipt_no": payment.receipt_no,
                "note": payment.note,
                "created_at": payment.created_at,
                "paid_at": payment.paid_at,
            }
            for payment in payments
        ]

    def update_billing_settings(
        self,
        *,
        settings,
        update_data: dict,
        updated_by: int,
    ) -> None:
        for field, value in update_data.items():
            setattr(settings, field, value)
        settings.updated_by = updated_by
        self.repository.commit()

    def get_billing_analytics(
        self,
        *,
        date_from: date | None,
        date_to: date | None,
    ) -> dict:
        data = self.repository.get_billing_analytics_data(
            date_from=date_from,
            date_to=date_to,
        )

        return {
            "period": {"date_from": date_from, "date_to": date_to},
            "summary": {
                "total_invoices": data["total_invoices"],
                "total_amount": data["total_amount"],
                "paid_amount": data["paid_amount"],
                "overdue_amount": data["overdue_amount"],
                "total_payments": data["total_payments"],
                "payments_amount": data["payments_amount"],
                "collection_rate": (
                    (data["paid_amount"] / data["total_amount"] * 100)
                    if data["total_amount"] > 0
                    else 0
                ),
            },
            "status_breakdown": [
                {
                    "status": stat.status,
                    "count": stat.count,
                    "amount": stat.amount or 0,
                }
                for stat in data["status_stats"]
            ],
        }
