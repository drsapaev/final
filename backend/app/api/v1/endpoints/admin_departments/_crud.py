"""Split from app.api.v1.endpoints.admin_departments.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.admin_departments._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.admin_departments._helpers import (
    router,
    _collect_department_overview,
    _ensure_department_integrations,
)  # noqa: F401


@router.get("", response_model=dict)
def list_departments(    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
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

    return {"success": True, "data": data, "count": len(departments)}


@router.get("/overview", response_model=dict)
def get_departments_overview(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """
    Получить реальные показатели по отделениям (очередь, услуги, визиты)
    """
    # Resolve via the package namespace so tests can monkeypatch
    # ``admin_departments._collect_department_overview`` and have the patch
    # take effect on the live endpoint.
    from app.api.v1.endpoints import admin_departments as _admin_departments

    overview = _admin_departments._collect_department_overview(db)
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
    department = db.query(Department).filter(Department.id == department_id).first()

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
        db.query(Department).filter(Department.key == department_data.key).first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Department with key '{department_data.key}' already exists",
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
        queue_prefix=department.key.upper()[0] if department.key else "Q",
    )
    db.add(queue_settings)

    # Создаем дефолтные настройки регистрации
    reg_settings = DepartmentRegistrationSettings(department_id=department.id)
    db.add(reg_settings)

    db.commit()

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
        "integration": integration_result,
        "message": "Department created successfully",
    }


# ==================== PR-18: BULK OPERATIONS ====================
# IMPORTANT: These static routes MUST be registered BEFORE /{department_id}
# routes, otherwise FastAPI matches /{department_id} first and treats
# "bulk-delete" as a department_id value.


@router.post("/bulk", response_model=dict)
def bulk_create_departments(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Массовое создание отделений (CSV импорт).

    PR-18: Frontend DepartmentManagement.jsx calls this endpoint for CSV
    import. Body: { departments: [{name_ru, name_uz, key, ...}, ...] }
    """
    departments_data = payload.get("departments", [])
    if not departments_data or not isinstance(departments_data, list):
        raise HTTPException(status_code=400, detail="departments list is required")

    created = 0
    skipped = 0
    errors = []

    for idx, dept_data in enumerate(departments_data):
        try:
            key = dept_data.get("key", "").strip().lower()
            if not key:
                errors.append(f"Row {idx + 1}: key is required")
                skipped += 1
                continue

            existing = db.query(Department).filter(Department.key == key).first()
            if existing:
                skipped += 1
                continue

            department = Department(
                key=key,
                name_ru=dept_data.get("name_ru", key),
                name_uz=dept_data.get("name_uz", ""),
                icon=dept_data.get("icon", "Layers"),
                color=dept_data.get("color", "#3b82f6"),
                display_order=int(dept_data.get("display_order", 999)),
                active=dept_data.get("active", True),
                description=dept_data.get("description", ""),
            )
            db.add(department)
            db.flush()

            _ensure_department_integrations(db, department)
            created += 1
        except Exception as exc:
            errors.append(f"Row {idx + 1}: {str(exc)}")
            skipped += 1

    db.commit()

    return {
        "success": True,
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "message": f"Импортировано {created} отделений, пропущено {skipped}",
    }


@router.delete("/bulk-delete", response_model=dict)
def bulk_delete_departments(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Массовое удаление отделений.

    PR-18: Frontend DepartmentManagement.jsx calls this endpoint for bulk
    delete. Body: { ids: [1, 2, 3] }
    """
    ids = payload.get("ids", [])
    if not ids or not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="ids list is required")

    deleted = 0
    not_found = 0

    for dept_id in ids:
        department = db.query(Department).filter(Department.id == dept_id).first()
        if not department:
            not_found += 1
            continue
        db.delete(department)
        deleted += 1

    db.commit()

    return {
        "success": True,
        "deleted": deleted,
        "not_found": not_found,
        "message": f"Удалено {deleted} отделений",
    }


@router.patch("/bulk-activate", response_model=dict)
def bulk_activate_departments(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Массовая активация/деактивация отделений.

    PR-18: Frontend DepartmentManagement.jsx calls this endpoint for bulk
    activate/deactivate. Body: { ids: [1, 2, 3], active: true/false }
    """
    ids = payload.get("ids", [])
    active = payload.get("active")
    if not ids or not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="ids list is required")
    if active is None:
        raise HTTPException(status_code=400, detail="active boolean is required")

    updated = 0
    not_found = 0

    for dept_id in ids:
        department = db.query(Department).filter(Department.id == dept_id).first()
        if not department:
            not_found += 1
            continue
        department.active = bool(active)
        updated += 1

    db.commit()

    action = "активировано" if active else "деактивировано"
    return {
        "success": True,
        "updated": updated,
        "not_found": not_found,
        "message": f"{action.capitalize()} {updated} отделений",
    }


