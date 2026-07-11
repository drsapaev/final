"""
CRUD endpoints для управления отделениями в админ-панели
"""

import logging  # noqa: F401
from datetime import date  # noqa: F401
from decimal import Decimal  # noqa: F401
from typing import Any  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Query, status  # noqa: F401
from pydantic import BaseModel, ConfigDict, Field  # noqa: F401
from sqlalchemy import func  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.api.deps import get_db, require_roles  # noqa: F401
from app.models.appointment import Appointment  # noqa: F401
from app.models.clinic import ClinicSettings, Doctor, ServiceCategory  # noqa: F401
from app.models.department import (  # noqa: F401
    Department,
    DepartmentQueueSettings,
    DepartmentRegistrationSettings,
    DepartmentService,
)
from app.models.online_queue import DailyQueue, OnlineQueueEntry  # noqa: F401
from app.models.queue_profile import QueueProfile  # noqa: F401
from app.models.service import Service  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.visit import Visit  # noqa: F401
from app.schemas.department import (  # noqa: F401
    DepartmentQueueSettingsUpdate,
    DepartmentRegistrationSettingsUpdate,
    DepartmentServiceCreate,
)
from app.services.service_mapping import (  # noqa: F401
    get_service_code,
    normalize_service_code,
)

router = APIRouter()
logger = logging.getLogger(__name__)

ADMIN_DEPARTMENTS_PUBLIC_ERROR = "Internal server error"


# Pydantic schemas
class DepartmentIntegrationOptions(BaseModel):
    """Настройки автоматической интеграции отделения в очередь/услуги."""

    queue_prefix: str | None = Field(None, max_length=10)
    queue_type: str | None = Field(None, pattern="^(live|online|mixed)$")
    auto_close_time: str | None = Field(None, max_length=5)
    start_number: int | None = Field(None, ge=1, le=999)
    max_daily_queue: int | None = Field(None, ge=1, le=9999)
    service_name: str | None = Field(None, max_length=256)
    service_code: str | None = Field(None, max_length=32)
    service_price: Decimal | None = None
    service_currency: str | None = Field("UZS", max_length=8)
    service_category_code: str | None = Field(None, max_length=2)


class DepartmentCreate(BaseModel):
    """Схема для создания отделения"""

    key: str
    name_ru: str
    name_uz: str | None = None
    icon: str | None = "folder"
    color: str | None = None
    gradient: str | None = None
    display_order: int | None = 999
    active: bool | None = True
    description: str | None = None
    integration: DepartmentIntegrationOptions | None = None


class DepartmentUpdate(BaseModel):
    """Схема для обновления отделения"""

    name_ru: str | None = None
    name_uz: str | None = None
    icon: str | None = None
    color: str | None = None
    gradient: str | None = None
    display_order: int | None = None
    active: bool | None = None
    description: str | None = None


class DepartmentResponse(BaseModel):
    """Схема ответа отделения"""

    id: int
    key: str
    name_ru: str
    name_uz: str | None
    icon: str
    color: str | None
    gradient: str | None
    display_order: int
    active: bool
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class DepartmentResponseWithSettings(DepartmentResponse):
    """Схема ответа отделения с настройками"""

    queue_prefix: str | None = None


def _default_stats() -> dict[str, int]:
    return {
        "appointments_today": 0,
        "visits_today": 0,
        "queue_entries_today": 0,
        "services": 0,
        "doctors": 0,
    }


def _ensure_clinic_setting(
    db: Session, key: str, value: Any, description: str, category: str = "queue"
) -> bool:
    """Создать настройку клиники, если она отсутствует."""
    setting = db.query(ClinicSettings).filter(ClinicSettings.key == key).first()
    if setting:
        return False

    db.add(
        ClinicSettings(
            key=key,
            value=value,
            category=category,
            description=description,
        )
    )
    return True


