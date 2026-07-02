"""Service layer for specialized_panels endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.repositories.specialized_panels_api_repository import (
    SpecializedPanelsApiRepository,
)


@dataclass
class SpecializedPanelsApiDomainError(Exception):
    status_code: int
    detail: str


class SpecializedPanelsApiService:
    """Builds responses for specialized panel endpoints."""

    def __init__(
        self,
        db: Session,
        repository: SpecializedPanelsApiRepository | None = None,
    ):
        self.repository = repository or SpecializedPanelsApiRepository(db)

    def get_cardiology_patients(self, *, skip: int, limit: int, search: str | None) -> dict:
        patients, total = self.repository.list_cardiology_patients(
            skip=skip,
            limit=limit,
            search=search,
        )
        return {"patients": patients, "total": total, "skip": skip, "limit": limit}

    def get_cardiology_visits(
        self,
        *,
        skip: int,
        limit: int,
        patient_id: int | None,
        status: str | None,
        start_date: date | None,
        end_date: date | None,
    ) -> dict:
        visits, total = self.repository.list_cardiology_visits(
            skip=skip,
            limit=limit,
            patient_id=patient_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )
        return {"visits": visits, "total": total, "skip": skip, "limit": limit}

    def get_cardiology_analytics(self, *, start_date: date | None, end_date: date | None):
        total_visits, total_revenue, status_stats, daily_stats = (
            self.repository.get_cardiology_analytics(
                start_date=start_date,
                end_date=end_date,
            )
        )
        return {
            "total_visits": total_visits,
            "total_revenue": float(total_revenue),
            "status_breakdown": [
                {"status": stat.status, "count": stat.count} for stat in status_stats
            ],
            "daily_stats": [
                {
                    "date": stat.date.isoformat(),
                    "visits": stat.visits,
                    "revenue": float(stat.revenue or 0),
                }
                for stat in daily_stats
            ],
        }

    def get_dentistry_patients(self, *, skip: int, limit: int, search: str | None) -> dict:
        patients, total = self.repository.list_dentistry_patients(
            skip=skip,
            limit=limit,
            search=search,
        )
        return {"patients": patients, "total": total, "skip": skip, "limit": limit}

    def get_dentistry_visits(
        self,
        *,
        skip: int,
        limit: int,
        patient_id: int | None,
        status: str | None,
        start_date: date | None,
        end_date: date | None,
    ) -> dict:
        visits, total = self.repository.list_dentistry_visits(
            skip=skip,
            limit=limit,
            patient_id=patient_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )
        return {"visits": visits, "total": total, "skip": skip, "limit": limit}

    def get_dentistry_analytics(self, *, start_date: date | None, end_date: date | None):
        total_visits, total_revenue, status_stats, daily_stats = (
            self.repository.get_dentistry_analytics(
                start_date=start_date,
                end_date=end_date,
            )
        )
        return {
            "total_visits": total_visits,
            "total_revenue": float(total_revenue),
            "status_breakdown": [
                {"status": stat.status, "count": stat.count} for stat in status_stats
            ],
            "daily_stats": [
                {
                    "date": stat.date.isoformat(),
                    "visits": stat.visits,
                    "revenue": float(stat.revenue or 0),
                }
                for stat in daily_stats
            ],
        }

    def get_specialized_services(self, *, department: str | None) -> dict:
        services = self.repository.list_specialized_services(department=department)
        return {"services": services, "department": department}

    def get_specialized_patient_history(
        self,
        *,
        patient_id: int,
        department: str | None,
    ) -> dict:
        patient = self.repository.get_patient(patient_id)
        if not patient:
            raise SpecializedPanelsApiDomainError(404, "Пациент не найден")

        visits = self.repository.list_specialized_patient_visits(
            patient_id=patient_id,
            department=department,
        )
        return {
            "patient": patient,
            "visits": visits,
            "department": department,
            "total_visits": len(visits),
        }

    def get_specialized_statistics(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> dict:
        cardiology_visits, cardiology_revenue, dentistry_visits, dentistry_revenue = (
            self.repository.get_specialized_statistics(
                start_date=start_date,
                end_date=end_date,
            )
        )

        return {
            "cardiology": {
                "visits": cardiology_visits,
                "revenue": float(cardiology_revenue),
                "average_visit_value": (
                    float(cardiology_revenue / cardiology_visits)
                    if cardiology_visits > 0
                    else 0
                ),
            },
            "dentistry": {
                "visits": dentistry_visits,
                "revenue": float(dentistry_revenue),
                "average_visit_value": (
                    float(dentistry_revenue / dentistry_visits)
                    if dentistry_visits > 0
                    else 0
                ),
            },
            "total": {
                "visits": cardiology_visits + dentistry_visits,
                "revenue": float(cardiology_revenue + dentistry_revenue),
            },
        }
