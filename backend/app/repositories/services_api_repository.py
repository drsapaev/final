"""Repository helpers for services endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.clinic import Doctor, ServiceCategory
from app.models.service import Service
from app.services.service_mapping import normalize_service_code
from app.crud import service as crud


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

    def list_services(self, *, q: str | None, active: bool | None, limit: int, offset: int):
        return crud.list_services(self.db, q=q, active=active, limit=limit, offset=offset)

    def resolve_service(self, *, service_id: int | None, code: str | None):
        service = None
        normalized_code = normalize_service_code(code) if code else None

        if service_id is not None:
            service = self.get_service(service_id)

        if service is None and code:
            service = (
                self.db.query(Service)
                .filter(
                    (Service.service_code == code)
                    | (Service.service_code == normalized_code)
                    | (Service.code == code)
                    | (Service.code == normalized_code)
                )
                .first()
            )

        if service is None:
            return {
                "service_id": service_id,
                "service_code": code,
                "normalized_code": normalized_code,
                "category": None,
                "subcategory": None,
                "departments": [],
                "ui_type": None,
            }

        return {
            "service_id": service.id,
            "service_code": service.service_code or service.code,
            "normalized_code": normalize_service_code(service.service_code or service.code or ""),
            "category": service.category_code or service.category,
            "subcategory": service.subcategory,
            "departments": [service.department] if getattr(service, "department", None) else [],
            "ui_type": None,
        }

    def add(self, obj) -> None:
        self.db.add(obj)

    def delete(self, obj) -> None:
        self.db.delete(obj)

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)
