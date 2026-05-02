"""Repository helpers for payment invoice flows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.payment_invoice import PaymentInvoice


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
            .filter(PaymentInvoice.status.in_(["pending", "processing"]))
            .order_by(PaymentInvoice.created_at.desc())
            .limit(limit)
            .all()
        )
