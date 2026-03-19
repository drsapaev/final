"""Repository helpers for specialized_panels endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit, VisitService


class SpecializedPanelsApiRepository:
    """Encapsulates ORM queries used by specialized panels endpoints."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _cardiology_service_filter():
        return or_(
            Service.name.ilike("%кардиолог%"),
            Service.department_key.ilike("%cardio%"),
            Service.queue_tag.ilike("%cardio%"),
            Service.queue_tag.ilike("%ecg%"),
            Service.queue_tag.ilike("%echo%"),
            Service.code.ilike("K%"),
            Service.service_code.ilike("K%"),
        )

    @staticmethod
    def _dentistry_service_filter():
        return or_(
            Service.name.ilike("%стоматолог%"),
            Service.name.ilike("%зуб%"),
            Service.name.ilike("%дентал%"),
            Service.department_key.ilike("%stomat%"),
            Service.department_key.ilike("%dent%"),
            Service.queue_tag.ilike("%stomat%"),
            Service.queue_tag.ilike("%dent%"),
            Service.code.ilike("S%"),
            Service.service_code.ilike("S%"),
        )

    @classmethod
    def _cardiology_filter(cls):
        return or_(
            Visit.department.ilike("%кардио%"),
            Visit.department.ilike("%cardio%"),
            cls._cardiology_service_filter(),
            VisitService.name.ilike("%кардиолог%"),
            VisitService.name.ilike("%ЭКГ%"),
            VisitService.name.ilike("%ЭхоКГ%"),
            VisitService.code.ilike("K%"),
        )

    @classmethod
    def _dentistry_filter(cls):
        return or_(
            Visit.department.ilike("%стомат%"),
            Visit.department.ilike("%дент%"),
            Visit.department.ilike("%stomat%"),
            Visit.department.ilike("%dent%"),
            cls._dentistry_service_filter(),
            VisitService.name.ilike("%стоматолог%"),
            VisitService.name.ilike("%зуб%"),
            VisitService.name.ilike("%дентал%"),
            VisitService.code.ilike("S%"),
        )

    @staticmethod
    def _patient_search_filter(search: str):
        term = f"%{search}%"
        full_name = func.trim(
            func.coalesce(Patient.last_name, "")
            + " "
            + func.coalesce(Patient.first_name, "")
            + " "
            + func.coalesce(Patient.middle_name, "")
        )
        return or_(
            Patient.last_name.ilike(term),
            Patient.first_name.ilike(term),
            Patient.middle_name.ilike(term),
            Patient.phone.ilike(term),
            full_name.ilike(term),
        )

    def _visit_filter_for_department(self, department: str | None):
        if department == "cardiology":
            return self._cardiology_filter()
        if department == "dentistry":
            return self._dentistry_filter()
        return None

    def _service_filter_for_department(self, department: str | None):
        if department == "cardiology":
            return self._cardiology_service_filter()
        if department == "dentistry":
            return self._dentistry_service_filter()
        return None

    def _patient_query_for_department(self, department: str):
        department_filter = self._visit_filter_for_department(department)
        return (
            self.db.query(Patient)
            .join(Visit, Visit.patient_id == Patient.id)
            .outerjoin(VisitService, VisitService.visit_id == Visit.id)
            .outerjoin(Service, Service.id == VisitService.service_id)
            .filter(department_filter)
        )

    def _patient_total_for_department(self, department: str):
        department_filter = self._visit_filter_for_department(department)
        return (
            self.db.query(func.count(func.distinct(Patient.id)))
            .select_from(Patient)
            .join(Visit, Visit.patient_id == Patient.id)
            .outerjoin(VisitService, VisitService.visit_id == Visit.id)
            .outerjoin(Service, Service.id == VisitService.service_id)
            .filter(department_filter)
        )

    def _visit_query_for_department(self, department: str):
        department_filter = self._visit_filter_for_department(department)
        return (
            self.db.query(Visit)
            .outerjoin(VisitService, VisitService.visit_id == Visit.id)
            .outerjoin(Service, Service.id == VisitService.service_id)
            .filter(department_filter)
        )

    def _visit_id_query_for_department(self, department: str):
        """Select distinct visit ids first to avoid DISTINCT over JSON columns on Visit."""
        department_filter = self._visit_filter_for_department(department)
        return (
            self.db.query(Visit.id)
            .outerjoin(VisitService, VisitService.visit_id == Visit.id)
            .outerjoin(Service, Service.id == VisitService.service_id)
            .filter(department_filter)
            .distinct()
        )

    def _visit_metrics_subquery(
        self,
        *,
        department: str,
        start_date: date | None,
        end_date: date | None,
    ):
        day_expr = func.date(Visit.created_at)
        revenue_expr = func.coalesce(
            func.sum(func.coalesce(VisitService.price, 0) * func.coalesce(VisitService.qty, 1)),
            0,
        )
        query = (
            self.db.query(
                Visit.id.label("visit_id"),
                Visit.status.label("status"),
                day_expr.label("visit_day"),
                revenue_expr.label("revenue"),
            )
            .outerjoin(VisitService, VisitService.visit_id == Visit.id)
            .outerjoin(Service, Service.id == VisitService.service_id)
            .filter(self._visit_filter_for_department(department))
        )
        if start_date:
            query = query.filter(Visit.created_at >= start_date)
        if end_date:
            query = query.filter(Visit.created_at <= end_date)
        return query.group_by(Visit.id, Visit.status, day_expr).subquery()

    def list_cardiology_patients(self, *, skip: int, limit: int, search: str | None):
        query = self._patient_query_for_department("cardiology")
        total_query = self._patient_total_for_department("cardiology")

        if search:
            search_filter = self._patient_search_filter(search)
            query = query.filter(search_filter)
            total_query = total_query.filter(search_filter)

        patients = (
            query.order_by(Patient.last_name.asc(), Patient.first_name.asc(), Patient.id.asc())
            .distinct()
            .offset(skip)
            .limit(limit)
            .all()
        )
        total = total_query.scalar() or 0
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
        base_stmt = (
            select(Visit.id, Visit.created_at)
            .select_from(Visit)
            .outerjoin(VisitService, VisitService.visit_id == Visit.id)
            .outerjoin(Service, Service.id == VisitService.service_id)
            .where(self._visit_filter_for_department("cardiology"))
            .distinct()
        )
        if patient_id:
            base_stmt = base_stmt.where(Visit.patient_id == patient_id)
        if status:
            base_stmt = base_stmt.where(Visit.status == status)
        if start_date:
            base_stmt = base_stmt.where(Visit.created_at >= start_date)
        if end_date:
            base_stmt = base_stmt.where(Visit.created_at <= end_date)

        total = self.db.execute(select(func.count()).select_from(base_stmt.subquery())).scalar() or 0
        visit_ids = [
            row.id
            for row in self.db.execute(
                base_stmt.order_by(Visit.created_at.desc(), Visit.id.desc()).offset(skip).limit(limit)
            ).mappings().all()
        ]
        if not visit_ids:
            return [], total

        visits_map = {
            visit.id: visit
            for visit in self.db.query(Visit).filter(Visit.id.in_(visit_ids)).all()
        }
        visits = [visits_map[visit_id] for visit_id in visit_ids if visit_id in visits_map]
        return visits, total

    def get_cardiology_analytics(self, *, start_date: date | None, end_date: date | None):
        metrics = self._visit_metrics_subquery(
            department="cardiology",
            start_date=start_date,
            end_date=end_date,
        )
        total_visits = self.db.query(func.count()).select_from(metrics).scalar() or 0
        total_revenue = (
            self.db.query(func.coalesce(func.sum(metrics.c.revenue), 0))
            .select_from(metrics)
            .scalar()
            or 0
        )

        status_stats = (
            self.db.query(metrics.c.status.label("status"), func.count().label("count"))
            .select_from(metrics)
            .group_by(metrics.c.status)
            .all()
        )

        daily_stats = (
            self.db.query(
                metrics.c.visit_day.label("date"),
                func.count().label("visits"),
                func.coalesce(func.sum(metrics.c.revenue), 0).label("revenue"),
            )
            .select_from(metrics)
            .group_by(metrics.c.visit_day)
            .all()
        )

        return total_visits, total_revenue, status_stats, daily_stats

    def list_dentistry_patients(self, *, skip: int, limit: int, search: str | None):
        query = self._patient_query_for_department("dentistry")
        total_query = self._patient_total_for_department("dentistry")

        if search:
            search_filter = self._patient_search_filter(search)
            query = query.filter(search_filter)
            total_query = total_query.filter(search_filter)

        patients = (
            query.order_by(Patient.last_name.asc(), Patient.first_name.asc(), Patient.id.asc())
            .distinct()
            .offset(skip)
            .limit(limit)
            .all()
        )
        total = total_query.scalar() or 0
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
        base_stmt = (
            select(Visit.id, Visit.created_at)
            .select_from(Visit)
            .outerjoin(VisitService, VisitService.visit_id == Visit.id)
            .outerjoin(Service, Service.id == VisitService.service_id)
            .where(self._visit_filter_for_department("dentistry"))
            .distinct()
        )
        if patient_id:
            base_stmt = base_stmt.where(Visit.patient_id == patient_id)
        if status:
            base_stmt = base_stmt.where(Visit.status == status)
        if start_date:
            base_stmt = base_stmt.where(Visit.created_at >= start_date)
        if end_date:
            base_stmt = base_stmt.where(Visit.created_at <= end_date)

        total = self.db.execute(select(func.count()).select_from(base_stmt.subquery())).scalar() or 0
        visit_ids = [
            row.id
            for row in self.db.execute(
                base_stmt.order_by(Visit.created_at.desc(), Visit.id.desc()).offset(skip).limit(limit)
            ).mappings().all()
        ]
        if not visit_ids:
            return [], total

        visits_map = {
            visit.id: visit
            for visit in self.db.query(Visit).filter(Visit.id.in_(visit_ids)).all()
        }
        visits = [visits_map[visit_id] for visit_id in visit_ids if visit_id in visits_map]
        return visits, total

    def get_dentistry_analytics(self, *, start_date: date | None, end_date: date | None):
        metrics = self._visit_metrics_subquery(
            department="dentistry",
            start_date=start_date,
            end_date=end_date,
        )
        total_visits = self.db.query(func.count()).select_from(metrics).scalar() or 0
        total_revenue = (
            self.db.query(func.coalesce(func.sum(metrics.c.revenue), 0))
            .select_from(metrics)
            .scalar()
            or 0
        )

        status_stats = (
            self.db.query(metrics.c.status.label("status"), func.count().label("count"))
            .select_from(metrics)
            .group_by(metrics.c.status)
            .all()
        )

        daily_stats = (
            self.db.query(
                metrics.c.visit_day.label("date"),
                func.count().label("visits"),
                func.coalesce(func.sum(metrics.c.revenue), 0).label("revenue"),
            )
            .select_from(metrics)
            .group_by(metrics.c.visit_day)
            .all()
        )

        return total_visits, total_revenue, status_stats, daily_stats

    def list_specialized_services(self, *, department: str | None):
        query = self.db.query(Service)
        department_filter = self._service_filter_for_department(department)
        if department_filter is not None:
            query = query.filter(department_filter)
        return query.all()

    def get_patient(self, patient_id: int) -> Patient | None:
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def list_specialized_patient_visits(self, *, patient_id: int, department: str | None):
        base_stmt = select(Visit.id, Visit.created_at).select_from(Visit).where(Visit.patient_id == patient_id)
        department_filter = self._visit_filter_for_department(department)
        if department_filter is not None:
            base_stmt = (
                base_stmt.outerjoin(VisitService, VisitService.visit_id == Visit.id)
                .outerjoin(Service, Service.id == VisitService.service_id)
                .where(department_filter)
                .distinct()
            )
        visit_ids = [
            row.id
            for row in self.db.execute(
                base_stmt.order_by(Visit.created_at.desc(), Visit.id.desc())
            ).mappings().all()
        ]
        if not visit_ids:
            return []

        visits_map = {
            visit.id: visit
            for visit in self.db.query(Visit).filter(Visit.id.in_(visit_ids)).all()
        }
        return [visits_map[visit_id] for visit_id in visit_ids if visit_id in visits_map]

    def get_specialized_statistics(self, *, start_date: date | None, end_date: date | None):
        cardiology_metrics = self._visit_metrics_subquery(
            department="cardiology",
            start_date=start_date,
            end_date=end_date,
        )
        dentistry_metrics = self._visit_metrics_subquery(
            department="dentistry",
            start_date=start_date,
            end_date=end_date,
        )

        cardiology_visits = (
            self.db.query(func.count()).select_from(cardiology_metrics).scalar() or 0
        )
        cardiology_revenue = (
            self.db.query(func.coalesce(func.sum(cardiology_metrics.c.revenue), 0))
            .select_from(cardiology_metrics)
            .scalar()
            or 0
        )
        dentistry_visits = (
            self.db.query(func.count()).select_from(dentistry_metrics).scalar() or 0
        )
        dentistry_revenue = (
            self.db.query(func.coalesce(func.sum(dentistry_metrics.c.revenue), 0))
            .select_from(dentistry_metrics)
            .scalar()
            or 0
        )

        return cardiology_visits, cardiology_revenue, dentistry_visits, dentistry_revenue