# ==================== END BULK OPERATIONS ====================


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
    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found",
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
        "message": "Department updated successfully",
    }


@router.post("/{department_id}/initialize", response_model=dict, include_in_schema=False)
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
    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found",
        )

    integration_result = _ensure_department_integrations(db, department, integration)
    db.commit()
    db.refresh(department)

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

    Доступно только для администраторов.
    PR-22: cascades cleanup — clears department_key from services, deletes
    DepartmentService/DepartmentQueueSettings/DepartmentRegistrationSettings,
    and deletes associated QueueProfile.
    """
    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found",
        )

    # PR-22: cascade cleanup
    cleaned = {"services": 0, "department_services": 0, "queue_settings": 0,
               "registration_settings": 0, "queue_profile": False}

    # Clear department_key from services
    from app.models.service import Service
    services = db.query(Service).filter(Service.department_key == department.key).all()
    for svc in services:
        svc.department_key = None
        cleaned["services"] += 1

    # Delete DepartmentService links
    dept_services = db.query(DepartmentService).filter(
        DepartmentService.department_id == department_id
    ).all()
    for ds in dept_services:
        db.delete(ds)
        cleaned["department_services"] += 1

    # Delete DepartmentQueueSettings
    queue_settings = db.query(DepartmentQueueSettings).filter(
        DepartmentQueueSettings.department_id == department_id
    ).first()
    if queue_settings:
        db.delete(queue_settings)
        cleaned["queue_settings"] = 1

    # Delete DepartmentRegistrationSettings
    reg_settings = db.query(DepartmentRegistrationSettings).filter(
        DepartmentRegistrationSettings.department_id == department_id
    ).first()
    if reg_settings:
        db.delete(reg_settings)
        cleaned["registration_settings"] = 1

    # Delete associated QueueProfile
    from app.models.queue_profile import QueueProfile
    queue_profile = db.query(QueueProfile).filter(
        QueueProfile.key == department.key
    ).first()
    if queue_profile:
        db.delete(queue_profile)
        cleaned["queue_profile"] = True

    db.delete(department)
    db.commit()

    logger.info(
        f"Deleted department '{department.name_ru}' (cascade: {cleaned})"
    )

    return {
        "success": True,
        "message": f"Department '{department.name_ru}' deleted successfully",
        "cascade": cleaned,
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
    department = db.query(Department).filter(Department.id == department_id).first()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Department with id {department_id} not found",
        )

    # Переключаем active
    department.active = not department.active
    db.commit()
    db.refresh(department)

    status_text = "активировано" if department.active else "деактивировано"

    return {
        "success": True,
        "data": DepartmentResponse.from_orm(department).dict(),
        "message": f"Department '{department.name_ru}' {status_text}",
    }


# ============================================================
# УПРАВЛЕНИЕ УСЛУГАМИ ОТДЕЛЕНИЯ
# ============================================================


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
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Проверка дубликатов
    existing = (
        db.query(DepartmentService)
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
    db.add(dept_service)
    db.commit()
    db.refresh(dept_service)

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
        db.query(DepartmentService)
        .filter(
            DepartmentService.department_id == department_id,
            DepartmentService.service_id == service_id,
        )
        .first()
    )

    if not dept_service:
        raise HTTPException(status_code=404, detail="Service not found in department")

    db.delete(dept_service)
    db.commit()

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
        db.query(DepartmentQueueSettings)
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
        db.query(DepartmentQueueSettings)
        .filter(DepartmentQueueSettings.department_id == department_id)
        .first()
    )

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

    return {"success": True, "message": "Queue settings updated"}


# ============================================================
# ОБЗОР СТАТИСТИКИ ОТДЕЛЕНИЙ
# ============================================================


def _legacy_departments_overview_payload(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
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
        queue_settings = (
            db.query(DepartmentQueueSettings)
            .filter(DepartmentQueueSettings.department_id == dept.id)
            .first()
        )

        # Получаем настройки регистрации
        reg_settings = (
            db.query(DepartmentRegistrationSettings)
            .filter(DepartmentRegistrationSettings.department_id == dept.id)
            .first()
        )

        # Получаем услуги отделения
        dept_services = (
            db.query(DepartmentService)
            .filter(DepartmentService.department_id == dept.id)
            .all()
        )

        # Получаем врачей отделения
        doctors = db.query(Doctor).filter(Doctor.department_id == dept.id).all()

        # Подсчитываем сегодняшние записи
        from datetime import date

        today = date.today()

        # Записи на сегодня
        appointments_today = (
            db.query(Appointment)
            .filter(Appointment.department_id == dept.id, Appointment.date == today)
            .count()
        )

        # Визиты на сегодня
        visits_today = (
            db.query(Visit)
            .filter(Visit.department_id == dept.id, Visit.created_at >= today)
            .count()
        )

        # Записи в очереди на сегодня
        queue_entries_today = 0
        if queue_settings:
            totals["queue_enabled"] += 1

        totals["appointments_today"] += appointments_today
        totals["visits_today"] += visits_today

        departments_overview.append(
            {
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
                    "queue_prefix": (
                        queue_settings.queue_prefix if queue_settings else None
                    ),
                    "start_number": (
                        queue_settings.start_number_online if queue_settings else None
                    ),
                    "max_per_day": (
                        queue_settings.max_daily_queue if queue_settings else None
                    ),
                },
            }
        )

    return {
        "success": True,
        "data": {"totals": totals, "departments": departments_overview},
    }


# P0-4 FIX (ENDPOINT-VALIDATION-AUDIT):
# A DUPLICATE initialize_department handler was previously defined here
# (lines 956-1077 in the pre-fix file). It accepted `payload: dict[str, Any]`
# (unvalidated body) and was dead code — FastAPI uses first-registration-
# wins, so the canonical handler at line 574 (which accepts
# `integration: DepartmentIntegrationOptions | None` and is properly
# typed) was always the one executed.
# The duplicate was marked `# noqa: F811  # manual-review: intentional
# redefinition for compatibility` but the "compatibility" claim was
# incorrect — both handlers registered the same route, only the first
# could ever be reached. Removed the dead duplicate. This also removes
# one P0 unvalidated-body endpoint (admin_departments.py:957 was on the
# P0 list with `payload: dict[str, Any] | None`).


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
        db.query(DepartmentRegistrationSettings)
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
        db.query(DepartmentRegistrationSettings)
        .filter(DepartmentRegistrationSettings.department_id == department_id)
        .first()
    )

    if not settings:
        # Если настроек нет, создаем их
        settings = DepartmentRegistrationSettings(department_id=department_id)
        db.add(settings)

    # Обновление полей
    for field, value in data.dict(exclude_unset=True).items():
        setattr(settings, field, value)

    db.commit()
    db.refresh(settings)

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
    department = db.query(Department).filter(Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")

    doctors = db.query(Doctor).filter(Doctor.department_id == department_id).all()

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
        db.query(Doctor)
        .filter(Doctor.id == doctor_id, Doctor.department_id == department_id)
        .first()
    )

    if not doctor:
        raise HTTPException(
            status_code=404, detail="Doctor not found in this department"
        )

    # Убираем привязку
    doctor.department_id = None
    db.commit()

    return {"success": True, "message": "Doctor removed from department"}


