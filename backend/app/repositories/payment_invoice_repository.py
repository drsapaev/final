"""Repository helpers for payment invoice flows."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import insert
from sqlalchemy.orm import Session, selectinload

from app.models.audit import AuditLog
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.visit import Visit


class PaymentInvoiceRepository:
    """Encapsulates ORM operations used by payment invoice service."""

    def __init__(self, db: Session):
        self.db = db

    def add(self, invoice: PaymentInvoice) -> None:
        self.db.add(invoice)

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, invoice: PaymentInvoice) -> None:
        self.db.refresh(invoice)

    def rollback(self) -> None:
        self.db.rollback()

    def list_pending(self, limit: int = 50) -> list[PaymentInvoice]:
        return (
            self.db.query(PaymentInvoice)
            .options(
                selectinload(PaymentInvoice.visits)
                .selectinload(PaymentInvoiceVisit.visit)
                .selectinload(Visit.services)
            )
            .filter(PaymentInvoice.status.in_(["pending", "processing"]))
            .order_by(PaymentInvoice.created_at.desc())
            .limit(limit)
            .all()
        )

    def processing_visit_ids(self, visit_ids: set[int]) -> set[int]:
        if not visit_ids:
            return set()
        rows = (
            self.db.query(PaymentInvoiceVisit.visit_id)
            .join(
                PaymentInvoice,
                PaymentInvoice.id == PaymentInvoiceVisit.invoice_id,
            )
            .filter(
                PaymentInvoiceVisit.visit_id.in_(visit_ids),
                PaymentInvoiceVisit.visit_amount > 0,
                PaymentInvoice.status == "processing",
            )
            .all()
        )
        return {int(row[0]) for row in rows}


def record_invoice_visit_release(
    db: Session,
    invoice: PaymentInvoice,
    *,
    visit_id: int,
    previous_total: Decimal,
    released_amount: Decimal,
    actor_user_id: int | None,
    actor_role: str | None,
) -> None:
    """Append the release in the caller's invoice transaction."""
    db.execute(
        insert(AuditLog.__table__).inline().values(
            action="invoice.cancel_visit",
            event_type="INVOICE.CANCEL_VISIT",
            entity_type="payment_invoice",
            entity_id=invoice.id,
            resource_type="payment_invoice",
            resource_id=str(invoice.id),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            actor_type="staff" if actor_user_id is not None else "system",
            outcome="success",
            payload={
                "visit_id": visit_id,
                "currency": invoice.currency,
                "released_amount": format(released_amount, "f"),
                "previous_total": format(previous_total, "f"),
                "total": format(invoice.total_amount, "f"),
                "previous_status": "pending",
                "status": invoice.status,
            },
        )
    )
