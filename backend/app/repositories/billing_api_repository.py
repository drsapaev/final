"""Repository helpers for billing endpoints."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, load_only, raiseload

from app.models.billing import Invoice, InvoiceStatus, InvoiceType
from app.models.payment import Payment


def _within_days(query, timestamp, date_from: date | None, date_to: date | None):
    if date_from is not None:
        query = query.filter(timestamp >= datetime.combine(date_from, time.min))
    if date_to is not None:
        query = query.filter(timestamp <= datetime.combine(date_to, time.max))
    return query


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

    def get_invoice(self, invoice_id: int, *, for_update: bool = False) -> Invoice | None:
        query = self.db.query(Invoice).filter(Invoice.id == invoice_id)
        if for_update:
            query = query.with_for_update(of=Invoice).populate_existing()
        return query.first()

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
        query = _within_days(query, Invoice.issue_date, date_from, date_to)
        return query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()

    def list_payments(
        self,
        *,
        skip: int,
        limit: int,
        date_from: date | None,
        date_to: date | None,
    ) -> list[Payment]:
        query = self.db.query(Payment).options(
            load_only(
                Payment.id, Payment.visit_id, Payment.amount, Payment.currency,
                Payment.method, Payment.status, Payment.receipt_no, Payment.note,
                Payment.created_at, Payment.paid_at, raiseload=True,
            ),
            raiseload(Payment.payment_visits),
        )
        query = _within_days(query, Payment.created_at, date_from, date_to)
        return query.order_by(Payment.created_at.desc(), Payment.id.desc()).offset(skip).limit(limit).all()

    def get_billing_analytics_data(
        self,
        *,
        date_from: date | None,
        date_to: date | None,
    ) -> dict:
        invoice_query = _within_days(self.db.query(Invoice), Invoice.issue_date, date_from, date_to)
        payment_query = _within_days(self.db.query(Payment), Payment.created_at, date_from, date_to)

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
            invoice_query.with_entities(
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
