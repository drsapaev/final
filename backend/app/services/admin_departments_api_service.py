"""
CRUD endpoints для управления отделениями в админ-панели
"""

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from pydantic import ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.appointment import Appointment
from app.models.clinic import ClinicSettings, Doctor, ServiceCategory
from app.models.department import (
    Department,
    DepartmentQueueSettings,
    DepartmentRegistrationSettings,
    DepartmentService,
)
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit
from app.repositories.admin_departments_api_repository import (
    AdminDepartmentsApiRepository,
)
from app.schemas.department import (
    DepartmentQueueSettingsUpdate,
    DepartmentRegistrationSettingsUpdate,
    DepartmentServiceCreate,
)
from app.services.service_mapping import normalize_service_code

router = APIRouter()


def _repo(db: Session) -> AdminDepartmentsApiRepository:
    return AdminDepartmentsApiRepository(db)


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
    setting = _repo(db).query(ClinicSettings).filter(ClinicSettings.key == key).first()
    if setting:
        return False

    _repo(db).add(
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
    }

    # Queue settings
    queue_settings = (
        _repo(db).query(DepartmentQueueSettings)
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
        _repo(db).add(queue_settings)
        integration_result["queue_settings_created"] = True

    # Registration settings
    registration_settings = (
        _repo(db).query(DepartmentRegistrationSettings)
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
        _repo(db).add(registration_settings)
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
        _repo(db).query(ServiceCategory).filter(ServiceCategory.code == category_code).first()
    )
    if not service_category:
        service_category = ServiceCategory(
            code=category_code,
            name_ru=department.name_ru,
            name_uz=department.name_uz or department.name_ru,
            specialty=department.key,
            active=True,
        )
        _repo(db).add(service_category)
        _repo(db).flush()
        integration_result["service_category_created"] = True

    # Update existing services to link department_id if key matches
    _repo(db).query(Service).filter(
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
        _repo(db).query(Service)
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
            _repo(db).query(Service).filter(Service.service_code == unique_code).first()
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
        _repo(db).add(default_service)
        _repo(db).flush()

        _repo(db).add(
            DepartmentService(
                department_id=department.id,
                service_id=default_service.id,
                is_default=True,
                display_order=1,
            )
        )
        integration_result["default_service_created"] = True
        integration_result["default_service_id"] = default_service.id

    return integration_result


def _collect_department_overview(db: Session) -> dict[str, Any]:
    """Формирует реальные показатели по отделениям."""
    today = date.today()
    departments = _repo(db).query(Department).order_by(Department.display_order).all()
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
            _repo(db).query(func.count(Appointment.id))
            .filter(
                Appointment.department_id == department.id,
                Appointment.appointment_date == today,
            )
            .scalar()
            or 0
        )
        stats["visits_today"] = (
            _repo(db).query(func.count(Visit.id))
            .filter(
                Visit.department_id == department.id,
                func.date(Visit.visit_date) == today,
            )
            .scalar()
            or 0
        )
        stats["services"] = (
            _repo(db).query(func.count(Service.id))
            .filter(
                (Service.department_id == department.id)
                | (Service.department_key == department.key)
            )
            .scalar()
            or 0
        )
        stats["doctors"] = (
            _repo(db).query(func.count(Doctor.id))
            .filter(Doctor.department_id == department.id)
            .scalar()
            or 0
        )
        stats["queue_entries_today"] = (
            _repo(db).query(func.count(OnlineQueueEntry.id))
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
            "has_service_category": _repo(db).query(ServiceCategory)
            .filter(ServiceCategory.specialty == department.key)
            .first()
            is not None,
            "has_services": stats["services"] > 0,
        }

        if department.queue_settings:
            integrations["queue_prefix"] = department.queue_settings.queue_prefix
            integrations["max_daily_queue"] = department.queue_settings.max_daily_queue

        start_setting = (
            _repo(db).query(ClinicSettings)
            .filter(ClinicSettings.key == f"start_number_{department.key}")
            .first()
        )
        if start_setting is not None:
            integrations["start_number"] = start_setting.value

        max_setting = (
            _repo(db).query(ClinicSettings)
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


@router.get("", response_model=dict)
def list_departments(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Получить список всех отделений

    Доступно только для администраторов
    """
    query = _repo(db).query(Department)

    if active_only:
        query = query.filter(Department.active == True)

    departments = query.order_by(Department.display_order).all()

    data = []
    for dept in departments:
        dept_dict = DepartmentResponse.from_orm(dept).dict()
        # Добавляем префикс очереди
        if dept.queue_settings:
            dept_dict["queue_prefix"] = dept.queue_settings.queue_prefix
        data.append(dept_dict)

    return {"success": True, "data": data, "count": len(departments)}


@router.get("/overview", response_model=dict)
def get_departments_overview(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """
    Получить реальные показатели по отделениям (очередь, услуги, визиты)
    """
    overview = _collect_department_overview(db)
    return {
        "success": True,
        "data": overview,
    }


@router.get("/{department_id}", response_model=dict)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Получить отделение по ID

    Доступно только для администраторов
    """
    department = _repo(db).query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found",
        )

    return {"success": True, "data": DepartmentResponse.from_orm(department).dict()}


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_department(
    department_data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Создать новое отделение

    Доступно только для администраторов
    """
    # Проверяем уникальность ключа
    existing = (
        _repo(db).query(Department).filter(Department.key == department_data.key).first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department with key '{department_data.key}' already exists",
        )

    payload = department_data.dict(exclude={"integration"})

    # Создаем новое отделение
    department = Department(**payload)
    _repo(db).add(department)
    _repo(db).flush()

    integration_result = _ensure_department_integrations(
        db, department, department_data.integration
    )

    _repo(db).commit()
    _repo(db).refresh(department)

    # Создаем дефолтные настройки очереди
    queue_settings = DepartmentQueueSettings(
        department_id=department.id,
        queue_prefix=department.key.upper()[0] if department.key else "Q",
    )
    _repo(db).add(queue_settings)

    # Создаем дефолтные настройки регистрации
    reg_settings = DepartmentRegistrationSettings(department_id=department.id)
    _repo(db).add(reg_settings)

    _repo(db).commit()

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
        "integration": integration_result,
        "message": "Department created successfully",
    }


@router.put("/{department_id}", response_model=dict)
def update_department(
    department_id: int,
    department_data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Обновить отделение

    Доступно только для администраторов
    """
    department = _repo(db).query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found",
        )

    # Обновляем только переданные поля
    update_data = department_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(department, field, value)

    _repo(db).commit()
    _repo(db).refresh(department)

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
        "message": "Department updated successfully",
    }


@router.post("/{department_id}/initialize", response_model=dict)
def initialize_department(
    department_id: int,
    integration: DepartmentIntegrationOptions | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Повторно синхронизировать отделение с очередями/услугами

    Позволяет принудительно создать настройки очередей, регистрацию и дефолтные услуги.
    """
    department = _repo(db).query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found",
        )

    integration_result = _ensure_department_integrations(db, department, integration)
    _repo(db).commit()
    _repo(db).refresh(department)

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
        "integration": integration_result,
        "message": "Department integrations initialized",
    }


@router.delete("/{department_id}", response_model=dict)
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Удалить отделение

    Доступно только для администраторов
    """
    department = _repo(db).query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found",
        )

    _repo(db).delete(department)
    _repo(db).commit()

    return {
        "success": True,
        "message": f"Department '{department.name_ru}' deleted successfully",
    }


@router.post("/{department_id}/toggle", response_model=dict)
def toggle_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Переключить активность отделения

    Доступно только для администраторов
    """
    department = _repo(db).query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found",
        )

    # Переключаем active
    department.active = not department.active
    _repo(db).commit()
    _repo(db).refresh(department)

    status_text = "активировано" if department.active else "деактивировано"

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
        "message": f"Department '{department.name_ru}' {status_text}",
    }


# ============================================================
# УПРАВЛЕНИЕ УСЛУГАМИ ОТДЕЛЕНИЯ
# ============================================================


@router.get("/{department_id}/services", response_model=dict)
def get_department_services(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить услуги отделения"""
    department = _repo(db).query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    services = (
        _repo(db).query(DepartmentService)
        .filter(DepartmentService.department_id == department_id)
        .order_by(DepartmentService.display_order)
        .all()
    )

    return {
        "success": True,
        "data": [
            {
                "id": ds.id,
                "service": {
                    "id": ds.service.id,
                    "name": ds.service.name,
                    "code": ds.service.code,
                    "base_price": float(ds.service.price) if ds.service.price else None,
                },
                "is_default": ds.is_default,
                "display_order": ds.display_order,
                "price_override": (
                    float(ds.price_override) if ds.price_override else None
                ),
            }
            for ds in services
        ],
        "count": len(services),
    }


@router.post("/{department_id}/services/{service_id}", response_model=dict)
def add_service_to_department(
    department_id: int,
    service_id: int,
    data: DepartmentServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Добавить услугу в отделение"""
    # Проверки
    department = _repo(db).query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    service = _repo(db).query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Проверка дубликатов
    existing = (
        _repo(db).query(DepartmentService)
        .filter(
            DepartmentService.department_id == department_id,
            DepartmentService.service_id == service_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="Service already added to department"
        )

    # Создание привязки
    dept_service = DepartmentService(
        department_id=department_id, service_id=service_id, **data.dict()
    )
    _repo(db).add(dept_service)
    _repo(db).commit()
    _repo(db).refresh(dept_service)

    return {"success": True, "message": f"Service '{service.name}' added to department"}


@router.delete("/{department_id}/services/{service_id}", response_model=dict)
def remove_service_from_department(
    department_id: int,
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Удалить услугу из отделения"""
    dept_service = (
        _repo(db).query(DepartmentService)
        .filter(
            DepartmentService.department_id == department_id,
            DepartmentService.service_id == service_id,
        )
        .first()
    )

    if not dept_service:
        raise HTTPException(status_code=404, detail="Service not found in department")

    _repo(db).delete(dept_service)
    _repo(db).commit()

    return {"success": True, "message": "Service removed from department"}


# ============================================================
# УПРАВЛЕНИЕ НАСТРОЙКАМИ ОЧЕРЕДИ
# ============================================================


@router.get("/{department_id}/settings/queue", response_model=dict)
def get_queue_settings(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить настройки очереди отделения"""
    settings = (
        _repo(db).query(DepartmentQueueSettings)
        .filter(DepartmentQueueSettings.department_id == department_id)
        .first()
    )

    if not settings:
        raise HTTPException(status_code=404, detail="Queue settings not found")

    return {
        "success": True,
        "data": {
            "enabled": settings.enabled,
            "queue_type": settings.queue_type,
            "queue_prefix": settings.queue_prefix,
            "max_daily_queue": settings.max_daily_queue,
            "max_concurrent_queue": settings.max_concurrent_queue,
            "avg_wait_time": settings.avg_wait_time,
            "show_on_display": settings.show_on_display,
            "auto_close_time": settings.auto_close_time,
        },
    }


@router.put("/{department_id}/settings/queue", response_model=dict)
def update_queue_settings(
    department_id: int,
    data: DepartmentQueueSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Обновить настройки очереди отделения"""
    settings = (
        _repo(db).query(DepartmentQueueSettings)
        .filter(DepartmentQueueSettings.department_id == department_id)
        .first()
    )

    if not settings:
        # Если настроек нет, создаем их
        settings = DepartmentQueueSettings(department_id=department_id)
        _repo(db).add(settings)
        # Не делаем commit здесь, он будет ниже

    # Обновление полей
    for field, value in data.dict(exclude_unset=True).items():
        setattr(settings, field, value)

    _repo(db).commit()
    _repo(db).refresh(settings)

    return {"success": True, "message": "Queue settings updated"}


# ============================================================
# УПРАВЛЕНИЕ НАСТРОЙКАМИ РЕГИСТРАЦИИ
# ============================================================


@router.get("/{department_id}/settings/registration", response_model=dict)
def get_registration_settings(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить настройки регистрации отделения"""
    settings = (
        _repo(db).query(DepartmentRegistrationSettings)
        .filter(DepartmentRegistrationSettings.department_id == department_id)
        .first()
    )

    if not settings:
        raise HTTPException(status_code=404, detail="Registration settings not found")

    return {
        "success": True,
        "data": {
            "online_booking_enabled": settings.online_booking_enabled,
            "requires_confirmation": settings.requires_confirmation,
            "min_booking_hours": settings.min_booking_hours,
            "max_booking_days": settings.max_booking_days,
            "auto_assign_doctor": settings.auto_assign_doctor,
            "allow_walkin": settings.allow_walkin,
        },
    }


@router.put("/{department_id}/settings/registration", response_model=dict)
def update_registration_settings(
    department_id: int,
    data: DepartmentRegistrationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Обновить настройки регистрации отделения"""
    settings = (
        _repo(db).query(DepartmentRegistrationSettings)
        .filter(DepartmentRegistrationSettings.department_id == department_id)
        .first()
    )

    if not settings:
        # Если настроек нет, создаем их
        settings = DepartmentRegistrationSettings(department_id=department_id)
        _repo(db).add(settings)

    # Обновление полей
    for field, value in data.dict(exclude_unset=True).items():
        setattr(settings, field, value)

    _repo(db).commit()
    _repo(db).refresh(settings)

    return {"success": True, "message": "Registration settings updated"}


# ============================================================
# УПРАВЛЕНИЕ ВРАЧАМИ ОТДЕЛЕНИЯ
# ============================================================


@router.get("/{department_id}/doctors", response_model=dict)
def get_department_doctors(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить список врачей отделения"""
    department = _repo(db).query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    doctors = _repo(db).query(Doctor).filter(Doctor.department_id == department_id).all()

    return {
        "success": True,
        "data": [
            {
                "id": doctor.id,
                "user_id": doctor.user_id,
                "name": doctor.user.full_name if doctor.user else None,
                "specialty": doctor.specialty,
            }
            for doctor in doctors
        ],
        "count": len(doctors),
    }


@router.post("/{department_id}/doctors/{doctor_id}", response_model=dict)
def assign_doctor_to_department(
    department_id: int,
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Назначить врача в отделение"""
    department = _repo(db).query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    doctor = _repo(db).query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # Назначение
    doctor.department_id = department_id
    _repo(db).commit()
    _repo(db).refresh(doctor)

    return {
        "success": True,
        "message": f"Doctor assigned to department '{department.name_ru}'",
    }


@router.delete("/{department_id}/doctors/{doctor_id}", response_model=dict)
def remove_doctor_from_department(
    department_id: int,
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Убрать врача из отделения"""
    doctor = (
        _repo(db).query(Doctor)
        .filter(Doctor.id == doctor_id, Doctor.department_id == department_id)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404, detail="Doctor not found in this department"
        )

    # Убираем привязку
    doctor.department_id = None
    _repo(db).commit()

    return {"success": True, "message": "Doctor removed from department"}
