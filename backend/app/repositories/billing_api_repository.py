"""Repository helpers for billing endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.billing import Invoice, InvoiceStatus, InvoiceType
from app.models.payment import Payment


class BillingApiRepository:
    """Encapsulates ORM operations used by billing API endpoints."""

    def __init__(self, db: Session):
        self.db = db

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, instance: Any) -> None:
        self.db.refresh(instance)

    def delete(self, instance: Any) -> None:
        self.db.delete(instance)
        self.db.commit()

    def get_invoice(self, invoice_id: int) -> Invoice | None:
        return self.db.query(Invoice).filter(Invoice.id == invoice_id).first()

    def list_invoices(
        self,
        *,
        skip: int,
        limit: int,
        patient_id: int | None,
        status: InvoiceStatus | None,
        invoice_type: InvoiceType | None,
        date_from: date | None,
        date_to: date | None,
    ) -> list[Invoice]:
        query = self.db.query(Invoice)

        if patient_id:
            query = query.filter(Invoice.patient_id == patient_id)
        if status:
            query = query.filter(Invoice.status == status)
        if invoice_type:
            query = query.filter(Invoice.invoice_type == invoice_type)
        if date_from:
            query = query.filter(Invoice.issue_date >= date_from)
        if date_to:
            query = query.filter(Invoice.issue_date <= date_to)

        return query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()

    def list_payments(
        self,
        *,
        skip: int,
        limit: int,
        date_from: date | None,
        date_to: date | None,
    ) -> list[Payment]:
        query = self.db.query(Payment)

        if date_from:
            query = query.filter(Payment.created_at >= date_from)
        if date_to:
            query = query.filter(Payment.created_at <= date_to)

        return query.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()

    def get_billing_analytics_data(
        self,
        *,
        date_from: date | None,
        date_to: date | None,
    ) -> dict:
        invoice_query = self.db.query(Invoice)
        payment_query = self.db.query(Payment)

        if date_from:
            invoice_query = invoice_query.filter(Invoice.issue_date >= date_from)
            payment_query = payment_query.filter(Payment.payment_date >= date_from)
        if date_to:
            invoice_query = invoice_query.filter(Invoice.issue_date <= date_to)
            payment_query = payment_query.filter(Payment.payment_date <= date_to)

        total_invoices = invoice_query.count()
        total_amount = (
            invoice_query.with_entities(func.sum(Invoice.total_amount)).scalar() or 0
        )
        paid_amount = (
            invoice_query.filter(Invoice.status == InvoiceStatus.PAID)
            .with_entities(func.sum(Invoice.total_amount))
            .scalar()
            or 0
        )
        overdue_amount = (
            invoice_query.filter(Invoice.status == InvoiceStatus.OVERDUE)
            .with_entities(func.sum(Invoice.balance))
            .scalar()
            or 0
        )

        total_payments = payment_query.count()
        payments_amount = (
            payment_query.with_entities(func.sum(Payment.amount)).scalar() or 0
        )

        status_stats = (
            self.db.query(
                Invoice.status,
                func.count(Invoice.id).label("count"),
                func.sum(Invoice.total_amount).label("amount"),
            )
            .group_by(Invoice.status)
            .all()
        )

        return {
            "total_invoices": total_invoices,
            "total_amount": total_amount,
            "paid_amount": paid_amount,
            "overdue_amount": overdue_amount,
            "total_payments": total_payments,
            "payments_amount": payments_amount,
            "status_stats": status_stats,
        }
