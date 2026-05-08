from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.departments_endpoint_service import (
    DepartmentsDomainError,
    DepartmentsService,
)


@pytest.mark.unit
class TestDepartmentsService:
    def test_get_departments_returns_wrapped_payload(self):
        repository = SimpleNamespace(
            list_departments=lambda active_only: [
                SimpleNamespace(
                    id=1,
                    key="lab",
                    name_ru="Лаборатория",
                    name_uz="Laboratoriya",
                    active=True,
                    display_order=1,
                    icon="beaker",
                    color="blue",
                    gradient="linear-gradient(...)",
                )
            ]
        )
        service = DepartmentsService(db=None, repository=repository)

        result = service.get_departments(active_only=True)

        assert result["success"] is True
        assert result["count"] == 1
        assert result["data"][0]["key"] == "lab"

    def test_get_department_raises_when_not_found(self):
        repository = SimpleNamespace(get_department=lambda department_id: None)
        service = DepartmentsService(db=None, repository=repository)

        with pytest.raises(DepartmentsDomainError) as exc_info:
            service.get_department(department_id=99)

        assert exc_info.value.status_code == 404

