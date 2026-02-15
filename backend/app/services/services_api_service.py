"""Service layer for services endpoints."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.crud import service as crud
from app.models.clinic import ServiceCategory
from app.models.service import Service
from app.repositories.services_api_repository import ServicesApiRepository
from app.services.service_mapping import normalize_service_code


class ServicesApiService:
    """Handles business rules for services and service categories."""

    def __init__(
        self,
        db: Session,
        repository: ServicesApiRepository | None = None,
    ):
        self.repository = repository or ServicesApiRepository(db)

    def list_service_categories(self, *, active: bool | None):
        return self.repository.list_service_categories(active=active)

    def create_service_category(self, *, category_data) -> ServiceCategory:
        existing = self.repository.get_service_category_by_code(category_data.code)
        if existing:
            raise ValueError(f"Категория с кодом '{category_data.code}' уже существует")

        payload = (
            category_data.model_dump()
            if hasattr(category_data, "model_dump")
            else category_data.dict()
        )
        category = ServiceCategory(**payload)
        self.repository.add(category)
        self.repository.commit()
        self.repository.refresh(category)
        return category

    def update_service_category(self, *, category_id: int, category_data) -> ServiceCategory:
        category = self.repository.get_service_category(category_id)
        if not category:
            raise LookupError("Категория не найдена")

        update_data = (
            category_data.model_dump(exclude_unset=True)
            if hasattr(category_data, "model_dump")
            else category_data.dict(exclude_unset=True)
        )
        if "code" in update_data and update_data["code"] != category.code:
            existing = self.repository.get_service_category_by_code(update_data["code"])
            if existing:
                raise ValueError(f"Категория с кодом '{update_data['code']}' уже существует")

        for field, value in update_data.items():
            setattr(category, field, value)

        self.repository.commit()
        self.repository.refresh(category)
        return category

    def delete_service_category(self, *, category_id: int) -> dict[str, Any]:
        category = self.repository.get_service_category(category_id)
        if not category:
            raise LookupError("Категория не найдена")

        services_count = self.repository.count_services_in_category(category_id)
        if services_count > 0:
            raise ValueError(
                f"Нельзя удалить категорию: к ней привязано {services_count} услуг"
            )

        self.repository.delete(category)
        self.repository.commit()
        return {"message": "Категория успешно удалена"}

    def list_services(
        self,
        *,
        q: str | None,
        active: bool | None,
        category_id: int | None,
        department: str | None,
        limit: int,
        offset: int,
    ):
        rows = crud.list_services(self.repository.db, q=q, active=active, limit=limit, offset=offset)
        if category_id is not None:
            rows = [row for row in rows if getattr(row, "category_id", None) == category_id]
        if department:
            rows = [row for row in rows if getattr(row, "department", None) == department]
        return rows

    def get_queue_groups_payload(self) -> dict[str, Any]:
        from app.services.service_mapping import QUEUE_GROUPS, get_queue_group_for_service

        groups = {}
        for key, data in QUEUE_GROUPS.items():
            groups[key] = {
                "display_name": data["display_name"],
                "display_name_uz": data.get("display_name_uz"),
                "service_codes": data.get("service_codes", []),
                "service_prefixes": data.get("service_prefixes", []),
                "exclude_codes": data.get("exclude_codes", []),
                "queue_tag": data["queue_tag"],
                "tab_key": data["tab_key"],
            }

        code_to_group = {}
        for key, data in QUEUE_GROUPS.items():
            for code in data.get("service_codes", []):
                code_to_group[code] = key

        try:
            services = self.repository.list_active_services()
            for service in services:
                if service.service_code:
                    group = get_queue_group_for_service(service.service_code)
                    if group:
                        code_to_group[service.service_code] = group
        except Exception:
            pass

        tab_to_group = {data["tab_key"]: key for key, data in QUEUE_GROUPS.items()}
        return {
            "groups": groups,
            "code_to_group": code_to_group,
            "tab_to_group": tab_to_group,
        }

    def get_service(self, *, service_id: int):
        return self.repository.get_service(service_id)

    def create_service(self, *, service_data):
        if service_data.code:
            existing = self.repository.get_service_by_code(service_data.code)
            if existing:
                raise ValueError(f"Услуга с кодом '{service_data.code}' уже существует")

        if service_data.category_id:
            category = self.repository.get_service_category(service_data.category_id)
            if not category:
                raise ValueError("Указанная категория не найдена")

        payload = (
            service_data.model_dump()
            if hasattr(service_data, "model_dump")
            else service_data.dict()
        )
        if payload.get("code"):
            payload["code"] = normalize_service_code(payload["code"])
        if payload.get("service_code"):
            payload["service_code"] = normalize_service_code(payload["service_code"])
        if payload.get("category_code"):
            payload["category_code"] = normalize_service_code(payload["category_code"])

        service = Service(**payload)
        self.repository.add(service)
        self.repository.commit()
        self.repository.refresh(service)
        return service

    def update_service(self, *, service_id: int, service_data):
        service = self.repository.get_service(service_id)
        if not service:
            raise LookupError("Услуга не найдена")

        update_data = (
            service_data.model_dump(exclude_unset=True)
            if hasattr(service_data, "model_dump")
            else service_data.dict(exclude_unset=True)
        )

        if "code" in update_data and update_data["code"] != service.code:
            existing = self.repository.get_service_by_code(update_data["code"])
            if existing:
                raise ValueError(f"Услуга с кодом '{update_data['code']}' уже существует")

        if update_data.get("category_id"):
            category = self.repository.get_service_category(update_data["category_id"])
            if not category:
                raise ValueError("Указанная категория не найдена")

        if "code" in update_data and update_data["code"] is not None:
            update_data["code"] = normalize_service_code(update_data["code"])
        if "service_code" in update_data and update_data["service_code"] is not None:
            update_data["service_code"] = normalize_service_code(update_data["service_code"])
        if "category_code" in update_data and update_data["category_code"] is not None:
            update_data["category_code"] = normalize_service_code(update_data["category_code"])

        for field, value in update_data.items():
            setattr(service, field, value)

        self.repository.commit()
        self.repository.refresh(service)
        return service

    def delete_service(self, *, service_id: int) -> dict[str, str]:
        service = self.repository.get_service(service_id)
        if not service:
            raise LookupError("Услуга не найдена")
        self.repository.delete(service)
        self.repository.commit()
        return {"message": "Услуга успешно удалена"}

    def list_doctors_temp(self):
        return self.repository.list_active_doctors()

    def resolve_service(self, *, service_id: int | None, code: str | None):
        from app.services.service_mapping import resolve_service

        return resolve_service(service_id=service_id, code=code, db=self.repository.db)

    def get_service_code_mappings_payload(self) -> dict[str, Any]:
        from app.services.service_mapping import SPECIALTY_ALIASES

        specialty_to_code = {
            "cardiology": "K01",
            "cardio": "K01",
            "dermatology": "D01",
            "derma": "D01",
            "stomatology": "S01",
            "dental": "S01",
            "laboratory": "L01",
            "lab": "L01",
            "echokg": "K10",
            "procedures": "P01",
            "cosmetology": "C01",
        }

        code_to_name = {
            "K01": "Консультация кардиолога",
            "K10": "ЭхоКГ",
            "D01": "Консультация дерматолога",
            "S01": "Консультация стоматолога",
            "L01": "Лабораторные анализы",
            "P01": "Процедуры",
            "C01": "Косметология",
        }

        category_mapping = {
            "cardiology": "K",
            "dermatology": "D",
            "laboratory": "L",
            "stomatology": "S",
            "cosmetology": "C",
            "procedures": "P",
        }

        try:
            services = self.repository.list_active_services()
            for service in services:
                if service.service_code and service.name:
                    code_to_name[service.service_code] = service.name
                if service.queue_tag and service.service_code:
                    specialty_to_code[service.queue_tag] = service.service_code
        except Exception:
            pass

        return {
            "specialty_to_code": specialty_to_code,
            "code_to_name": code_to_name,
            "category_mapping": category_mapping,
            "specialty_aliases": SPECIALTY_ALIASES,
        }
