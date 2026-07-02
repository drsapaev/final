"""Repository helpers for registrar wizard API."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.payment import Payment


class RegistrarWizardApiRepository:
    """Shared DB session adapter for registrar wizard service."""

    def __init__(self, db: Session):
        self.db = db

    def query(self, *entities):
        return self.db.query(*entities)

    def get_latest_payment_for_visit(self, visit_id: int):
        return (
            self.db.query(Payment)
            .filter(Payment.visit_id == visit_id)
            .order_by(Payment.created_at.desc())
            .first()
        )

    def add(self, obj) -> None:
        self.db.add(obj)

    def delete(self, obj) -> None:
        self.db.delete(obj)

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def rollback(self) -> None:
        self.db.rollback()

    def flush(self) -> None:
        self.db.flush()

    def execute(self, statement, params=None):
        if params is None:
            return self.db.execute(statement)
        return self.db.execute(statement, params)
