"""Repository helpers for global_search endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.global_search_audit import GlobalSearchAudit
from app.models.lab import LabOrder
from app.models.patient import Patient
from app.models.visit import Visit


class GlobalSearchApiRepository:
    """Encapsulates ORM operations used by global search service."""

    def __init__(self, db: Session):
        self.db = db

    def get_patient(self, patient_id: int) -> Patient | None:
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def search_patients(self, *, query: str, limit: int) -> list[Patient]:
        search_term = f"%{query}%"
        return (
            self.db.query(Patient)
            .filter(
                or_(
                    Patient.first_name.ilike(search_term),
                    Patient.last_name.ilike(search_term),
                    Patient.phone.ilike(search_term)
                    if hasattr(Patient, "phone")
                    else False,
                )
            )
            .limit(limit)
            .all()
        )

    def get_visit(self, visit_id: int) -> Visit | None:
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def search_recent_visits_by_patient_name(
        self,
        *,
        query: str,
        since_date: date,
        limit: int,
    ) -> list[Visit]:
        search_term = f"%{query}%"
        return (
            self.db.query(Visit)
            .join(Patient, Visit.patient_id == Patient.id)
            .filter(
                or_(Patient.first_name.ilike(search_term), Patient.last_name.ilike(search_term)),
                Visit.created_at >= since_date,
            )
            .order_by(Visit.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_lab_order(self, order_id: int) -> LabOrder | None:
        return self.db.query(LabOrder).filter(LabOrder.id == order_id).first()

    def search_lab_orders_by_patient_name(self, *, query: str, limit: int) -> list[LabOrder]:
        search_term = f"%{query}%"
        return (
            self.db.query(LabOrder)
            .join(Patient, LabOrder.patient_id == Patient.id)
            .filter(or_(Patient.first_name.ilike(search_term), Patient.last_name.ilike(search_term)))
            .order_by(LabOrder.created_at.desc())
            .limit(limit)
            .all()
        )

    def create_audit(
        self,
        *,
        user_id: int,
        role: str,
        query: str,
        result_types,
        result_count,
        opened_type,
        opened_id,
        created_at,
    ) -> None:
        audit = GlobalSearchAudit(
            user_id=user_id,
            role=role,
            query=query,
            result_types=result_types,
            result_count=result_count,
            opened_type=opened_type,
            opened_id=opened_id,
            created_at=created_at,
        )
        self.db.add(audit)
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
