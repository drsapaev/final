"""Repository helpers for cashier endpoints."""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.patient import Patient
from app.models.payment import Payment
from app.models.visit import Visit


class CashierApiRepository:
    """Thin DB access wrapper for cashier service."""

    def __init__(self, db: Session):
        self.db = db

    def query_payments(self):
        return self.db.query(Payment)

    def query_visits(self):
        return self.db.query(Visit)

    def query_active_visits_with_services(self, excluded_statuses: list[str]):
        return (
            self.db.query(Visit)
            .options(joinedload(Visit.services))
            .filter(
                ~Visit.status.in_(excluded_statuses),
                or_(
                    Visit.discount_mode.is_(None),
                    Visit.discount_mode != "paid",
                ),
            )
        )

    def list_patients_by_ids(self, patient_ids: list[int]):
        if not patient_ids:
            return []
        return self.db.query(Patient).filter(Patient.id.in_(patient_ids)).all()

    def list_visits_by_ids(self, visit_ids: list[int]):
        if not visit_ids:
            return []
        return self.db.query(Visit).filter(Visit.id.in_(visit_ids)).all()

    def list_paid_payments_by_visit_ids(self, visit_ids: list[int]):
        if not visit_ids:
            return []
        return (
            self.db.query(Payment)
            .filter(
                Payment.visit_id.in_(visit_ids),
                Payment.status.in_(["paid", "completed"]),
            )
            .all()
        )

    def list_paid_payments_for_visit(self, visit_id: int):
        return (
            self.db.query(Payment)
            .filter(
                Payment.visit_id == visit_id,
                Payment.status.in_(["paid", "completed"]),
            )
            .all()
        )

    def get_payment_by_id(self, payment_id: int):
        return self.db.query(Payment).filter(Payment.id == payment_id).first()

    def get_visit_by_id(self, visit_id: int):
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def get_patient_by_id(self, patient_id: int):
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def add(self, obj) -> None:
        self.db.add(obj)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)
