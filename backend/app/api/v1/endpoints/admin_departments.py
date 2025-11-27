"""
CRUD endpoints для управления отделениями в админ-панели
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.api.deps import get_db, require_roles
from app.models.department import (
    Department,
    DepartmentService,
    DepartmentQueueSettings,
    DepartmentRegistrationSettings
)
from app.models.clinic import Doctor
from app.models.service import Service
from app.models.user import User
from app.schemas.department import (
    DepartmentServiceCreate,
    DepartmentQueueSettingsUpdate,
    DepartmentRegistrationSettingsUpdate
)

router = APIRouter()


# Pydantic schemas
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


@router.get("", response_model=dict)
def list_departments(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Получить список всех отделений

    Доступно только для администраторов
    """
    query = db.query(Department)

    if active_only:
        query = query.filter(Department.active == True)

    departments = query.order_by(Department.display_order).all()

    return {
        "success": True,
        "data": [DepartmentResponse.from_orm(d).dict() for d in departments],
        "count": len(departments)
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

    # Создаем новое отделение
    department = Department(**department_data.dict())
    db.add(department)
    db.commit()
    db.refresh(department)

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
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
        raise HTTPException(status_code=404, detail="Queue settings not found")

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
        raise HTTPException(status_code=404, detail="Registration settings not found")

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