def _ensure_department_integrations(
    db: Session,
    department: Department,
    options: DepartmentIntegrationOptions | None = None,
) -> dict[str, Any]:
    """Гарантирует, что отделение подключено к очередям, услугам и мастеру регистрации."""
    opts = options.dict(exclude_unset=True) if options else {}
    integration_result: dict[str, Any] = {
        "queue_settings_created": False,
        "registration_settings_created": False,
        "clinic_settings_updated": [],
        "service_category_created": False,
        "default_service_created": False,
        "default_service_id": None,
        "queue_profile_created": False,
    }

    # Queue settings
    queue_settings = (
        db.query(DepartmentQueueSettings)
        .filter(DepartmentQueueSettings.department_id == department.id)
        .first()
    )
    if not queue_settings:
        prefix = (opts.get("queue_prefix") or department.key[:2] or "CL").upper()
        queue_settings = DepartmentQueueSettings(
            department_id=department.id,
            queue_prefix=prefix,
            queue_type=opts.get("queue_type") or "mixed",
            max_daily_queue=opts.get("max_daily_queue") or 50,
            avg_wait_time=20,
            auto_close_time=opts.get("auto_close_time") or "09:00",
        )
        db.add(queue_settings)
        integration_result["queue_settings_created"] = True

    # Registration settings
    registration_settings = (
        db.query(DepartmentRegistrationSettings)
        .filter(DepartmentRegistrationSettings.department_id == department.id)
        .first()
    )
    if not registration_settings:
        registration_settings = DepartmentRegistrationSettings(
            department_id=department.id,
            online_booking_enabled=True,
            requires_confirmation=False,
            min_booking_hours=2,
            max_booking_days=30,
            auto_assign_doctor=False,
            allow_walkin=True,
        )
        db.add(registration_settings)
        integration_result["registration_settings_created"] = True

    # Clinic queue settings (start numbers / limits)
    start_number_key = f"start_number_{department.key}"
    max_per_day_key = f"max_per_day_{department.key}"

    if _ensure_clinic_setting(
        db,
        start_number_key,
        opts.get("start_number") or 1,
        f"Стартовый номер очереди для {department.name_ru}",
    ):
        integration_result["clinic_settings_updated"].append(start_number_key)

    if _ensure_clinic_setting(
        db,
        max_per_day_key,
        opts.get("max_daily_queue") or 50,
        f"Максимум записей в день для {department.name_ru}",
    ):
        integration_result["clinic_settings_updated"].append(max_per_day_key)

    # Service category
    category_code = (
        opts.get("service_category_code") or department.key[:1] or "O"
    ).upper()
    service_category = (
        db.query(ServiceCategory).filter(ServiceCategory.code == category_code).first()
    )
    if not service_category:
        service_category = ServiceCategory(
            code=category_code,
            name_ru=department.name_ru,
            name_uz=department.name_uz or department.name_ru,
            specialty=department.key,
            active=True,
        )
        db.add(service_category)
        db.flush()
        integration_result["service_category_created"] = True

    # Update existing services to link department_id if key matches
    db.query(Service).filter(
        Service.department_key == department.key,
        Service.department_id.is_(None),
    ).update(
        {
            Service.department_id: department.id,
        },
        synchronize_session=False,
    )

    # Default service (used by wizard/queue mapping)
    existing_service = (
        db.query(Service)
        .filter(
            (Service.department_id == department.id)
            | (Service.department_key == department.key)
        )
        .first()
    )

    if not existing_service:
        service_name = opts.get("service_name") or f"Консультация {department.name_ru}"
        raw_service_code = opts.get("service_code") or f"{department.key}_consult"
        normalized_code = normalize_service_code(raw_service_code) or department.key

        # Гарантируем уникальность service_code
        suffix = 1
        unique_code = normalized_code.upper()
        while (
            db.query(Service).filter(Service.service_code == unique_code).first()
            is not None
        ):
            suffix += 1
            unique_code = f"{normalized_code.upper()}_{suffix}"

        default_service = Service(
            code=unique_code,
            service_code=unique_code,
            name=service_name,
            department_id=department.id,
            department_key=department.key,
            category_id=service_category.id if service_category else None,
            category_code=category_code[:1],
            price=opts.get("service_price"),
            currency=opts.get("service_currency") or "UZS",
            active=True,
            requires_doctor=False,
            is_consultation=True,
        )
        db.add(default_service)
        db.flush()

        db.add(
            DepartmentService(
                department_id=department.id,
                service_id=default_service.id,
                is_default=True,
                display_order=1,
            )
        )
        integration_result["default_service_created"] = True
        integration_result["default_service_id"] = default_service.id

    # PR-16: Auto-create a QueueProfile so the new department immediately
    # appears as a registrar tab. Without this, admin creates a department
    # but no tab appears — they must separately create a QueueProfile via
    # "Вкладки регистратуры" with the same key, which is non-obvious.
    existing_profile = (
        db.query(QueueProfile)
        .filter(QueueProfile.key == department.key)
        .first()
    )
    if not existing_profile:
        queue_profile = QueueProfile(
            key=department.key,
            title=department.name_ru or department.key,
            title_ru=department.name_ru or department.key,
            queue_tags=[department.key],
            department_key=department.key,
            display_order=department.display_order,
            is_active=department.active,
            show_on_qr_page=True,
            icon=department.icon or "Layers",
            color=department.color or "#3b82f6",
        )
        db.add(queue_profile)
        integration_result["queue_profile_created"] = True
    else:
        integration_result["queue_profile_created"] = False

    return integration_result


