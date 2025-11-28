"""
CRUD endpoints для управления отделениями в админ-панели
"""
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.department import (
    Department,
    DepartmentService,
    DepartmentQueueSettings,
    DepartmentRegistrationSettings,
)
from app.models.clinic import ClinicSettings, Doctor, ServiceCategory
from app.models.service import Service
from app.models.appointment import Appointment
from app.models.visit import Visit
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User
from app.schemas.department import (
    DepartmentServiceCreate,
    DepartmentQueueSettingsUpdate,
    DepartmentRegistrationSettingsUpdate,
)
from app.services.service_mapping import normalize_service_code

router = APIRouter()


# Pydantic schemas
class DepartmentIntegrationOptions(BaseModel):
    """Настройки автоматической интеграции отделения в очередь/услуги."""

    queue_prefix: Optional[str] = Field(None, max_length=10)
    queue_type: Optional[str] = Field(None, pattern="^(live|online|mixed)$")
    auto_close_time: Optional[str] = Field(None, max_length=5)
    start_number: Optional[int] = Field(None, ge=1, le=999)
    max_daily_queue: Optional[int] = Field(None, ge=1, le=9999)
    service_name: Optional[str] = Field(None, max_length=256)
    service_code: Optional[str] = Field(None, max_length=32)
    service_price: Optional[Decimal] = None
    service_currency: Optional[str] = Field("UZS", max_length=8)
    service_category_code: Optional[str] = Field(None, max_length=2)


class DepartmentCreate(BaseModel):
    """Схема для создания отделения"""
    key: str
    name_ru: str
    name_uz: Optional[str] = None
    icon: Optional[str] = "folder"
    color: Optional[str] = None
    gradient: Optional[str] = None
    display_order: Optional[int] = 999
    active: Optional[bool] = True
    description: Optional[str] = None
    integration: Optional[DepartmentIntegrationOptions] = None


class DepartmentUpdate(BaseModel):
    """Схема для обновления отделения"""
    name_ru: Optional[str] = None
    name_uz: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    gradient: Optional[str] = None
    display_order: Optional[int] = None
    active: Optional[bool] = None
    description: Optional[str] = None


class DepartmentResponse(BaseModel):
    """Схема ответа отделения"""
    id: int
    key: str
    name_ru: str
    name_uz: Optional[str]
    icon: str
    color: Optional[str]
    gradient: Optional[str]
    display_order: int
    active: bool
    description: Optional[str]

    class Config:
        from_attributes = True

class DepartmentResponseWithSettings(DepartmentResponse):
    """Схема ответа отделения с настройками"""
    queue_prefix: Optional[str] = None



def _default_stats() -> Dict[str, int]:
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
    options: Optional[DepartmentIntegrationOptions] = None,
) -> Dict[str, Any]:
    """Гарантирует, что отделение подключено к очередям, услугам и мастеру регистрации."""
    opts = options.dict(exclude_unset=True) if options else {}
    integration_result: Dict[str, Any] = {
        "queue_settings_created": False,
        "registration_settings_created": False,
        "clinic_settings_updated": [],
        "service_category_created": False,
        "default_service_created": False,
        "default_service_id": None,
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
    category_code = (opts.get("service_category_code") or department.key[:1] or "O").upper()
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
            db.query(Service)
            .filter(Service.service_code == unique_code)
            .first()
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

    return integration_result


def _collect_department_overview(db: Session) -> Dict[str, Any]:
    """Формирует реальные показатели по отделениям."""
    today = date.today()
    departments = db.query(Department).order_by(Department.display_order).all()
    overview_items: List[Dict[str, Any]] = []

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


@router.get("", response_model=dict)
def list_departments(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Получить список всех отделений

    Доступно только для администраторов
    """
    query = db.query(Department)

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

    return {
        "success": True,
        "data": data,
        "count": len(departments)
    }


@router.get("/overview", response_model=dict)
def get_departments_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
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
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Получить отделение по ID

    Доступно только для администраторов
    """
    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found"
        )

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict()
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_department(
    department_data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Создать новое отделение

    Доступно только для администраторов
    """
    # Проверяем уникальность ключа
    existing = db.query(Department).filter(Department.key == department_data.key).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department with key '{department_data.key}' already exists"
        )

    payload = department_data.dict(exclude={"integration"})

    # Создаем новое отделение
    department = Department(**payload)
    db.add(department)
    db.flush()

    integration_result = _ensure_department_integrations(
        db, department, department_data.integration
    )

    db.commit()
    db.refresh(department)

    # Создаем дефолтные настройки очереди
    queue_settings = DepartmentQueueSettings(
        department_id=department.id,
        queue_prefix=department.key.upper()[0] if department.key else "Q"
    )
    db.add(queue_settings)

    # Создаем дефолтные настройки регистрации
    reg_settings = DepartmentRegistrationSettings(
        department_id=department.id
    )
    db.add(reg_settings)
    
    db.commit()

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
        "integration": integration_result,
        "message": "Department created successfully"
    }


@router.put("/{department_id}", response_model=dict)
def update_department(
    department_id: int,
    department_data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Обновить отделение

    Доступно только для администраторов
    """
    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found"
        )

    # Обновляем только переданные поля
    update_data = department_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(department, field, value)

    db.commit()
    db.refresh(department)

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
        "message": "Department updated successfully"
    }


