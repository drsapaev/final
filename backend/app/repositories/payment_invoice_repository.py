"""Repository helpers for payment invoice flows."""

from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

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
