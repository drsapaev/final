"""Service layer for lightweight analytics endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.repositories.analytics_simple_repository import AnalyticsSimpleRepository


@dataclass
class AnalyticsSimpleDomainError(Exception):
    status_code: int
    detail: str


class AnalyticsSimpleApiService:
    """Orchestrates simple analytics payloads for API controllers."""

    def __init__(
        self,
        db,  # type: ignore[no-untyped-def]
        repository: AnalyticsSimpleRepository | None = None,
    ):
        self.repository = repository or AnalyticsSimpleRepository(db)

    def get_quick_stats(self) -> dict[str, Any]:
        try:
            today = date.today()
            return {
                "total_patients": self.repository.count_patients(),
                "today_appointments": self.repository.count_appointments_for_date(today),
                "total_appointments": self.repository.count_appointments(),
                "total_payments": self.repository.count_payments(),
                "date": today.isoformat(),
            }
        except Exception as exc:
            raise AnalyticsSimpleDomainError(
                status_code=500,
                detail=f"Ошибка получения статистики: {exc}",
            ) from exc

    def get_dashboard_data(self) -> dict[str, Any]:
        try:
            today = date.today()
            tomorrow = today + timedelta(days=1)

            return {
                "overview": {
                    "total_patients": self.repository.count_patients(),
                    "total_appointments": self.repository.count_appointments(),
                    "total_payments": self.repository.count_payments(),
                },
                "today": {
                    "appointments": self.repository.count_appointments_for_date(today),
                    "date": today.isoformat(),
                },
                "tomorrow": {
                    "appointments": self.repository.count_appointments_for_date(tomorrow),
                    "date": tomorrow.isoformat(),
                },
            }
        except Exception as exc:
            raise AnalyticsSimpleDomainError(
                status_code=500,
                detail=f"Ошибка получения данных дашборда: {exc}",
            ) from exc

    def get_trends_analytics(self, *, days: int) -> dict[str, Any]:
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            trends = self.repository.list_appointment_trends(
                start_date=start_date,
                end_date=end_date,
            )
            trends_data = [
                {"date": row.date.isoformat(), "appointments": row.count} for row in trends
            ]

            return {
                "period_days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "trends": trends_data,
            }
        except Exception as exc:
            raise AnalyticsSimpleDomainError(
                status_code=500,
                detail=f"Ошибка получения трендов: {exc}",
            ) from exc