@router.post("/{department_id}/initialize", response_model=dict)
def initialize_department(
    department_id: int,
    integration: Optional[DepartmentIntegrationOptions] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Повторно синхронизировать отделение с очередями/услугами

    Позволяет принудительно создать настройки очередей, регистрацию и дефолтные услуги.
    """
    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found"
        )

    integration_result = _ensure_department_integrations(db, department, integration)
    db.commit()
    db.refresh(department)

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
        "integration": integration_result,
        "message": "Department integrations initialized"
    }


@router.delete("/{department_id}", response_model=dict)
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Удалить отделение

    Доступно только для администраторов
    """
    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found"
        )

    db.delete(department)
    db.commit()

    return {
        "success": True,
        "message": f"Department '{department.name_ru}' deleted successfully"
    }


@router.post("/{department_id}/toggle", response_model=dict)
def toggle_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Переключить активность отделения

    Доступно только для администраторов
    """
    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found"
        )

    # Переключаем active
    department.active = not department.active
    db.commit()
    db.refresh(department)

    status_text = "активировано" if department.active else "деактивировано"

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
        "message": f"Department '{department.name_ru}' {status_text}"
    }


# ============================================================
# УПРАВЛЕНИЕ УСЛУГАМИ ОТДЕЛЕНИЯ
# ============================================================

@router.get("/{department_id}/services", response_model=dict)
def get_department_services(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить услуги отделения"""
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    services = db.query(DepartmentService).filter(
        DepartmentService.department_id == department_id
    ).order_by(DepartmentService.display_order).all()

    return {
        "success": True,
        "data": [
            {
                "id": ds.id,
                "service": {
                    "id": ds.service.id,
                    "name": ds.service.name,
                    "code": ds.service.code,
                    "base_price": float(ds.service.price) if ds.service.price else None
                },
                "is_default": ds.is_default,
                "display_order": ds.display_order,
                "price_override": float(ds.price_override) if ds.price_override else None
            }
            for ds in services
        ],
        "count": len(services)
    }