def _collect_department_overview(db: Session) -> dict[str, Any]:
    """Формирует реальные показатели по отделениям."""
    today = date.today()
    departments = db.query(Department).order_by(Department.display_order).all()
    overview_items: list[dict[str, Any]] = []

    totals = {
        "departments": len(departments),
        "active": 0,
        "appointments_today": 0,
        "visits_today": 0,
        "queue_entries_today": 0,
        "services": 0,
        "doctors": 0,
        "queue_enabled": 0,
    }

    for department in departments:
        stats = _default_stats()

        stats["appointments_today"] = (
            db.query(func.count(Appointment.id))
            .filter(
                Appointment.department_id == department.id,
                Appointment.appointment_date == today,
            )
            .scalar()
            or 0
        )
        stats["visits_today"] = (
            db.query(func.count(Visit.id))
            .filter(
                Visit.department_id == department.id,
                func.date(Visit.visit_date) == today,
            )
            .scalar()
            or 0
        )
        stats["services"] = (
            db.query(func.count(Service.id))
            .filter(
                (Service.department_id == department.id)
                | (Service.department_key == department.key)
            )
            .scalar()
            or 0
        )
        stats["doctors"] = (
            db.query(func.count(Doctor.id))
            .filter(Doctor.department_id == department.id)
            .scalar()
            or 0
        )
        stats["queue_entries_today"] = (
            db.query(func.count(OnlineQueueEntry.id))
            .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
            .join(Doctor, DailyQueue.specialist_id == Doctor.id)
            .filter(
                Doctor.department_id == department.id,
                DailyQueue.day == today,
                OnlineQueueEntry.status.in_(["waiting", "called"]),
            )
            .scalar()
            or 0
        )

        integrations = {
            "has_queue_settings": department.queue_settings is not None,
            "has_registration_settings": department.registration_settings is not None,
            "has_service_category": db.query(ServiceCategory)
            .filter(ServiceCategory.specialty == department.key)
            .first()
            is not None,
            "has_services": stats["services"] > 0,
        }

        if department.queue_settings:
            integrations["queue_prefix"] = department.queue_settings.queue_prefix
            integrations["max_daily_queue"] = department.queue_settings.max_daily_queue

        start_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == f"start_number_{department.key}")
            .first()
        )
        if start_setting is not None:
            integrations["start_number"] = start_setting.value

        max_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == f"max_per_day_{department.key}")
            .first()
        )
        if max_setting is not None:
            integrations["max_per_day"] = max_setting.value

        if integrations["has_queue_settings"]:
            totals["queue_enabled"] += 1

        overview_items.append(
            {
                "id": department.id,
                "key": department.key,
                "active": department.active,
                "stats": stats,
                "integrations": integrations,
            }
        )

        if department.active:
            totals["active"] += 1
        totals["appointments_today"] += stats["appointments_today"]
        totals["visits_today"] += stats["visits_today"]
        totals["queue_entries_today"] += stats["queue_entries_today"]
        totals["services"] += stats["services"]
        totals["doctors"] += stats["doctors"]

    return {"departments": overview_items, "totals": totals}


