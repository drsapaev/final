"""Service layer for services endpoints."""

from __future__ import annotations

import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.clinic import ServiceCategory
from app.models.service import Service
from app.repositories.services_api_repository import ServicesApiRepository
from app.services.service_mapping import (
    get_allowed_service_code_prefixes,
    normalize_service_code,
    resolve_queue_group_key,
)


class ServicesApiService:
    """Handles business rules for services and service categories."""

    def __init__(
        self,
        db: Session,
        repository: ServicesApiRepository | None = None,
    ):
        self.repository = repository or ServicesApiRepository(db)

    @staticmethod
    def _normalize_category_code_value(value: Any) -> str:
        return normalize_service_code(str(value)).upper()

    @staticmethod
    def _normalize_service_code_payload(payload: dict[str, Any]) -> str | None:
        code = payload.get("code")
        service_code = payload.get("service_code")
        normalized_code = normalize_service_code(str(code)) if code else None
        normalized_service_code = (
            normalize_service_code(str(service_code)) if service_code else None
        )

        canonical_code = normalized_service_code or normalized_code
        if (
            normalized_code
            and normalized_service_code
            and normalized_code != normalized_service_code
        ):
            raise HTTPException(
                status_code=422,
                detail="code and service_code must match after normalization",
            )

        if canonical_code:
            payload["code"] = canonical_code
            payload["service_code"] = canonical_code

        return canonical_code

    @staticmethod
    def _validate_service_code_prefix_alignment(
        *,
        service_code: str | None,
        queue_tag: str | None,
        department_key: str | None,
        category_specialty: str | None,
        category_code: str | None,
    ) -> None:
        if not service_code:
            return

        normalized_code = normalize_service_code(str(service_code))
        if not re.match(r"^[A-Z]\d{1,2}$", normalized_code):
            return

        expected_group = resolve_queue_group_key(
            queue_tag=queue_tag,
            department_key=department_key,
        )
        allowed_prefixes = get_allowed_service_code_prefixes(
            queue_tag=queue_tag,
            department_key=department_key,
            category_specialty=category_specialty,
            category_code=category_code,
        )
        if not expected_group or not allowed_prefixes:
            return

        prefix = normalized_code[0]
        if prefix not in allowed_prefixes:
            allowed = ", ".join(sorted(allowed_prefixes))
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Код услуги {normalized_code} не соответствует выбранной "
                    f"категории. Допустимые префиксы: {allowed}"
                ),
            )


    @staticmethod
    def _should_validate_service_code_alignment(
        change_set: dict[str, Any],
        existing_service: Service | None = None,
    ) -> bool:
        routing_fields = {
            "code",
            "service_code",
            "category_id",
            "queue_tag",
            "department_key",
            "category_code",
        }
        if existing_service is None:
            return True
        return bool(routing_fields.intersection(change_set.keys()))

    @staticmethod
    def _service_snapshot(service: Service) -> Service:
        return Service(
            id=service.id,
            code=service.code,
            service_code=service.service_code,
            name=service.name,
            category_id=service.category_id,
            category_code=service.category_code,
            price=service.price,
            currency=service.currency,
            duration_minutes=service.duration_minutes,
            doctor_id=service.doctor_id,
            department_key=service.department_key,
            queue_tag=service.queue_tag,
            requires_doctor=service.requires_doctor,
            is_consultation=service.is_consultation,
            allow_doctor_price_override=service.allow_doctor_price_override,
            active=service.active,
        )

    @staticmethod
    def _service_validation_payload(service: Service) -> dict[str, Any]:
        return {
            "code": service.code,
            "service_code": service.service_code,
            "category_id": service.category_id,
            "category_code": service.category_code,
            "queue_tag": service.queue_tag,
            "department_key": service.department_key,
        }

    def _log_service_creation(self, service: Service) -> None:
        self.repository.log_service_creation(service=service)

    def _log_service_update(
        self,
        *,
        service_id: int,
        old_service: Service,
        new_service: Service,
        comment: str | None = None,
    ) -> None:
        self.repository.log_service_update(
            service_id=service_id,
            old_service=old_service,
            new_service=new_service,
            comment=comment,
        )
    def list_service_categories(self, *, active: bool | None):
        return self.repository.list_service_categories(active=active)

    def create_service_category(self, *, category_data) -> ServiceCategory:
        existing = self.repository.get_service_category_by_code(category_data.code)
        if existing:
            raise ValueError(f"РљР°С‚РµРіРѕСЂРёСЏ СЃ РєРѕРґРѕРј '{category_data.code}' СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚")

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
            raise LookupError("РљР°С‚РµРіРѕСЂРёСЏ РЅРµ РЅР°Р№РґРµРЅР°")

        update_data = (
            category_data.model_dump(exclude_unset=True)
            if hasattr(category_data, "model_dump")
            else category_data.dict(exclude_unset=True)
        )
        if "code" in update_data and update_data["code"] != category.code:
            existing = self.repository.get_service_category_by_code(update_data["code"])
            if existing:
                raise ValueError(f"РљР°С‚РµРіРѕСЂРёСЏ СЃ РєРѕРґРѕРј '{update_data['code']}' СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚")

        for field, value in update_data.items():
            setattr(category, field, value)

        self.repository.commit()
        self.repository.refresh(category)
        return category

    def delete_service_category(self, *, category_id: int) -> dict[str, Any]:
        category = self.repository.get_service_category(category_id)
        if not category:
            raise LookupError("РљР°С‚РµРіРѕСЂРёСЏ РЅРµ РЅР°Р№РґРµРЅР°")

        services_count = self.repository.count_services_in_category(category_id)
        if services_count > 0:
            raise ValueError(
                f"РќРµР»СЊР·СЏ СѓРґР°Р»РёС‚СЊ РєР°С‚РµРіРѕСЂРёСЋ: Рє РЅРµР№ РїСЂРёРІСЏР·Р°РЅРѕ {services_count} СѓСЃР»СѓРі"
            )

        self.repository.delete(category)
        self.repository.commit()
        return {"message": "РљР°С‚РµРіРѕСЂРёСЏ СѓСЃРїРµС€РЅРѕ СѓРґР°Р»РµРЅР°"}

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
        rows = self.repository.list_services(q=q, active=active, limit=limit, offset=offset)
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
        payload = (
            service_data.model_dump()
            if hasattr(service_data, "model_dump")
            else service_data.dict()
        )

        canonical_code = self._normalize_service_code_payload(payload)
        if canonical_code:
            existing = self.repository.get_service_code_conflict(code=canonical_code)
            if existing:
                raise ValueError(f"РЈСЃР»СѓРіР° СЃ РєРѕРґРѕРј '{canonical_code}' СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚")

        category_specialty = None
        if payload.get("category_id"):
            category = self.repository.get_service_category(payload["category_id"])
            if not category:
                raise ValueError("РЈРєР°Р·Р°РЅРЅР°СЏ РєР°С‚РµРіРѕСЂРёСЏ РЅРµ РЅР°Р№РґРµРЅР°")
            category_specialty = category.specialty

        if payload.get("category_code"):
            payload["category_code"] = self._normalize_category_code_value(
                payload["category_code"]
            )

        self._validate_service_code_prefix_alignment(
            service_code=canonical_code,
            queue_tag=payload.get("queue_tag"),
            department_key=payload.get("department_key"),
            category_specialty=category_specialty,
            category_code=payload.get("category_code"),
        )

        service = Service(**payload)
        self.repository.add(service)
        self.repository.commit()
        self.repository.refresh(service)
        self._log_service_creation(service)
        return service

    def update_service(self, *, service_id: int, service_data):
        service = self.repository.get_service(service_id)
        if not service:
            raise LookupError("Service not found")
        old_service = self._service_snapshot(service)

        update_data = (
            service_data.model_dump(exclude_unset=True)
            if hasattr(service_data, "model_dump")
            else service_data.dict(exclude_unset=True)
        )

        if self._should_validate_service_code_alignment(update_data, service):
            validation_payload = self._service_validation_payload(service)
            validation_payload.update(update_data)
            canonical_code = self._normalize_service_code_payload(validation_payload)
            if canonical_code:
                existing = self.repository.get_service_code_conflict(
                    code=canonical_code,
                    exclude_service_id=service.id,
                )
                if existing:
                    raise ValueError(
                        f"Service with code {canonical_code!r} already exists"
                    )

            category_specialty = None
            category_id = validation_payload.get("category_id")
            if category_id:
                category = self.repository.get_service_category(category_id)
                if not category:
                    raise ValueError("Selected category not found")
                category_specialty = category.specialty

            if validation_payload.get("category_code"):
                validation_payload["category_code"] = self._normalize_category_code_value(
                    validation_payload["category_code"]
                )

            self._validate_service_code_prefix_alignment(
                service_code=canonical_code,
                queue_tag=validation_payload.get("queue_tag"),
                department_key=validation_payload.get("department_key"),
                category_specialty=category_specialty,
                category_code=validation_payload.get("category_code"),
            )

            for field in (
                "code",
                "service_code",
                "category_code",
                "queue_tag",
                "department_key",
                "category_id",
            ):
                if field in update_data:
                    update_data[field] = validation_payload.get(field)
        elif update_data.get("category_id"):
            category = self.repository.get_service_category(update_data["category_id"])
            if not category:
                raise ValueError("Selected category not found")

        for field, value in update_data.items():
            setattr(service, field, value)

        self.repository.commit()
        self.repository.refresh(service)
        self._log_service_update(
            service_id=service.id,
            old_service=old_service,
            new_service=service,
        )
        return service

    def delete_service(self, *, service_id: int) -> dict[str, Any]:
        service = self.repository.get_service(service_id)
        if not service:
            raise LookupError("Service not found")

        old_service = self._service_snapshot(service)
        visit_services_count = self.repository.count_visit_services_for_service(
            service_id,
        )
        service.active = False
        self.repository.add(service)
        self.repository.commit()
        self.repository.refresh(service)
        self._log_service_update(
            service_id=service.id,
            old_service=old_service,
            new_service=service,
            comment=(
                "Soft delete via service catalog API; "
                f"visit_service_links={visit_services_count}"
            ),
        )
        return {
            "message": "Service deactivated successfully",
            "service_id": service.id,
            "active": service.active,
            "soft_deleted": True,
            "visit_usage_count": visit_services_count,
            "visit_service_links": visit_services_count,
        }

    def list_doctors_temp(self):
        return self.repository.list_active_doctors()

    def resolve_service(self, *, service_id: int | None, code: str | None):
        return self.repository.resolve_service(service_id=service_id, code=code)

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
            "K01": "РљРѕРЅСЃСѓР»СЊС‚Р°С†РёСЏ РєР°СЂРґРёРѕР»РѕРіР°",
            "K10": "Р­С…РѕРљР“",
            "D01": "РљРѕРЅСЃСѓР»СЊС‚Р°С†РёСЏ РґРµСЂРјР°С‚РѕР»РѕРіР°",
            "S01": "РљРѕРЅСЃСѓР»СЊС‚Р°С†РёСЏ СЃС‚РѕРјР°С‚РѕР»РѕРіР°",
            "L01": "Р›Р°Р±РѕСЂР°С‚РѕСЂРЅС‹Рµ Р°РЅР°Р»РёР·С‹",
            "P01": "РџСЂРѕС†РµРґСѓСЂС‹",
            "C01": "РљРѕСЃРјРµС‚РѕР»РѕРіРёСЏ",
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
