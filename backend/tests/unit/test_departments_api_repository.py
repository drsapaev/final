from __future__ import annotations

import pytest

from app.models.department import Department
from app.repositories.departments_api_repository import DepartmentsApiRepository


@pytest.mark.unit
class TestDepartmentsApiRepository:
    def test_list_departments_filters_by_active_and_orders(self, db_session):
        db_session.add_all(
            [
                Department(
                    key="lab",
                    name_ru="Лаборатория",
                    name_uz="Laboratoriya",
                    display_order=2,
                    active=True,
                ),
                Department(
                    key="derma",
                    name_ru="Дерматология",
                    name_uz="Dermatologiya",
                    display_order=1,
                    active=False,
                ),
            ]
        )
        db_session.commit()
        repository = DepartmentsApiRepository(db_session)

        all_rows = repository.list_departments(active_only=False)
        active_rows = repository.list_departments(active_only=True)

        assert [row.key for row in all_rows] == ["derma", "lab"]
        assert [row.key for row in active_rows] == ["lab"]

    def test_get_department_returns_none_for_missing(self, db_session):
        repository = DepartmentsApiRepository(db_session)

        row = repository.get_department(404_404)

        assert row is None

