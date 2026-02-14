"""Service layer for global_search endpoints."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.global_search_api_repository import GlobalSearchApiRepository


class GlobalSearchApiService:
    """Aggregates global search results and handles audit logging."""

    def __init__(
        self,
        db: Session,
        repository: GlobalSearchApiRepository | None = None,
    ):
        self.repository = repository or GlobalSearchApiRepository(db)

    def search_patients(self, *, query: str, limit: int) -> list[dict]:
        results = []
        if query.isdigit():
            patient = self.repository.get_patient(int(query))
            if patient:
                results.append(self._patient_payload(patient))

        for patient in self.repository.search_patients(query=query, limit=limit):
            if not any(result["id"] == patient.id for result in results):
                results.append(self._patient_payload(patient))

        return results[:limit]

    def search_visits(self, *, query: str, limit: int) -> list[dict]:
        results = []
        if query.isdigit():
            visit = self.repository.get_visit(int(query))
            if visit:
                patient = self.repository.get_patient(visit.patient_id)
                results.append(self._visit_payload(visit, patient))

        for visit in self.repository.search_recent_visits_by_patient_name(
            query=query,
            since_date=date.today() - timedelta(days=7),
            limit=limit,
        ):
            if not any(result["id"] == visit.id for result in results):
                patient = self.repository.get_patient(visit.patient_id)
                results.append(self._visit_payload(visit, patient))

        return results[:limit]

    def search_lab_results(self, *, query: str, limit: int) -> list[dict]:
        results = []
        if query.isdigit():
            order = self.repository.get_lab_order(int(query))
            if order:
                patient = (
                    self.repository.get_patient(order.patient_id)
                    if order.patient_id
                    else None
                )
                results.append(self._lab_payload(order, patient))

        for order in self.repository.search_lab_orders_by_patient_name(query=query, limit=limit):
            if not any(result["id"] == order.id for result in results):
                patient = (
                    self.repository.get_patient(order.patient_id)
                    if order.patient_id
                    else None
                )
                results.append(self._lab_payload(order, patient))

        return results[:limit]

    def search_all(self, *, query: str, limit: int):
        patients = self.search_patients(query=query, limit=limit)
        visits = self.search_visits(query=query, limit=limit)
        lab_results = self.search_lab_results(query=query, limit=limit)
        return patients, visits, lab_results

    def log_search_query(
        self,
        *,
        user,
        query: str,
        patients: list[dict],
        visits: list[dict],
        lab_results: list[dict],
        total: int,
    ) -> None:
        result_types = []
        if patients:
            result_types.append("patient")
        if visits:
            result_types.append("visit")
        if lab_results:
            result_types.append("lab")

        role = getattr(user, "role", None) or getattr(user, "role_name", "unknown")
        try:
            self.repository.create_audit(
                user_id=user.id,
                role=str(role),
                query=query[:255],
                result_types=result_types,
                result_count=total,
                opened_type=None,
                opened_id=None,
                created_at=datetime.utcnow(),
            )
        except Exception:
            self.repository.rollback()

    def log_search_click(
        self,
        *,
        user,
        query: str,
        opened_type: str,
        opened_id: int,
    ) -> dict:
        role = getattr(user, "role", None) or getattr(user, "role_name", "unknown")
        try:
            self.repository.create_audit(
                user_id=user.id,
                role=str(role),
                query=query[:255],
                result_types=None,
                result_count=None,
                opened_type=opened_type,
                opened_id=opened_id,
                created_at=datetime.utcnow(),
            )
            return {"status": "ok"}
        except Exception as exc:
            self.repository.rollback()
            return {"status": "error", "message": str(exc)}

    @staticmethod
    def _patient_payload(patient) -> dict:
        return {
            "id": patient.id,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "middle_name": getattr(patient, "middle_name", None),
            "phone": getattr(patient, "phone", None),
            "birth_date": getattr(patient, "birth_date", None),
        }

    @staticmethod
    def _visit_payload(visit, patient) -> dict:
        patient_name = None
        if patient:
            patient_name = f"{patient.last_name or ''} {patient.first_name or ''}".strip()

        return {
            "id": visit.id,
            "patient_id": visit.patient_id,
            "patient_name": patient_name,
            "status": visit.status,
            "visit_date": getattr(visit, "visit_date", None),
            "visit_time": (
                str(getattr(visit, "visit_time", ""))
                if hasattr(visit, "visit_time")
                else None
            ),
            "specialist_name": getattr(visit, "specialist_name", None),
        }

    @staticmethod
    def _lab_payload(order, patient) -> dict:
        patient_name = None
        if patient:
            patient_name = f"{patient.last_name or ''} {patient.first_name or ''}".strip()

        return {
            "id": order.id,
            "patient_id": order.patient_id,
            "patient_name": patient_name,
            "status": order.status,
            "test_type": getattr(order, "notes", None),
            "created_at": order.created_at,
        }