@router.post("/{department_id}/services/{service_id}", response_model=dict)
def add_service_to_department(
    department_id: int,
    service_id: int,
    data: DepartmentServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Добавить услугу в отделение"""
    # Проверки
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Проверка дубликатов
    existing = db.query(DepartmentService).filter(
        DepartmentService.department_id == department_id,
        DepartmentService.service_id == service_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Service already added to department")

    # Создание привязки
    dept_service = DepartmentService(
        department_id=department_id,
        service_id=service_id,
        **data.dict()
    )
    db.add(dept_service)
    db.commit()
    db.refresh(dept_service)

    return {
        "success": True,
        "message": f"Service '{service.name}' added to department"
    }


@router.delete("/{department_id}/services/{service_id}", response_model=dict)
def remove_service_from_department(
    department_id: int,
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Удалить услугу из отделения"""
    dept_service = db.query(DepartmentService).filter(
        DepartmentService.department_id == department_id,
        DepartmentService.service_id == service_id
    ).first()

    if not dept_service:
        raise HTTPException(status_code=404, detail="Service not found in department")

    db.delete(dept_service)
    db.commit()

    return {
        "success": True,
        "message": "Service removed from department"
    }


# ============================================================
# УПРАВЛЕНИЕ НАСТРОЙКАМИ ОЧЕРЕДИ
# ============================================================

@router.get("/{department_id}/settings/queue", response_model=dict)
def get_queue_settings(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить настройки очереди отделения"""
    settings = db.query(DepartmentQueueSettings).filter(
        DepartmentQueueSettings.department_id == department_id
    ).first()

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
            "auto_close_time": settings.auto_close_time
        }
    }


@router.put("/{department_id}/settings/queue", response_model=dict)
def update_queue_settings(
    department_id: int,
    data: DepartmentQueueSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Обновить настройки очереди отделения"""
    settings = db.query(DepartmentQueueSettings).filter(
        DepartmentQueueSettings.department_id == department_id
    ).first()

    if not settings:
        # Если настроек нет, создаем их
        settings = DepartmentQueueSettings(department_id=department_id)
        db.add(settings)
        # Не делаем commit здесь, он будет ниже


    # Обновление полей
    for field, value in data.dict(exclude_unset=True).items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)

    return {
        "success": True,
        "message": "Queue settings updated"
    }


# ============================================================
# ОБЗОР СТАТИСТИКИ ОТДЕЛЕНИЙ
# ============================================================

@router.get("/overview", response_model=dict)
def get_departments_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить обзор статистики всех отделений"""
    departments = db.query(Department).order_by(Department.display_order).all()

    totals = {
        "departments": len(departments),
        "active": len([d for d in departments if d.active]),
        "queue_enabled": 0,
        "appointments_today": 0,
        "visits_today": 0,
    }

    departments_overview = []
    for dept in departments:
        # Получаем настройки очереди
        queue_settings = db.query(DepartmentQueueSettings).filter(
            DepartmentQueueSettings.department_id == dept.id
        ).first()

        # Получаем настройки регистрации
        reg_settings = db.query(DepartmentRegistrationSettings).filter(
            DepartmentRegistrationSettings.department_id == dept.id
        ).first()

        # Получаем услуги отделения
        dept_services = db.query(DepartmentService).filter(
            DepartmentService.department_id == dept.id
        ).all()

        # Получаем врачей отделения
        doctors = db.query(Doctor).filter(
            Doctor.department_id == dept.id
        ).all()

        # Подсчитываем сегодняшние записи
        from datetime import date
        today = date.today()

        # Записи на сегодня
        appointments_today = db.query(Appointment).filter(
            Appointment.department_id == dept.id,
            Appointment.date == today
        ).count()

        # Визиты на сегодня
        visits_today = db.query(Visit).filter(
            Visit.department_id == dept.id,
            Visit.created_at >= today
        ).count()

        # Записи в очереди на сегодня
        queue_entries_today = 0
        if queue_settings:
            totals["queue_enabled"] += 1

        totals["appointments_today"] += appointments_today
        totals["visits_today"] += visits_today

        departments_overview.append({
            "key": dept.key,
            "stats": {
                "appointments_today": appointments_today,
                "visits_today": visits_today,
                "queue_entries_today": queue_entries_today,
                "services": len(dept_services),
                "doctors": len(doctors),
            },
            "integrations": {
                "has_queue_settings": queue_settings is not None,
                "has_registration_settings": reg_settings is not None,
                "has_services": len(dept_services) > 0,
                "has_service_category": bool(dept_services),  # Упрощенно
                "queue_prefix": queue_settings.queue_prefix if queue_settings else None,
                "start_number": queue_settings.start_number_online if queue_settings else None,
                "max_per_day": queue_settings.max_daily_queue if queue_settings else None,
            }
        })

    return {
        "success": True,
        "data": {
            "totals": totals,
            "departments": departments_overview
        }
    }


@router.post("/{department_id}/initialize", response_model=dict)
def initialize_department(
    department_id: int,
    payload: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Инициализировать отделение - создать настройки очередей и регистрации"""
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    try:
        # Создаем настройки очереди если их нет
        queue_settings = db.query(DepartmentQueueSettings).filter(
            DepartmentQueueSettings.department_id == department_id
        ).first()

        if not queue_settings:
            queue_settings = DepartmentQueueSettings(
                department_id=department_id,
                enabled=True,
                queue_type="mixed",
                queue_prefix=payload.get("queue_prefix") if payload else None,
                max_daily_queue=payload.get("max_daily_queue", 50) if payload else 50,
                avg_wait_time=20,
                show_on_display=True,
                auto_close_time="09:00"
            )
            db.add(queue_settings)

        # Создаем настройки регистрации если их нет
        reg_settings = db.query(DepartmentRegistrationSettings).filter(
            DepartmentRegistrationSettings.department_id == department_id
        ).first()

        if not reg_settings:
            reg_settings = DepartmentRegistrationSettings(
                department_id=department_id,
                online_booking_enabled=True,
                requires_confirmation=False,
                min_booking_hours=2,
                max_booking_days=30,
                auto_assign_doctor=False,
                allow_walkin=True
            )
            db.add(reg_settings)

        # Создаем дефолтную услугу если переданы данные
        if payload and (payload.get("service_name") or payload.get("service_code")):
            # Проверяем, что услуга не существует
            existing_service = db.query(Service).filter(
                Service.code == payload.get("service_code")
            ).first()

            if not existing_service:
                # Находим категорию услуги
                category = None
                if payload.get("service_category_code"):
                    category = db.query(ServiceCategory).filter(
                        ServiceCategory.code == payload.get("service_category_code")
                    ).first()

                service = Service(
                    name=payload.get("service_name", f"Услуга отделения {department.name_ru}"),
                    code=payload.get("service_code"),
                    department_key=department.key,
                    category_code=payload.get("service_category_code"),
                    service_code=payload.get("service_code"),
                    price=payload.get("service_price", 0),
                    currency=payload.get("service_currency", "UZS"),
                    active=True,
                    requires_doctor=True,
                    category_id=category.id if category else None
                )
                db.add(service)

                # Создаем связь с отделением
                dept_service = DepartmentService(
                    department_id=department_id,
                    service=service,
                    is_default=True,
                    display_order=1,
                    price_override=payload.get("service_price")
                )
                db.add(dept_service)

        db.commit()

        return {
            "success": True,
            "message": f"Отделение '{department.name_ru}' инициализировано"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка инициализации отделения: {str(e)}"
        )


# ============================================================
# УПРАВЛЕНИЕ НАСТРОЙКАМИ РЕГИСТРАЦИИ
# ============================================================

@router.get("/{department_id}/settings/registration", response_model=dict)
def get_registration_settings(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить настройки регистрации отделения"""
    settings = db.query(DepartmentRegistrationSettings).filter(
        DepartmentRegistrationSettings.department_id == department_id
    ).first()

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
            "allow_walkin": settings.allow_walkin
        }
    }


@router.put("/{department_id}/settings/registration", response_model=dict)
def update_registration_settings(
    department_id: int,
    data: DepartmentRegistrationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Обновить настройки регистрации отделения"""
    settings = db.query(DepartmentRegistrationSettings).filter(
        DepartmentRegistrationSettings.department_id == department_id
    ).first()

    if not settings:
        # Если настроек нет, создаем их
        settings = DepartmentRegistrationSettings(department_id=department_id)
        db.add(settings)


    # Обновление полей
    for field, value in data.dict(exclude_unset=True).items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)

    return {
        "success": True,
        "message": "Registration settings updated"
    }


# ============================================================
# УПРАВЛЕНИЕ ВРАЧАМИ ОТДЕЛЕНИЯ
# ============================================================

@router.get("/{department_id}/doctors", response_model=dict)
def get_department_doctors(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Получить список врачей отделения"""
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    doctors = db.query(Doctor).filter(
        Doctor.department_id == department_id
    ).all()

    return {
        "success": True,
        "data": [
            {
                "id": doctor.id,
                "user_id": doctor.user_id,
                "name": doctor.user.full_name if doctor.user else None,
                "specialty": doctor.specialty
            }
            for doctor in doctors
        ],
        "count": len(doctors)
    }


@router.post("/{department_id}/doctors/{doctor_id}", response_model=dict)
def assign_doctor_to_department(
    department_id: int,
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Назначить врача в отделение"""
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # Назначение
    doctor.department_id = department_id
    db.commit()
    db.refresh(doctor)

    return {
        "success": True,
        "message": f"Doctor assigned to department '{department.name_ru}'"
    }


@router.delete("/{department_id}/doctors/{doctor_id}", response_model=dict)
def remove_doctor_from_department(
    department_id: int,
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Убрать врача из отделения"""
    doctor = db.query(Doctor).filter(
        Doctor.id == doctor_id,
        Doctor.department_id == department_id
    ).first()

    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found in this department")

    # Убираем привязку
    doctor.department_id = None
    db.commit()

    return {
        "success": True,
        "message": "Doctor removed from department"
    }
