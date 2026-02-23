"""Repository helpers for specialized_panels endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit


class SpecializedPanelsApiRepository:
    """Encapsulates ORM queries used by specialized panels endpoints."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _dentistry_filter():
        return or_(
            Service.name.ilike("%стоматолог%"),
            Service.name.ilike("%зуб%"),
            Service.name.ilike("%дентал%"),
        )

    def list_cardiology_patients(self, *, skip: int, limit: int, search: str | None):
        query = (
            self.db.query(Patient)
            .join(Visit)
            .join(Service)
            .filter(Service.name.ilike("%кардиолог%"))
        )

        if search:
            query = query.filter(
                or_(
                    Patient.full_name.ilike(f"%{search}%"),
                    Patient.phone.ilike(f"%{search}%"),
                )
            )

        patients = query.offset(skip).limit(limit).all()
        total = query.count()
        return patients, total

    def list_cardiology_visits(
        self,
        *,
        skip: int,
        limit: int,
        patient_id: int | None,
        status: str | None,
        start_date: date | None,
        end_date: date | None,
    ):
        query = self.db.query(Visit).join(Service).filter(Service.name.ilike("%кардиолог%"))
        if patient_id:
            query = query.filter(Visit.patient_id == patient_id)
        if status:
            query = query.filter(Visit.status == status)
        if start_date:
            query = query.filter(Visit.created_at >= start_date)
        if end_date:
            query = query.filter(Visit.created_at <= end_date)

        visits = query.offset(skip).limit(limit).all()
        total = query.count()
        return visits, total

    def get_cardiology_analytics(self, *, start_date: date | None, end_date: date | None):
        base_query = self.db.query(Visit).join(Service).filter(Service.name.ilike("%кардиолог%"))
        if start_date:
            base_query = base_query.filter(Visit.created_at >= start_date)
        if end_date:
            base_query = base_query.filter(Visit.created_at <= end_date)

        total_visits = base_query.count()
        total_revenue = base_query.with_entities(func.sum(Visit.payment_amount)).scalar() or 0

        status_stats = (
            self.db.query(Visit.status, func.count(Visit.id).label("count"))
            .join(Service)
            .filter(Service.name.ilike("%кардиолог%"))
            .group_by(Visit.status)
            .all()
        )

        daily_stats = (
            self.db.query(
                func.date(Visit.created_at).label("date"),
                func.count(Visit.id).label("visits"),
                func.sum(Visit.payment_amount).label("revenue"),
            )
            .join(Service)
            .filter(Service.name.ilike("%кардиолог%"))
            .group_by(func.date(Visit.created_at))
            .all()
        )

        return total_visits, total_revenue, status_stats, daily_stats

    def list_dentistry_patients(self, *, skip: int, limit: int, search: str | None):
        query = (
            self.db.query(Patient)
            .join(Visit)
            .join(Service)
            .filter(self._dentistry_filter())
        )

        if search:
            query = query.filter(
                or_(
                    Patient.full_name.ilike(f"%{search}%"),
                    Patient.phone.ilike(f"%{search}%"),
                )
            )

        patients = query.offset(skip).limit(limit).all()
        total = query.count()
        return patients, total

    def list_dentistry_visits(
        self,
        *,
        skip: int,
        limit: int,
        patient_id: int | None,
        status: str | None,
        start_date: date | None,
        end_date: date | None,
    ):
        query = self.db.query(Visit).join(Service).filter(self._dentistry_filter())
        if patient_id:
            query = query.filter(Visit.patient_id == patient_id)
        if status:
            query = query.filter(Visit.status == status)
        if start_date:
            query = query.filter(Visit.created_at >= start_date)
        if end_date:
            query = query.filter(Visit.created_at <= end_date)

        visits = query.offset(skip).limit(limit).all()
        total = query.count()
        return visits, total

    def get_dentistry_analytics(self, *, start_date: date | None, end_date: date | None):
        base_query = self.db.query(Visit).join(Service).filter(self._dentistry_filter())
        if start_date:
            base_query = base_query.filter(Visit.created_at >= start_date)
        if end_date:
            base_query = base_query.filter(Visit.created_at <= end_date)

        total_visits = base_query.count()
        total_revenue = base_query.with_entities(func.sum(Visit.payment_amount)).scalar() or 0

        status_stats = (
            self.db.query(Visit.status, func.count(Visit.id).label("count"))
            .join(Service)
            .filter(self._dentistry_filter())
            .group_by(Visit.status)
            .all()
        )

        daily_stats = (
            self.db.query(
                func.date(Visit.created_at).label("date"),
                func.count(Visit.id).label("visits"),
                func.sum(Visit.payment_amount).label("revenue"),
            )
            .join(Service)
            .filter(self._dentistry_filter())
            .group_by(func.date(Visit.created_at))
            .all()
        )

        return total_visits, total_revenue, status_stats, daily_stats

    def list_specialized_services(self, *, department: str | None):
        query = self.db.query(Service)
        if department == "cardiology":
            query = query.filter(Service.name.ilike("%кардиолог%"))
        elif department == "dentistry":
            query = query.filter(self._dentistry_filter())
        return query.all()

    def get_patient(self, patient_id: int) -> Patient | None:
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def list_specialized_patient_visits(self, *, patient_id: int, department: str | None):
        query = self.db.query(Visit).filter(Visit.patient_id == patient_id)
        if department == "cardiology":
            query = query.join(Service).filter(Service.name.ilike("%кардиолог%"))
        elif department == "dentistry":
            query = query.join(Service).filter(self._dentistry_filter())
        return query.order_by(Visit.created_at.desc()).all()

    def get_specialized_statistics(self, *, start_date: date | None, end_date: date | None):
        cardiology_query = self.db.query(Visit).join(Service).filter(Service.name.ilike("%кардиолог%"))
        dentistry_query = self.db.query(Visit).join(Service).filter(self._dentistry_filter())

        if start_date:
            cardiology_query = cardiology_query.filter(Visit.created_at >= start_date)
            dentistry_query = dentistry_query.filter(Visit.created_at >= start_date)
        if end_date:
            cardiology_query = cardiology_query.filter(Visit.created_at <= end_date)
            dentistry_query = dentistry_query.filter(Visit.created_at <= end_date)

        cardiology_visits = cardiology_query.count()
        cardiology_revenue = cardiology_query.with_entities(func.sum(Visit.payment_amount)).scalar() or 0
        dentistry_visits = dentistry_query.count()
        dentistry_revenue = dentistry_query.with_entities(func.sum(Visit.payment_amount)).scalar() or 0

        return cardiology_visits, cardiology_revenue, dentistry_visits, dentistry_revenue
