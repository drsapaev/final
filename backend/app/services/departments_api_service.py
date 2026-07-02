"""Service layer for departments API endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.departments_api_repository import DepartmentsApiRepository


@dataclass
class DepartmentsApiDomainError(Exception):
    status_code: int
    detail: str


class DepartmentsApiService:
    """Builds departments endpoint payloads."""

    def __init__(
        self,
        db: Session,
        repository: DepartmentsApiRepository | None = None,
    ):
        self.repository = repository or DepartmentsApiRepository(db)

    @staticmethod
    def _to_payload(department):  # type: ignore[no-untyped-def]
        return {
            "id": department.id,
            "key": department.key,
            "name": department.name_ru,
            "name_ru": department.name_ru,
            "name_uz": department.name_uz,
            "active": department.active,
            "display_order": department.display_order,
            "icon": department.icon,
            "color": department.color,
            "gradient": department.gradient,
        }

    def get_departments(self, *, active_only: bool) -> dict:
        departments = self.repository.list_departments(active_only=active_only)
        departments_data = [self._to_payload(dept) for dept in departments]
        return {"success": True, "data": departments_data, "count": len(departments_data)}

    def get_department(self, *, department_id: int) -> dict:
        department = self.repository.get_department(department_id)
        if not department:
            raise DepartmentsApiDomainError(status_code=404, detail="Department not found")
        return {"success": True, "data": self._to_payload(department)}
