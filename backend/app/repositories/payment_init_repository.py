"""Repository helpers for payment initialization flow."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.visit import Visit


class PaymentInitRepository:
    """Encapsulates ORM operations used by payment init service."""

    def __init__(self, db: Session):
        self.db = db

    def get_visit(self, visit_id: int) -> Visit | None:
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, obj) -> None:  # type: ignore[no-untyped-def]
        self.db.refresh(obj)

