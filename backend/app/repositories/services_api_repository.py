"""Repository helpers for services endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.clinic import Doctor, ServiceCategory
from app.models.service import Service


class ServicesApiRepository:
    """Encapsulates ORM operations for services API."""

    def __init__(self, db: Session):
        self.db = db

    def list_service_categories(self, *, active: bool | None):
        query = self.db.query(ServiceCategory)
        if active is not None:
            query = query.filter(ServiceCategory.active == active)
        return query.order_by(ServiceCategory.name_ru).all()

    def get_service_category_by_code(self, code: str):
        return self.db.query(ServiceCategory).filter(ServiceCategory.code == code).first()

    def get_service_category(self, category_id: int):
        return self.db.query(ServiceCategory).filter(ServiceCategory.id == category_id).first()

    def count_services_in_category(self, category_id: int) -> int:
        return self.db.query(Service).filter(Service.category_id == category_id).count()

    def get_service(self, service_id: int):
        return self.db.query(Service).filter(Service.id == service_id).first()

    def get_service_by_code(self, code: str):
        return self.db.query(Service).filter(Service.code == code).first()

    def list_active_services(self):
        return self.db.query(Service).filter(Service.active.is_(True)).all()

    def list_active_doctors(self):
        return self.db.query(Doctor).filter(Doctor.active.is_(True)).all()

    def add(self, obj) -> None:
        self.db.add(obj)

    def delete(self, obj) -> None:
        self.db.delete(obj)

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)
