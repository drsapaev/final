"""Repository helpers for departments API endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.department import Department


class DepartmentsApiRepository:
    """Encapsulates Department ORM operations for endpoint services."""

    def __init__(self, db: Session):
        self.db = db

    def list_departments(self, *, active_only: bool) -> list[Department]:
        query = self.db.query(Department)
        if active_only:
            query = query.filter(Department.active.is_(True))
        return query.order_by(Department.display_order).all()

    def get_department(self, department_id: int) -> Department | None:
        return self.db.query(Department).filter(Department.id == department_id).first()
