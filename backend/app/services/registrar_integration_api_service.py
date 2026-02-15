"""
API endpoints для интеграции регистратуры с админ панелью
Основа: detail.md стр. 85-183
"""

import logging
import traceback
from datetime import UTC, date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import clinic as crud_clinic
from app.crud import online_queue as crud_queue
from app.models.department import Department, DepartmentService
from app.models.service import Service
from app.models.user import User
from app.services.queue_batch_service import (
    QueueBatchDomainError,
    QueueBatchService,
    QueueBatchServiceItem,
)
from app.services.queue_service import queue_service
from app.services.service_mapping import get_service_code

# [OK] Используем прямой SQL вместо импорта модели для избежания конфликта DailyQueue
# Проблема: DailyQueue определен в двух местах (queue_old.py и online_queue.py)
# Решение: используем прямой SQL запрос через text() для доступа к queue_entries без импорта модели

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================== ОТДЕЛЕНИЯ ДЛЯ РЕГИСТРАТУРЫ =====================


@router.get("/registrar/departments")
def get_registrar_departments(
    active_only: bool = Query(True, description="Только активные отделения"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Registrar", "Doctor", "Cashier")
    ),
):
    """
    Получить список отделений для регистратуры
    Доступен для регистраторов, в отличие от admin endpoint
    """
    try:
        query = db.query(Department)

        if active_only:
            query = query.filter(Department.active == True)

        # Сортируем по display_order
        query = query.order_by(Department.display_order)

        departments = query.all()

        # Формируем ответ
        result = []
        for dept in departments:
            # Получаем queue_prefix из настроек очереди
            from app.models.department import DepartmentQueueSettings

            queue_settings = (
                db.query(DepartmentQueueSettings)
                .filter(DepartmentQueueSettings.department_id == dept.id)
                .first()
            )

            result.append(
                {
                    "id": dept.id,
                    "key": dept.key,
                    "name_ru": dept.name_ru,
                    "name_uz": dept.name_uz,
                    "icon": dept.icon,
                    "color": dept.color,
                    "gradient": dept.gradient,
                    "display_order": dept.display_order,
                    "active": dept.active,
                    "description": dept.description,
                    "queue_prefix": (
                        queue_settings.queue_prefix
                        if queue_settings
                        else dept.key.upper()[0]
                    ),
                }
            )

        return {"success": True, "data": result, "count": len(result)}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения отделений: {str(e)}",
        )


# ===================== СПРАВОЧНИК УСЛУГ ДЛЯ РЕГИСТРАТУРЫ =====================


# ===================== ПРОФИЛИ ОЧЕРЕДЕЙ (DYNAMIC TABS) =====================


@router.get("/queues/profiles")
def get_queue_profiles(
    active_only: bool = Query(True, description="Только активные профили"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Registrar", "Doctor", "Cashier", "Lab")
    ),
):
    """
    Получить список профилей очередей для динамических вкладок.

    Каждый профиль определяет:
    - key: уникальный ключ (cardiology, ecg, dermatology и т.д.)
    - title/title_ru: названия для отображения
    - queue_tags: список queue_tag значений, которые относятся к этому профилю
    - icon/color: UI конфигурация

    Frontend использует queue_tags для фильтрации записей по вкладкам.

    SSOT: Вкладки определяются в БД, НЕ хардкодятся в frontend.
    """
    try:
        from app.models.queue_profile import INITIAL_QUEUE_PROFILES, QueueProfile

        # Пытаемся получить из БД
        query = db.query(QueueProfile)

        if active_only:
            query = query.filter(QueueProfile.is_active == True)

        profiles = query.order_by(QueueProfile.display_order).all()

        # Если таблица не существует или пуста - возвращаем fallback
        if not profiles:
            logger.warning("Queue profiles table is empty, returning hardcoded fallback")
            return {
                "success": True,
                "profiles": [
                    {
                        "key": p["key"],
                        "title": p["title"],
                        "title_ru": p["title_ru"],
                        "queue_tags": p["queue_tags"],
                        "department_key": p.get("department_key"),
                        "icon": p.get("icon"),
                        "color": p.get("color"),
                        "order": p.get("order", 0),
                    }
                    for p in INITIAL_QUEUE_PROFILES
                ],
                "source": "fallback",
            }

        return {
            "success": True,
            "profiles": [
                {
                    "key": p.key,
                    "title": p.title,
                    "title_ru": p.title_ru,
                    "queue_tags": p.queue_tags or [],
                    "department_key": p.department_key,
                    "icon": p.icon,
                    "color": p.color,
                    "order": p.display_order,  # API returns as 'order' for frontend compatibility
                    "is_active": p.is_active,
                    "show_on_qr_page": getattr(p, 'show_on_qr_page', True),  # Handle missing column
                }
                for p in profiles
            ],
            "source": "database",
        }

    except Exception as e:
        # При любой ошибке (включая отсутствие таблицы) возвращаем fallback
        logger.error("Error fetching queue profiles: %s", e)
        from app.models.queue_profile import INITIAL_QUEUE_PROFILES

        return {
            "success": True,
            "profiles": [
                {
                    "key": p["key"],
                    "title": p["title"],
                    "title_ru": p["title_ru"],
                    "queue_tags": p["queue_tags"],
                    "department_key": p.get("department_key"),
                    "icon": p.get("icon"),
                    "color": p.get("color"),
                    "order": p.get("order", 0),
                }
                for p in INITIAL_QUEUE_PROFILES
            ],
            "source": "fallback_error",
            "error": str(e),
        }


@router.get("/queues/profiles/public")
def get_queue_profiles_public(
    db: Session = Depends(get_db),
):
    """
    ⭐ PUBLIC ENDPOINT: Получить список профилей для QR-страницы регистрации.

    Не требует авторизации - используется пациентами при самостоятельной регистрации.
    Возвращает только профили с is_active=True И show_on_qr_page=True.

    Используется на странице /queue/join для выбора специальности.
    """
    try:
        from app.models.queue_profile import INITIAL_QUEUE_PROFILES, QueueProfile

        # Получаем только активные профили, которые видны на QR странице
        profiles = (
            db.query(QueueProfile)
            .filter(
                QueueProfile.is_active == True,
                QueueProfile.show_on_qr_page == True
            )
            .order_by(QueueProfile.display_order)
            .all()
        )

        if not profiles:
            # Fallback: возвращаем все из INITIAL_QUEUE_PROFILES (кроме general и ecg)
            logger.warning("Queue profiles table is empty for QR page, returning fallback")
            return {
                "success": True,
                "specialists": [
                    {
                        "id": idx + 1,
                        "specialty": p["key"],
                        "specialty_display": p["title_ru"] or p["title"],
                        "icon": _get_emoji_for_key(p["key"]),
                        "color": p.get("color", "#6b7280"),
                    }
                    for idx, p in enumerate(INITIAL_QUEUE_PROFILES)
                    if p["key"] not in ["general", "ecg"]  # Exclude general and ecg from QR
                ],
                "source": "fallback",
            }

        return {
            "success": True,
            "specialists": [
                {
                    "id": p.id,
                    "specialty": p.key,
                    "specialty_display": p.title_ru or p.title,
                    "icon": _get_emoji_for_key(p.key),
                    "color": p.color or "#6b7280",
                }
                for p in profiles
            ],
            "source": "database",
        }

    except Exception as e:
        logger.error("Error fetching queue profiles for QR page: %s", e)
        # Fallback на базовый список
        return {
            "success": True,
            "specialists": [
                {"id": 1, "specialty": "cardiology", "specialty_display": "Кардиолог", "icon": "❤️", "color": "#FF3B30"},
                {"id": 2, "specialty": "dermatology", "specialty_display": "Дерматолог", "icon": "✨", "color": "#FF9500"},
                {"id": 3, "specialty": "stomatology", "specialty_display": "Стоматолог", "icon": "🦷", "color": "#007AFF"},
                {"id": 4, "specialty": "lab", "specialty_display": "Лаборатория", "icon": "🔬", "color": "#34C759"},
            ],
            "source": "fallback_error",
            "error": str(e),
        }


def _get_emoji_for_key(key: str) -> str:
    """Helper to get emoji icon for profile key"""
    emoji_map = {
        "cardiology": "❤️",
        "ecg": "📊",
        "dermatology": "✨",
        "stomatology": "🦷",
        "lab": "🔬",
        "laboratory": "🔬",
        "procedures": "💉",
        "cosmetology": "💄",
        "general": "👥",
    }
    return emoji_map.get(key, "👨‍⚕️")


# ===================== QUEUE PROFILE CRUD (ADMIN) =====================




class QueueProfileCreate(BaseModel):
    """Schema for creating a new QueueProfile"""
    key: str = Field(..., min_length=1, max_length=50, description="Unique key (e.g., 'cardiology')")
    title: str = Field(..., min_length=1, max_length=100, description="English title")
    title_ru: str | None = Field(None, max_length=100, description="Russian title")
    queue_tags: list[str] = Field(default=[], description="List of queue_tag values for this profile")
    department_key: str | None = Field(None, max_length=50)
    display_order: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)
    show_on_qr_page: bool = Field(default=True, description="Show this profile on QR join page")
    icon: str | None = Field(None, max_length=50, description="Lucide icon name (e.g., 'Heart')")
    color: str | None = Field(None, max_length=20, description="Hex color (e.g., '#E53E3E')")


class QueueProfileUpdate(BaseModel):
    """Schema for updating an existing QueueProfile"""
    title: str | None = Field(None, max_length=100)
    title_ru: str | None = Field(None, max_length=100)
    queue_tags: list[str] | None = None
    department_key: str | None = Field(None, max_length=50)
    display_order: int | None = Field(None, ge=0)
    is_active: bool | None = None
    show_on_qr_page: bool | None = Field(None, description="Show this profile on QR join page")
    icon: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=20)


@router.post("/queues/profiles")
def create_queue_profile(
    profile_data: QueueProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Create a new QueueProfile (admin only).

    SSOT: Tabs are defined in DB, not hardcoded in frontend.
    """
    try:
        from app.models.queue_profile import QueueProfile

        # Check if key already exists
        existing = db.query(QueueProfile).filter(QueueProfile.key == profile_data.key).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Profile with key '{profile_data.key}' already exists")

        # Create new profile
        new_profile = QueueProfile(
            key=profile_data.key,
            title=profile_data.title,
            title_ru=profile_data.title_ru,
            queue_tags=profile_data.queue_tags,
            department_key=profile_data.department_key,
            display_order=profile_data.display_order,
            is_active=profile_data.is_active,
            icon=profile_data.icon,
            color=profile_data.color,
        )

        db.add(new_profile)
        db.commit()
        db.refresh(new_profile)

        logger.info(f"Created QueueProfile: {new_profile.key}")

        return {
            "success": True,
            "profile": {
                "id": new_profile.id,
                "key": new_profile.key,
                "title": new_profile.title,
                "title_ru": new_profile.title_ru,
                "queue_tags": new_profile.queue_tags or [],
                "department_key": new_profile.department_key,
                "order": new_profile.display_order,
                "is_active": new_profile.is_active,
                "icon": new_profile.icon,
                "color": new_profile.color,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating queue profile: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/queues/profiles/{profile_key}")
def update_queue_profile(
    profile_key: str,
    profile_data: QueueProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Update an existing QueueProfile by key (admin only).

    SSOT: Changes here reflect immediately in Registrar Panel tabs.
    """
    try:
        from app.models.queue_profile import QueueProfile

        # Find profile
        profile = db.query(QueueProfile).filter(QueueProfile.key == profile_key).first()
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile '{profile_key}' not found")

        # Update fields (only those provided)
        update_data = profile_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)

        db.commit()
        db.refresh(profile)

        logger.info(f"Updated QueueProfile: {profile.key}")

        return {
            "success": True,
            "profile": {
                "id": profile.id,
                "key": profile.key,
                "title": profile.title,
                "title_ru": profile.title_ru,
                "queue_tags": profile.queue_tags or [],
                "department_key": profile.department_key,
                "order": profile.display_order,
                "is_active": profile.is_active,
                "icon": profile.icon,
                "color": profile.color,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating queue profile: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/queues/profiles/{profile_key}")
def delete_queue_profile(
    profile_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Delete a QueueProfile by key (admin only).

    Warning: This will remove the tab from Registrar Panel.
    """
    try:
        from app.models.queue_profile import QueueProfile

        # Find profile
        profile = db.query(QueueProfile).filter(QueueProfile.key == profile_key).first()
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile '{profile_key}' not found")

        db.delete(profile)
        db.commit()

        logger.info(f"Deleted QueueProfile: {profile_key}")

        return {
            "success": True,
            "message": f"Profile '{profile_key}' deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting queue profile: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/queues/profiles/reorder")
def reorder_queue_profiles(
    orders: dict,  # {"profile_key": new_order, ...}
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Batch update display_order for multiple profiles (admin only).

    Request body: {"cardiology": 1, "ecg": 2, "dermatology": 3, ...}
    """
    try:
        from app.models.queue_profile import QueueProfile

        updated = 0
        for key, order in orders.items():
            profile = db.query(QueueProfile).filter(QueueProfile.key == key).first()
            if profile:
                profile.display_order = order
                updated += 1

        db.commit()

        logger.info(f"Reordered {updated} QueueProfiles")

        return {
            "success": True,
            "updated": updated,
        }

    except Exception as e:
        logger.error(f"Error reordering queue profiles: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ===================== СПРАВОЧНИК УСЛУГ (СТАРЫЙ) =====================


@router.get("/registrar/services")
def get_registrar_services(
    specialty: str | None = Query(None, description="Фильтр по специальности"),
    active_only: bool = Query(True, description="Только активные услуги"),
    db: Session = Depends(get_db),
    # Разрешаем доступ также профильным ролям врачей
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Doctor",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Получить услуги для регистратуры из справочника админ панели
    Из detail.md стр. 112: "Услуги (чек‑лист, группами — дерма/косметология/кардио/ЭКГ/ЭхоКГ/стоматология/лаборатория)"
    """
    try:
        # Получаем категории услуг
        categories = crud_clinic.get_service_categories(
            db, specialty=specialty, active_only=active_only
        )

        # Получаем услуги из основной таблицы
        query = db.query(Service)

        if active_only:
            query = query.filter(Service.active == True)

        services = query.all()

        # Получаем маппинг услуг к отделениям
        dept_services = (
            db.query(DepartmentService)
            .options(
                # joinedload(DepartmentService.department) # Если нужно
            )
            .all()
        )

        # Создаем словарь service_id -> department_key
        service_dept_map = {}
        for ds in dept_services:
            # Загружаем department если он не загружен (lazy load)
            if ds.department:
                service_dept_map[ds.service_id] = ds.department.key

        # Группируем услуги по категориям согласно документации
        grouped_services = {
            "laboratory": [],  # L - Лабораторные анализы
            "dermatology": [],  # D - Дерматологические услуги
            "cosmetology": [],  # C - Косметологические услуги
            "cardiology": [],  # K - Кардиология
            "stomatology": [],  # S - Стоматология
            "procedures": [],  # O - Прочие процедуры
        }

        # Простая логика распределения услуг по трём группам
        for service in services:
            service_data = {
                "id": service.id,
                "name": service.name,
                "code": service.code,
                "price": float(service.price) if service.price else 0,
                "currency": service.currency or "UZS",
                "duration_minutes": service.duration_minutes or 30,
                "category_id": service.category_id,
                "doctor_id": service.doctor_id,
                "department_key": service_dept_map.get(service.id)
                or getattr(
                    service, 'department_key', None
                ),  # [OK] Берем из маппинга или поля
                # [OK] НОВЫЕ ПОЛЯ ДЛЯ КЛАССИФИКАЦИИ
                "category_code": getattr(service, 'category_code', None),
                "service_code": getattr(service, 'service_code', None),
                "queue_tag": getattr(
                    service, 'queue_tag', None
                ),  # [TARGET] ДОБАВЛЯЕМ queue_tag ДЛЯ ЭКГ!
                "is_consultation": getattr(
                    service, 'is_consultation', False
                ),  # Добавляем поле is_consultation
                "group": None,  # Добавим группу для frontend
            }

            # [OK] НОВАЯ ЛОГИКА: определяем группу по category_code
            category_code = getattr(service, 'category_code', None)

            if category_code:
                # Используем новую систему кодов
                if category_code == 'L':
                    service_data["group"] = "laboratory"
                    grouped_services["laboratory"].append(service_data)
                elif category_code == 'D':
                    service_data["group"] = "dermatology"
                    grouped_services["dermatology"].append(service_data)
                elif category_code == 'C':
                    service_data["group"] = "procedures"
                    grouped_services["procedures"].append(service_data)
                elif category_code == 'K':
                    service_data["group"] = "cardiology"
                    grouped_services["cardiology"].append(service_data)
                elif category_code == 'S':
                    service_data["group"] = "stomatology"
                    grouped_services["stomatology"].append(service_data)
                elif category_code == 'O':
                    service_data["group"] = "procedures"
                    grouped_services["procedures"].append(service_data)
                else:
                    # Неизвестный код - в прочие
                    service_data["group"] = "procedures"
                    grouped_services["procedures"].append(service_data)
            else:
                # Fallback: если нет category_code, пытаемся определить по названию
                name_lower = service.name.lower()
                if any(
                    word in name_lower
                    for word in ["анализ", "кровь", "моча", "биохим", "гормон"]
                ):
                    service_data["group"] = "laboratory"
                    grouped_services["laboratory"].append(service_data)
                elif any(
                    word in name_lower
                    for word in ["дерматолог", "кожа", "псориаз", "акне"]
                ):
                    service_data["group"] = "dermatology"
                    grouped_services["dermatology"].append(service_data)
                elif any(
                    word in name_lower
                    for word in ["косметолог", "пилинг", "чистка", "ботокс"]
                ):
                    service_data["group"] = "procedures"
                    grouped_services["procedures"].append(service_data)
                elif any(
                    word in name_lower
                    for word in ["кардиолог", "экг", "эхокг", "холтер"]
                ):
                    service_data["group"] = "cardiology"
                    grouped_services["cardiology"].append(service_data)
                elif any(
                    word in name_lower for word in ["стоматолог", "зуб", "кариес"]
                ):
                    service_data["group"] = "stomatology"
                    grouped_services["stomatology"].append(service_data)
                else:
                    # По умолчанию в прочие процедуры
                    service_data["group"] = "procedures"
                    grouped_services["procedures"].append(service_data)

        return {
            "services_by_group": grouped_services,
            "categories": [
                {
                    "id": cat.id,
                    "code": cat.code,
                    "name_ru": cat.name_ru,
                    "name_uz": cat.name_uz,
                    "specialty": cat.specialty,
                }
                for cat in categories
            ],
            "total_services": len(services),
        }

    except (ValueError, AttributeError) as e:
        # Ошибки валидации или доступа к атрибутам
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка обработки данных услуг: {str(e)}",
        )
    except Exception as e:
        # Остальные ошибки (БД, сеть и т.д.)
        from sqlalchemy.exc import SQLAlchemyError

        if isinstance(e, SQLAlchemyError):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка базы данных при получении услуг: {str(e)}",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения услуг для регистратуры: {str(e)}",
        )


# ===================== ВРАЧИ И РАСПИСАНИЯ =====================


@router.get("/registrar/doctors")
def get_registrar_doctors(
    specialty: str | None = Query(None, description="Фильтр по специальности"),
    with_schedule: bool = Query(True, description="Включить расписание"),
    db: Session = Depends(get_db),
    # Разрешаем доступ также профильным ролям врачей
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Doctor",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Получить врачей с расписаниями для регистратуры
    Из detail.md стр. 106: "Специалист/Кабинет"
    """
    try:
        doctors = crud_clinic.get_doctors(db, active_only=True)

        if specialty:
            doctors = [d for d in doctors if d.specialty == specialty]

        result = []
        for doctor in doctors:
            doctor_data = {
                "id": doctor.id,
                "user_id": doctor.user_id,
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet,
                "price_default": (
                    float(doctor.price_default) if doctor.price_default else 0
                ),
                "start_number_online": doctor.start_number_online,
                "max_online_per_day": doctor.max_online_per_day,
                "user": (
                    {
                        "full_name": (
                            doctor.user.full_name
                            if doctor.user
                            else f"Врач #{doctor.id}"
                        ),
                        "username": doctor.user.username if doctor.user else None,
                    }
                    if doctor.user
                    else None
                ),
            }

            if with_schedule:
                schedules = crud_clinic.get_doctor_schedules(db, doctor.id)
                doctor_data["schedules"] = [
                    {
                        "id": schedule.id,
                        "weekday": schedule.weekday,
                        "start_time": (
                            schedule.start_time.strftime("%H:%M")
                            if schedule.start_time
                            else None
                        ),
                        "end_time": (
                            schedule.end_time.strftime("%H:%M")
                            if schedule.end_time
                            else None
                        ),
                        "breaks": schedule.breaks,
                        "active": schedule.active,
                    }
                    for schedule in schedules
                ]

            result.append(doctor_data)

        return {
            "doctors": result,
            "total_doctors": len(result),
            "by_specialty": {
                specialty: len([d for d in result if d["specialty"] == specialty])
                for specialty in {d["specialty"] for d in result}
            },
        }

    except (ValueError, AttributeError) as e:
        # Ошибки валидации или доступа к атрибутам
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка обработки данных врачей: {str(e)}",
        )
    except Exception as e:
        # Остальные ошибки (БД, сеть и т.д.)
        from sqlalchemy.exc import SQLAlchemyError

        if isinstance(e, SQLAlchemyError):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка базы данных при получении врачей: {str(e)}",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения врачей: {str(e)}",
        )


# ===================== НАСТРОЙКИ ОЧЕРЕДИ ДЛЯ РЕГИСТРАТУРЫ =====================


@router.get("/registrar/queue-settings")
def get_registrar_queue_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Получить настройки очереди для регистратуры
    Из detail.md стр. 303-338: конфигурации очереди
    """
    try:
        queue_settings = crud_clinic.get_queue_settings(db)

        # Дополняем информацией о врачах
        doctors = crud_clinic.get_doctors(db, active_only=True)

        specialty_info = {}
        for doctor in doctors:
            if doctor.specialty not in specialty_info:
                specialty_info[doctor.specialty] = {
                    "start_number": queue_settings.get("start_numbers", {}).get(
                        doctor.specialty, 1
                    ),
                    "max_per_day": queue_settings.get("max_per_day", {}).get(
                        doctor.specialty, 15
                    ),
                    "doctors": [],
                }

            specialty_info[doctor.specialty]["doctors"].append(
                {
                    "id": doctor.id,
                    "name": (
                        doctor.user.full_name if doctor.user else f"Врач #{doctor.id}"
                    ),
                    "cabinet": doctor.cabinet,
                }
            )

        return {
            "timezone": queue_settings.get("timezone", "Asia/Tashkent"),
            "queue_start_hour": queue_settings.get("queue_start_hour", 7),
            "auto_close_time": queue_settings.get("auto_close_time", "09:00"),
            "specialties": specialty_info,
            "current_time": datetime.utcnow().isoformat(),
        }

    except (ValueError, AttributeError) as e:
        # Ошибки валидации или доступа к атрибутам
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка обработки настроек очереди: {str(e)}",
        )
    except Exception as e:
        # Остальные ошибки (БД, сеть и т.д.)
        from sqlalchemy.exc import SQLAlchemyError

        if isinstance(e, SQLAlchemyError):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка базы данных при получении настроек очереди: {str(e)}",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения настроек очереди: {str(e)}",
        )


# ===================== СОЗДАНИЕ ЗАПИСИ В РЕГИСТРАТУРЕ =====================


@router.post("/registrar/appointments")
def create_registrar_appointment(
    appointment_data: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Создание записи через регистратуру
    Из detail.md стр. 366-376: POST /api/visits
    """
    try:
        # Валидируем обязательные поля
        required_fields = [
            "patient_id",
            "doctor_id",
            "date",
            "services",
            "type",
            "payment_type",
        ]
        for field in required_fields:
            if field not in appointment_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Обязательное поле '{field}' отсутствует",
                )

        # Получаем врача для проверки настроек
        doctor = crud_clinic.get_doctor_by_id(db, appointment_data["doctor_id"])
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Врач не найден"
            )

        # Получаем настройки очереди
        queue_settings = crud_clinic.get_queue_settings(db)

        # Создаем запись в очереди если это на сегодня
        appointment_date = datetime.strptime(
            appointment_data["date"], "%Y-%m-%d"
        ).date()

        if appointment_date == date.today():
            # Получаем или создаем дневную очередь
            daily_queue = (
                db.query(crud_queue.DailyQueue)
                .filter(
                    and_(
                        crud_queue.DailyQueue.day == appointment_date,
                        crud_queue.DailyQueue.specialist_id == doctor.id,
                    )
                )
                .first()
            )

            if not daily_queue:
                daily_queue = crud_queue.DailyQueue(
                    day=appointment_date, specialist_id=doctor.id, active=True
                )
                db.add(daily_queue)
                db.commit()
                db.refresh(daily_queue)

            # Вычисляем номер в очереди
            current_count = (
                db.query(crud_queue.QueueEntry)
                .filter(crud_queue.QueueEntry.queue_id == daily_queue.id)
                .count()
            )

            start_number = queue_settings.get("start_numbers", {}).get(
                doctor.specialty, 1
            )
            next_number = start_number + current_count

            # Создаем запись в очереди
            queue_entry = crud_queue.QueueEntry(
                queue_id=daily_queue.id,
                number=next_number,
                patient_id=appointment_data["patient_id"],
                source="desk",
                status="waiting",
            )
            db.add(queue_entry)

        # Здесь будет создание визита в основной таблице visits
        # Пока возвращаем успешный ответ

        db.commit()

        return {
            "success": True,
            "message": "Запись создана успешно",
            "appointment_id": f"temp_{datetime.utcnow().timestamp()}",
            "queue_number": next_number if appointment_date == date.today() else None,
            "print_ticket": appointment_date
            == date.today(),  # Печатать талон если на сегодня
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания записи: {str(e)}",
        )


# ===================== QR КОДЫ ДЛЯ РЕГИСТРАТУРЫ =====================


@router.post("/registrar/generate-qr")
def generate_qr_for_registrar(
    day: date = Query(..., description="Дата"),
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Генерация QR кода из регистратуры
    Из detail.md стр. 355: POST /api/online-queue/qrcode?day&specialist_id
    """
    try:
        token, token_data = queue_service.assign_queue_token(
            db,
            specialist_id=specialist_id,
            department=None,
            generated_by_user_id=current_user.id,
            target_date=day,
            is_clinic_wide=False,
        )

        # Формируем QR URL для пациентов
        qr_url = f"/pwa/queue?token={token}"

        return {
            "success": True,
            "token": token,
            "qr_url": qr_url,
            "qr_data": f"{qr_url}",  # Данные для QR кода
            "specialist": token_data["specialist_name"],
            "cabinet": token_data["cabinet"],
            "day": day.isoformat(),
            "max_slots": token_data["max_slots"],
            "current_count": token_data["current_count"],
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации QR: {str(e)}",
        )


# ===================== ОТКРЫТИЕ ПРИЕМА =====================


@router.post("/registrar/open-reception")
def open_reception(
    day: date = Query(..., description="Дата"),
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Открытие приема из регистратуры
    Из detail.md стр. 253: Кнопка «Открыть приём сейчас»
    """
    try:
        result = crud_queue.open_daily_queue(db, day, specialist_id, current_user.id)

        return {
            "success": True,
            "message": "Прием открыт, онлайн-набор закрыт",
            "opened_at": result["opened_at"],
            "online_entries_transferred": result["online_entries_count"],
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка открытия приема: {str(e)}",
        )


# ===================== УПРАВЛЕНИЕ ОЧЕРЕДЯМИ =====================


@router.post("/registrar/queue/{entry_id}/start-visit")
def start_queue_visit(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Doctor",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Начать прием для записи в очереди (статус в процессе)
    Работает с Visit и Appointment записями
    """
    try:
        from app.models.appointment import Appointment
        from app.models.visit import Visit

        # Сначала ищем в Visit
        visit = db.query(Visit).filter(Visit.id == entry_id).first()
        if visit:
            # Обновляем статус визита
            visit.status = "in_progress"

            # [OK] ИСПРАВЛЕНО: Сохраняем discount_mode и создаем платеж через SSOT
            # Не теряем информацию об оплате при обновлении статуса
            if not visit.discount_mode or visit.discount_mode == "none":
                from app.models.payment import Payment

                payment = (
                    db.query(Payment)
                    .filter(Payment.visit_id == visit.id)
                    .order_by(Payment.created_at.desc())
                    .first()
                )
                if payment and (
                    payment.status
                    and payment.status.lower() == 'paid'
                    or payment.paid_at
                ):
                    visit.discount_mode = "paid"
                elif visit.status in ("in_visit", "in_progress", "completed"):
                    # [OK] ИСПРАВЛЕНО: Если визит был начат (в кабинете) или завершён, вероятно был оплачен
                    # Создаем платеж через SSOT
                    from app.services.billing_service import BillingService

                    billing_service = BillingService(db)

                    # Проверяем, не создан ли уже платеж
                    if not payment:
                        # Рассчитываем сумму визита через SSOT
                        total_info = billing_service.calculate_total(
                            visit_id=visit.id,
                            discount_mode=visit.discount_mode or "none",
                        )
                        payment_amount = float(total_info["total"])

                        # Создаем платеж через SSOT
                        payment = billing_service.create_payment(
                            visit_id=visit.id,
                            amount=payment_amount,
                            currency=total_info.get("currency", "UZS"),
                            method="cash",  # Предполагаем наличные для визитов в процессе
                            status="paid",
                            note=f"Автоматическое создание платежа при начале приема (visit {visit.id})",
                        )
                        logger.info(
                            "start_queue_visit: Создан платеж ID=%d для визита %d, сумма=%s",
                            payment.id,
                            visit.id,
                            payment_amount,
                        )

                    visit.discount_mode = "paid"

            db.commit()
            db.refresh(visit)

            return {
                "success": True,
                "message": "Прием начат успешно",
                "entry": {
                    "id": visit.id,
                    "status": visit.status,
                    "patient_id": visit.patient_id,
                },
            }

        # Если не найден в Visit, ищем в Appointment
        appointment = db.query(Appointment).filter(Appointment.id == entry_id).first()
        if appointment:
            # Обновляем статус appointment
            appointment.status = "in_progress"

            # [OK] Сохраняем visit_type: если appointment был оплачен, сохраняем visit_type='paid'
            # Appointment не имеет discount_mode, используем visit_type
            if not appointment.visit_type or appointment.visit_type not in (
                "paid",
                "repeat",
                "benefit",
                "all_free",
            ):
                from app.models.payment import Payment

                payment = (
                    db.query(Payment)
                    .filter(Payment.visit_id == appointment.id)
                    .order_by(Payment.created_at.desc())
                    .first()
                )
                if payment and (
                    payment.status
                    and payment.status.lower() == 'paid'
                    or payment.paid_at
                ):
                    appointment.visit_type = "paid"
                elif (
                    hasattr(appointment, 'payment_amount')
                    and appointment.payment_amount
                    and appointment.payment_amount > 0
                ):
                    appointment.visit_type = "paid"
                elif appointment.status in (
                    "paid",
                    "in_visit",
                    "in_progress",
                    "completed",
                ):
                    appointment.visit_type = "paid"

            db.commit()
            db.refresh(appointment)

            return {
                "success": True,
                "message": "Прием начат успешно",
                "entry": {
                    "id": appointment.id,
                    "status": appointment.status,
                    "patient_id": appointment.patient_id,
                },
            }

        # Если не найден ни в Visit, ни в Appointment
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка начала приема: {str(e)}",
        )


# ===================== ТЕКУЩИЕ ОЧЕРЕДИ =====================


@router.get("/registrar/queues/today")
def get_today_queues(
    target_date: str | None = Query(
        None, description="Дата (YYYY-MM-DD), по умолчанию сегодня"
    ),
    department: str | None = Query(None, description="Фильтр по отделению"),
    db: Session = Depends(get_db),
    # [OK] ИСПРАВЛЕНО: Добавлена роль Cashier для доступа к очереди
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Cashier",
            "Doctor",
            "Lab",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
        )
    ),
):
    """
    Получить все очереди на указанную дату для регистратуры
    Из detail.md стр. 363: GET /api/queue/today?specialist_id&date=YYYY-MM-DD

    ОБНОВЛЕНО: Теперь получаем данные из Visit вместо DailyQueue
    Доступ: Admin, Registrar, Cashier, Doctor, Lab, cardio, cardiology, derma, dentist

    Параметры:
    - target_date: дата в формате YYYY-MM-DD (опционально, по умолчанию - сегодня)
    - department: фильтр по отделению (опционально)
    """
    try:
        from datetime import datetime

        from app.models.appointment import Appointment
        from app.models.clinic import Doctor
        from app.models.patient import Patient
        from app.models.visit import Visit

        # [OK] УПРОЩЕНО: Валидация формата даты перед парсингом (Single Source of Truth)
        # Если дата не указана, используем сегодня
        if target_date:
            # Проверяем формат даты перед парсингом (YYYY-MM-DD)
            import re

            date_pattern = r'^\d{4}-\d{2}-\d{2}$'
            if re.match(date_pattern, target_date):
                try:
                    today = datetime.strptime(target_date, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    # Если парсинг не удался (некорректная дата), используем сегодня
                    today = date.today()
            else:
                # Неправильный формат - используем сегодня
                today = date.today()
        else:
            today = date.today()

        # Получаем все визиты на сегодня (новая система)
        visits = db.query(Visit).filter(Visit.visit_date == today).all()

        # Получаем все appointments на сегодня (старая система)
        appointments = (
            db.query(Appointment).filter(Appointment.appointment_date == today).all()
        )

        # [OK] ДОБАВЛЕНО: Получаем записи из онлайн-очереди (OnlineQueueEntry)
        from app.models.online_queue import DailyQueue, OnlineQueueEntry

        online_entries = (
            db.query(OnlineQueueEntry)
            .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
            .filter(
                DailyQueue.day == today,
                # [OK] ИСПРАВЛЕНО: Добавлен статус "paid" чтобы оплаченные записи
                # отображались в списке регистратора (UI может фильтровать по статусу)
                OnlineQueueEntry.status.in_(["waiting", "called", "paid"]),
            )
            .order_by(OnlineQueueEntry.queue_time.asc(), OnlineQueueEntry.id.asc())  # ✅ EXPLICIT SORT: Oldest first
            .all()
        )

        # Группируем записи по специальности
        queues_by_specialty = {}
        seen_visit_ids = set()  # Для отслеживания уже обработанных Visit
        seen_appointment_ids = set()  # Для отслеживания уже обработанных Appointment
        seen_patient_specialty_date = (
            set()
        )  # Для отслеживания комбинации patient_id + specialty + date (предотвращение дубликатов)

        # Обрабатываем Visit (новая система)
        for visit in visits:
            # Пропускаем если уже обработан
            if visit.id in seen_visit_ids:
                continue
            # ⚠️ НЕ добавляем в seen_visit_ids здесь - сначала проверяем OQE

            # ⭐ PHASE 1.1: Пропускаем Visit если есть связанный OnlineQueueEntry
            # Очередь должна читаться ТОЛЬКО из OnlineQueueEntry (SSOT)
            from sqlalchemy import text
            has_queue_entry = db.execute(
                text("SELECT 1 FROM queue_entries WHERE visit_id = :visit_id LIMIT 1"),
                {"visit_id": visit.id}
            ).first()
            if has_queue_entry:
                # ⚠️ НЕ добавляем в seen_visit_ids - пусть OQE обрабатывается
                logger.debug(
                    "get_today_queues: PHASE 1.1 - Visit %d пропущен, есть OnlineQueueEntry",
                    visit.id,
                )
                continue

            # ✅ Только Visit БЕЗ OQE добавляем в seen_visit_ids
            seen_visit_ids.add(visit.id)

            # [OK] Определяем specialty на основе услуг визита, а не только department
            # Проверяем услуги визита для правильного определения очереди
            from app.models.service import Service
            from app.models.visit import VisitService

            visit_services = (
                db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            )
            service_ids = [vs.service_id for vs in visit_services]
            services = (
                db.query(Service).filter(Service.id.in_(service_ids)).all()
                if service_ids
                else []
            )

            # [OK] Проверяем, есть ли ЭКГ в услугах (по queue_tag, названию и коду)
            has_ecg = False
            ecg_services_count = 0
            non_ecg_services_count = 0

            logger.debug(
                "get_today_queues: Проверка ЭКГ для Visit %d, услуг: %d",
                visit.id,
                len(services),
            )
            for service in services:
                is_ecg_service = False
                service_name = service.name or 'N/A'
                # [OK] SSOT: Используем service_mapping.get_service_code() вместо дублирующей логики
                service_code_val = (
                    get_service_code(
                        {
                            'code': service.code,
                            'service_code': getattr(service, 'service_code', None),
                            'category_code': getattr(service, 'category_code', None),
                        }
                    )
                    or service.code
                    or 'N/A'
                )
                queue_tag_val = service.queue_tag or 'N/A'

                # Проверяем по queue_tag
                if service.queue_tag == 'ecg':
                    is_ecg_service = True
                    logger.debug(
                        "get_today_queues: ЭКГ найдено по queue_tag: %s (код: %s)",
                        service_name,
                        service_code_val,
                    )
                # Проверяем по названию услуги
                elif service.name:
                    service_name_lower = str(service.name).lower()
                    if 'экг' in service_name_lower or 'ecg' in service_name_lower:
                        is_ecg_service = True
                        logger.debug(
                            "get_today_queues: ЭКГ найдено по названию: %s (код: %s, queue_tag: %s)",
                            service_name,
                            service_code_val,
                            queue_tag_val,
                        )
                # Проверяем по коду услуги
                if not is_ecg_service:
                    if service.service_code:
                        service_code_upper = str(service.service_code).upper()
                        if 'ECG' in service_code_upper or 'ЭКГ' in service_code_upper:
                            is_ecg_service = True
                            logger.debug(
                                "get_today_queues: ЭКГ найдено по service_code: %s (код: %s)",
                                service_name,
                                service_code_val,
                            )
                    elif service.code:
                        service_code_upper = str(service.code).upper()
                        if 'ECG' in service_code_upper or 'ЭКГ' in service_code_upper:
                            is_ecg_service = True
                            logger.debug(
                                "get_today_queues: ЭКГ найдено по code: %s (код: %s)",
                                service_name,
                                service_code_val,
                            )

                if is_ecg_service:
                    has_ecg = True
                    ecg_services_count += 1
                else:
                    non_ecg_services_count += 1
                    logger.debug(
                        "get_today_queues: Не ЭКГ: %s (код: %s, queue_tag: %s)",
                        service_name,
                        service_code_val,
                        queue_tag_val,
                    )

            # Только ЭКГ: если есть ЭКГ услуги и нет не-ЭКГ услуг
            has_only_ecg = has_ecg and non_ecg_services_count == 0
            logger.debug(
                "get_today_queues: Итог для Visit %d: has_ecg=%s, has_only_ecg=%s, ЭКГ услуг=%d, не-ЭКГ услуг=%d",
                visit.id,
                has_ecg,
                has_only_ecg,
                ecg_services_count,
                non_ecg_services_count,
            )

            # [OK] Определяем specialty: если есть ЭКГ, разделяем на отдельные очереди
            visit_date = visit.visit_date or today
            patient_id = visit.patient_id

            if has_ecg and not has_only_ecg:
                # Визит содержит и ЭКГ и другие услуги - разделяем:
                # 1. Создаем запись для ЭКГ в очередь echokg (только ЭКГ услуги)
                specialty_ecg = "echokg"
                if specialty_ecg not in queues_by_specialty:
                    queues_by_specialty[specialty_ecg] = {
                        "entries": [],
                        "doctor": None,
                        "doctor_id": visit.doctor_id,
                    }

                # Проверяем дедупликацию для ЭКГ очереди
                patient_specialty_date_key_ecg = (
                    f"{patient_id}_{specialty_ecg}_{visit_date}"
                )
                if patient_specialty_date_key_ecg not in seen_patient_specialty_date:
                    visit_created_at = (
                        visit.confirmed_at or visit.created_at
                        if hasattr(visit, 'confirmed_at')
                        else visit.created_at
                    )

                    # ✅ ИСПРАВЛЕНО: Получаем queue_time из связанной записи в queue_entries
                    visit_queue_time = None
                    try:
                        from sqlalchemy import text

                        queue_entry_row = db.execute(
                            text(
                                "SELECT queue_time FROM queue_entries WHERE visit_id = :visit_id LIMIT 1"
                            ),
                            {"visit_id": visit.id},
                        ).first()
                        if queue_entry_row and queue_entry_row.queue_time:
                            visit_queue_time = queue_entry_row.queue_time
                    except Exception:
                        pass  # Тихая ошибка - используем created_at как fallback

                    queues_by_specialty[specialty_ecg]["entries"].append(
                        {
                            "type": "visit",
                            "data": visit,
                            "created_at": visit_created_at,
                            "queue_time": visit_queue_time,  # ✅ ИСПРАВЛЕНО: Добавляем queue_time для правильной сортировки
                            "filter_services": True,  # Флаг для фильтрации услуг при обработке
                            "ecg_only": True,  # Только ЭКГ услуги для этой записи
                        }
                    )
                    seen_patient_specialty_date.add(patient_specialty_date_key_ecg)

                # 2. Создаем запись для кардиолога в очередь cardiology (без ЭКГ услуг)
                specialty = "cardiology"
                patient_specialty_date_key = f"{patient_id}_{specialty}_{visit_date}"
                if patient_specialty_date_key not in seen_patient_specialty_date:
                    if specialty not in queues_by_specialty:
                        queues_by_specialty[specialty] = {
                            "entries": [],
                            "doctor": None,
                            "doctor_id": visit.doctor_id,
                        }
                    visit_created_at = (
                        visit.confirmed_at or visit.created_at
                        if hasattr(visit, 'confirmed_at')
                        else visit.created_at
                    )

                    # ✅ ИСПРАВЛЕНО: Получаем queue_time из связанной записи в queue_entries
                    visit_queue_time = None
                    try:
                        from sqlalchemy import text

                        queue_entry_row = db.execute(
                            text(
                                "SELECT queue_time FROM queue_entries WHERE visit_id = :visit_id LIMIT 1"
                            ),
                            {"visit_id": visit.id},
                        ).first()
                        if queue_entry_row and queue_entry_row.queue_time:
                            visit_queue_time = queue_entry_row.queue_time
                    except Exception:
                        pass  # Тихая ошибка - используем created_at как fallback

                    queues_by_specialty[specialty]["entries"].append(
                        {
                            "type": "visit",
                            "data": visit,
                            "created_at": visit_created_at,
                            "queue_time": visit_queue_time,  # ✅ ИСПРАВЛЕНО: Добавляем queue_time для правильной сортировки
                            "filter_services": True,  # Флаг для фильтрации услуг при обработке
                            "ecg_only": False,  # Исключаем ЭКГ услуги
                        }
                    )
                    seen_patient_specialty_date.add(patient_specialty_date_key)
                else:
                    logger.debug(
                        "get_today_queues: Пропущен Visit %d для cardiology - дубликат по ключу %s",
                        visit.id,
                        patient_specialty_date_key,
                    )
                continue  # Переходим к следующему визиту
            elif has_ecg and has_only_ecg:
                # Только ЭКГ - идёт в echokg
                specialty = "echokg"
                patient_specialty_date_key = f"{patient_id}_{specialty}_{visit_date}"
                if patient_specialty_date_key in seen_patient_specialty_date:
                    logger.debug(
                        "get_today_queues: Пропущен Visit %d - дубликат по ключу %s",
                        visit.id,
                        patient_specialty_date_key,
                    )
                    continue
                seen_patient_specialty_date.add(patient_specialty_date_key)

                if specialty not in queues_by_specialty:
                    queues_by_specialty[specialty] = {
                        "entries": [],
                        "doctor": None,
                        "doctor_id": visit.doctor_id,
                    }

                visit_created_at = (
                    visit.confirmed_at or visit.created_at
                    if hasattr(visit, 'confirmed_at')
                    else visit.created_at
                )

                # ✅ ИСПРАВЛЕНО: Получаем queue_time из связанной записи в queue_entries
                visit_queue_time = None
                try:
                    from sqlalchemy import text

                    queue_entry_row = db.execute(
                        text(
                            "SELECT queue_time FROM queue_entries WHERE visit_id = :visit_id LIMIT 1"
                        ),
                        {"visit_id": visit.id},
                    ).first()
                    if queue_entry_row and queue_entry_row.queue_time:
                        visit_queue_time = queue_entry_row.queue_time
                except Exception:
                    pass  # Тихая ошибка - используем created_at как fallback

                queues_by_specialty[specialty]["entries"].append(
                    {
                        "type": "visit",
                        "data": visit,
                        "created_at": visit_created_at,
                        "queue_time": visit_queue_time,  # ✅ ИСПРАВЛЕНО: Добавляем queue_time для правильной сортировки
                        "filter_services": True,  # [OK] ИСПРАВЛЕНО: Включаем фильтрацию услуг
                        "ecg_only": True,  # [OK] ИСПРАВЛЕНО: Показываем только ЭКГ услуги
                    }
                )
                continue  # Переходим к следующему визиту
            else:
                # [OK] ОБНОВЛЕНО: Определяем specialty по department_key из услуг визита
                # Приоритет: service.department_key > visit.department > "general"
                specialty = None

                # Проверяем department_key из услуг
                for service in services:
                    if service.department_key:
                        specialty = service.department_key
                        break

                # Fallback на visit.department
                if not specialty:
                    specialty = visit.department or "general"

            # Дедупликация для обычных визитов (без ЭКГ)
            patient_specialty_date_key = f"{patient_id}_{specialty}_{visit_date}"
            if patient_specialty_date_key in seen_patient_specialty_date:
                logger.debug(
                    "get_today_queues: Пропущен Visit %d - дубликат по ключу %s",
                    visit.id,
                    patient_specialty_date_key,
                )
                continue
            seen_patient_specialty_date.add(patient_specialty_date_key)

            if specialty not in queues_by_specialty:
                queues_by_specialty[specialty] = {
                    "entries": [],
                    "doctor": None,
                    "doctor_id": visit.doctor_id,
                }

            # Безопасно получаем дату создания
            # [OK] УПРОЩЕНО: Используем getattr вместо try/except (Single Source of Truth)
            visit_created_at = getattr(visit, 'confirmed_at', None) or getattr(
                visit, 'created_at', None
            )

            # ✅ ИСПРАВЛЕНО: Получаем queue_time из связанной записи в queue_entries
            visit_queue_time = None
            try:
                from sqlalchemy import text

                queue_entry_row = db.execute(
                    text(
                        "SELECT queue_time FROM queue_entries WHERE visit_id = :visit_id LIMIT 1"
                    ),
                    {"visit_id": visit.id},
                ).first()
                if queue_entry_row and queue_entry_row.queue_time:
                    visit_queue_time = queue_entry_row.queue_time
            except Exception:
                pass  # Тихая ошибка - используем created_at как fallback

            # ⭐ PHASE 1.2: Visit без OQE всегда type='visit'
            # Visit с source='online' уже пропущен выше (имеет OnlineQueueEntry)

            queues_by_specialty[specialty]["entries"].append(
                {
                    "type": "visit",  # ✅ PHASE 1.2: Всегда 'visit' для Visit без OQE
                    "data": visit,
                    "created_at": visit_created_at,
                    "queue_time": visit_queue_time,
                }
            )

            # [OK] УПРОЩЕНО: Используем getattr вместо try/except (Single Source of Truth)
            # ✅ ИСПРАВЛЕНО: Для visit записей обновляем doctor_id только если doctor ещё не установлен
            # Это предотвращает перезапись doctor_id, установленного online_queue записями
            if not queues_by_specialty[specialty]["doctor"]:
                visit_doctor = getattr(visit, 'doctor', None)
                if visit_doctor:
                    queues_by_specialty[specialty]["doctor"] = visit_doctor
                    # ✅ ИСПРАВЛЕНО: Обновляем doctor_id, если doctor найден
                    queues_by_specialty[specialty]["doctor_id"] = visit_doctor.id
            # ✅ ИСПРАВЛЕНО: Убрана логика обновления doctor_id для visit записей, если specialty уже существует
            # Это предотвращает перезапись doctor_id, установленного online_queue записями (которые обрабатываются позже)

        # [OK] ДОБАВЛЕНО: Обрабатываем записи из онлайн-очереди (OnlineQueueEntry)
        from app.models.online_queue import DailyQueue, OnlineQueueEntry

        for online_entry in online_entries:
            # ⭐ PHASE 1.1: OnlineQueueEntry теперь ЕДИНСТВЕННЫЙ источник очереди
            # Проверка seen_visit_ids нужна только для Visit БЕЗ OQE (редкий edge case)
            if online_entry.visit_id and online_entry.visit_id in seen_visit_ids:
                logger.debug(
                    "get_today_queues: PHASE 1.1 - OQE %d пропущен, Visit %d был обработан (без OQE - edge case)",
                    online_entry.id,
                    online_entry.visit_id,
                )
                continue

            # ⭐ ДОПОЛНИТЕЛЬНО: Пропускаем "сиротские" OnlineQueueEntry (без visit_id)
            # если для этого пациента уже есть Visit на сегодня
            # ✅ FIX 11: НО НЕ пропускаем QR-записи! Они должны показывать source='online'
            if not online_entry.visit_id and online_entry.patient_id:
                # ✅ FIX 11: QR-записи (source='online' или 'confirmation') НЕ пропускаем
                is_qr_entry = online_entry.source in ('online', 'confirmation')
                if is_qr_entry:
                    logger.debug(
                        "get_today_queues: OnlineQueueEntry %d - QR-запись (source=%s), НЕ пропускаем",
                        online_entry.id,
                        online_entry.source,
                    )
                else:
                    # Проверяем есть ли Visit для этого пациента на сегодня
                    patient_has_visit = any(
                        v.patient_id == online_entry.patient_id
                        for v in visits
                    )
                    if patient_has_visit:
                        logger.debug(
                            "get_today_queues: Пропуск OnlineQueueEntry %d - пациент %d уже имеет Visit на сегодня",
                            online_entry.id,
                            online_entry.patient_id,
                        )
                        continue

            daily_queue = (
                db.query(DailyQueue)
                .filter(DailyQueue.id == online_entry.queue_id)
                .first()
            )
            if not daily_queue:
                continue

            # ✅ ИСПРАВЛЕНО: daily_queue.specialist_id может хранить как doctor.id, так и user_id
            # Проверяем оба варианта для совместимости с существующими данными
            doctor = (
                db.query(Doctor).filter(Doctor.id == daily_queue.specialist_id).first()
            )
            # Если не нашли по doctor.id, пробуем по user_id (для совместимости со старыми данными)
            if not doctor:
                doctor = (
                    db.query(Doctor).filter(Doctor.user_id == daily_queue.specialist_id).first()
                )
            if not doctor:
                continue

            # [OK] ИСПРАВЛЕНО: Приоритет - queue_tag из DailyQueue, затем doctor.specialty
            # queue_tag - это точное указание очереди, созданное при регистрации
            specialty = None
            if daily_queue.queue_tag:
                specialty = daily_queue.queue_tag.lower()
            elif doctor.specialty:
                specialty = doctor.specialty.lower()
            elif doctor.department:
                specialty = doctor.department.lower()
            else:
                specialty = "general"

            # Маппинг specialty для соответствия с другими записями
            specialty_mapping = {
                "cardio": "cardiology",
                "cardiology": "cardiology",
                "derma": "dermatology",
                "dermatology": "dermatology",
                "dentist": "stomatology",
                "stomatology": "stomatology",
                "lab": "laboratory",
                "laboratory": "laboratory",
                "ecg": "echokg",  # [OK] ДОБАВЛЕНО: маппинг для ЭКГ
                "echokg": "echokg",
            }
            specialty = specialty_mapping.get(specialty, specialty)

            if specialty not in queues_by_specialty:
                queues_by_specialty[specialty] = {
                    "entries": [],
                    "doctor": doctor,
                    "doctor_id": doctor.id,  # ✅ ИСПРАВЛЕНО: Используем doctor.id вместо user_id
                }
            else:
                # ✅ ИСПРАВЛЕНО: Обновляем doctor_id и doctor, если specialty уже существует
                # Приоритет у online_queue записей (они обрабатываются после visit и отражают актуальное состояние)
                # Это важно, когда для одной специальности есть записи от разных врачей
                if doctor and doctor.id:
                    # ✅ ИСПРАВЛЕНО: Всегда обновляем doctor_id для online_queue записей
                    # Это гарантирует, что если есть QR-записи от врача 4, doctor_id будет 4
                    queues_by_specialty[specialty]["doctor"] = doctor
                    queues_by_specialty[specialty]["doctor_id"] = doctor.id

            # ✅ ИСПРАВЛЕНО: Добавляем queue_time для правильной сортировки
            # Приоритет: queue_time > created_at
            entry_time = (
                online_entry.queue_time
                if online_entry.queue_time
                else (
                    online_entry.created_at
                    if online_entry.created_at
                    else datetime.now()
                )
            )

            # Добавляем запись из онлайн-очереди
            queues_by_specialty[specialty]["entries"].append(
                {
                    "type": "online_queue",
                    "data": online_entry,
                    "created_at": (
                        online_entry.created_at
                        if online_entry.created_at
                        else datetime.now()
                    ),
                    "queue_time": entry_time,  # ⭐ ВАЖНО: queue_time для правильной сортировки
                }
            )

            logger.debug(
                "get_today_queues: QR-запись добавлена: ID=%d, specialty=%s, queue_tag=%s, number=%d, patient=%s",
                online_entry.id,
                specialty,
                daily_queue.queue_tag,
                online_entry.number,
                online_entry.patient_name,
            )

        # Обрабатываем Appointment (старая система)
        # Подгружаем актуальный статус оплаты из payments при наличии

        for appointment in appointments:
            # Пропускаем если уже обработан
            if appointment.id in seen_appointment_ids:
                continue
            seen_appointment_ids.add(appointment.id)

            # [OK] ОБНОВЛЕНО: Определяем специальность из appointment
            # Приоритет: services.department_key > appointment.department > "general"
            specialty = None
            appointment_date = getattr(appointment, 'appointment_date', today)
            patient_id = getattr(appointment, 'patient_id', None)

            # Проверяем department_key из услуг appointment
            if hasattr(appointment, 'services') and appointment.services:
                from app.models.service import Service

                for service_item in appointment.services:
                    service = None
                    if isinstance(service_item, dict):
                        service_id = service_item.get('id')
                        if service_id:
                            service = (
                                db.query(Service)
                                .filter(Service.id == service_id)
                                .first()
                            )
                    elif isinstance(service_item, int):
                        service = (
                            db.query(Service).filter(Service.id == service_item).first()
                        )
                    elif isinstance(service_item, str):
                        # [OK] ДОБАВЛЕНО: Поиск услуги по названию (Appointment.services - это JSON строк)
                        service = (
                            db.query(Service)
                            .filter(Service.name == service_item)
                            .first()
                        )

                    if service and service.department_key:
                        specialty = service.department_key
                        break

            # Fallback на appointment.department
            if not specialty:
                specialty = getattr(appointment, 'department', None) or "general"

            # Проверяем, нет ли уже Visit или Appointment для этого пациента в этой специальности на эту дату
            patient_specialty_date_key = f"{patient_id}_{specialty}_{appointment_date}"
            if patient_specialty_date_key in seen_patient_specialty_date:
                logger.debug(
                    "get_today_queues: Пропущен Appointment %d - дубликат по ключу %s",
                    appointment.id,
                    patient_specialty_date_key,
                )
                continue

            # [OK] УПРОЩЕНО: Проверяем, нет ли уже Visit для этого Appointment (чтобы избежать дубликатов)
            # Используем проверки вместо try/except (Single Source of Truth)
            visit_exists = False
            doctor_id = getattr(appointment, 'doctor_id', None)

            # Проверяем наличие обязательных данных перед запросом
            if patient_id and appointment_date:
                try:
                    # Строим фильтр для поиска соответствующего Visit
                    visit_filters = [
                        Visit.patient_id == patient_id,
                        Visit.visit_date == appointment_date,
                    ]

                    # doctor_id может быть None, поэтому добавляем его в фильтр только если он не None
                    if doctor_id is not None:
                        visit_filters.append(Visit.doctor_id == doctor_id)
                    else:
                        # Если doctor_id None, ищем Visit с doctor_id None
                        visit_filters.append(Visit.doctor_id.is_(None))

                    existing_visit = (
                        db.query(Visit).filter(and_(*visit_filters)).first()
                    )
                    if existing_visit:
                        visit_exists = True
                        logger.debug(
                            "get_today_queues: Пропущен Appointment %d - есть соответствующий Visit %d",
                            appointment.id,
                            existing_visit.id,
                        )
                except Exception as check_error:
                    # Если проверка не удалась, логируем и продолжаем - лучше показать дубликат, чем упасть с ошибкой
                    logger.warning(
                        "get_today_queues: Ошибка при проверке дубликатов для Appointment %s: %s",
                        getattr(appointment, 'id', 'unknown'),
                        check_error,
                        exc_info=True,
                    )
                    # Не прерываем выполнение - продолжаем обработку Appointment

            if visit_exists:
                continue

            # Отмечаем, что этот patient_id + specialty + date уже обработан
            seen_patient_specialty_date.add(patient_specialty_date_key)

            if specialty not in queues_by_specialty:
                queues_by_specialty[specialty] = {
                    "entries": [],
                    "doctor": None,
                    "doctor_id": getattr(appointment, 'doctor_id', None),
                }

            # ✅ ИСПРАВЛЕНО: Получаем queue_time из связанной записи в queue_entries
            appointment_queue_time = None
            try:
                from sqlalchemy import text

                if patient_id:
                    queue_entry_row = db.execute(
                        text(
                            "SELECT queue_time FROM queue_entries WHERE patient_id = :patient_id AND visit_id IS NULL ORDER BY created_at DESC LIMIT 1"
                        ),
                        {"patient_id": patient_id},
                    ).first()
                    if queue_entry_row and queue_entry_row.queue_time:
                        appointment_queue_time = queue_entry_row.queue_time
            except Exception:
                pass  # Тихая ошибка - используем created_at как fallback

            queues_by_specialty[specialty]["entries"].append(
                {
                    "type": "appointment",
                    "data": appointment,
                    "created_at": appointment.created_at,
                    "queue_time": appointment_queue_time,  # ✅ ИСПРАВЛЕНО: Добавляем queue_time для правильной сортировки
                }
            )

            # [OK] УПРОЩЕНО: Используем getattr вместо try/except (Single Source of Truth)
            if not queues_by_specialty[specialty]["doctor"]:
                appointment_doctor = getattr(appointment, 'doctor', None)
                if appointment_doctor:
                    queues_by_specialty[specialty]["doctor"] = appointment_doctor

        # Формируем результат
        result = []
        queue_number = 1

        for specialty, data in queues_by_specialty.items():
            doctor = data["doctor"]
            entries_list = data["entries"]

            # ✅ ИСПРАВЛЕНО: Сортируем записи по queue_time (приоритет), иначе по created_at
            # Это формирует правильную очередь: кто раньше зарегистрировался, тот раньше в очереди
            # queue_time - это бизнес-время регистрации, которое не меняется при редактировании
            try:

                def get_sort_key(e):
                    # Безопасно получаем значения
                    queue_time = e.get("queue_time")
                    created_at = e.get("created_at")

                    # Приоритет: queue_time, затем created_at, затем текущий момент
                    sort_time = None

                    # Обрабатываем queue_time
                    if queue_time:
                        if isinstance(queue_time, datetime):
                            sort_time = queue_time
                            # ✅ ИСПРАВЛЕНО Bug 3: Нормализуем naive datetime к timezone-aware UTC
                            if sort_time.tzinfo is None:

                                sort_time = sort_time.replace(tzinfo=UTC)
                        elif isinstance(queue_time, str):
                            try:
                                # Пробуем разные форматы дат
                                if 'T' in queue_time:
                                    sort_time = datetime.fromisoformat(
                                        queue_time.replace('Z', '+00:00')
                                    )
                                else:
                                    # ✅ ИСПРАВЛЕНО Bug 3: strptime возвращает naive datetime, нормализуем к UTC

                                    sort_time = datetime.strptime(
                                        queue_time, '%Y-%m-%d %H:%M:%S'
                                    ).replace(tzinfo=UTC)
                            except (ValueError, TypeError):
                                pass

                    # Если queue_time не сработал, пробуем created_at
                    if not sort_time and created_at:
                        if isinstance(created_at, datetime):
                            sort_time = created_at
                            # ✅ ИСПРАВЛЕНО Bug 3: Нормализуем naive datetime к timezone-aware UTC
                            if sort_time.tzinfo is None:

                                sort_time = sort_time.replace(tzinfo=UTC)
                        elif isinstance(created_at, str):
                            try:
                                if 'T' in created_at:
                                    sort_time = datetime.fromisoformat(
                                        created_at.replace('Z', '+00:00')
                                    )
                                else:
                                    # ✅ ИСПРАВЛЕНО Bug 3: strptime возвращает naive datetime, нормализуем к UTC

                                    sort_time = datetime.strptime(
                                        created_at, '%Y-%m-%d %H:%M:%S'
                                    ).replace(tzinfo=UTC)
                            except (ValueError, TypeError):
                                pass

                    # ✅ ИСПРАВЛЕНО Bug 3: Если ничего не сработало, используем timezone-aware UTC datetime
                    # Это предотвращает TypeError при сравнении timezone-aware и naive datetime
                    if not sort_time:

                        sort_time = datetime.now(UTC)

                    return sort_time

                entries_list.sort(key=get_sort_key)
            except Exception as sort_error:
                logger.warning(
                    f"Ошибка сортировки записей для {specialty}: {sort_error}"
                )
                # В случае ошибки сортировки оставляем записи как есть
                pass

            entries = []
            seen_entry_keys = set()  # Для дедупликации записей в одной специальности

            # ⭐ FIX: Улучшенная дедупликация для поддержки множественных записей одной сессии
            # Каждая новая услуга (добавленная через edit) создаёт отдельную OnlineQueueEntry.
            # Мы не должны их скрывать/объединять здесь, они должны быть видны как отдельные элементы
            # или сгруппированы корректно на frontend.
            # Поэтому в ключ добавляем ID записи, чтобы уникальные ID не склеивались.

            for idx, entry_wrapper in enumerate(entries_list, 1):
                # ⭐ FIX ROOT CAUSE: Strict SSOT - 1 Row = 1 OnlineQueueEntry
                # No aggregation here. We only deduplicate IDENTICAL record instances
                # that might appear due to SQL joins.

                entry_id = entry_wrapper.get('id')
                if entry_id:
                     unique_key = f"id_{entry_id}"
                else:
                     # Fallback only for legacy visit-based records without OQE
                     unique_key = f"visit_{entry_wrapper.get('visit_id')}_idx_{idx}"

                if unique_key in seen_entry_keys:
                    continue
                seen_entry_keys.add(unique_key)

                entry_type = entry_wrapper["type"]
                entry_data = entry_wrapper["data"]

                # Получаем базовые идентификаторы для дедупликации
                if entry_type == "visit":
                    entry_record_id = entry_data.id
                    entry_patient_id = entry_data.patient_id
                    entry_date = getattr(entry_data, 'visit_date', today)
                elif entry_type == "online_queue":
                    entry_record_id = entry_data.id
                    # ⚠️ ВАЖНО: для онлайн-очереди patient_id часто NULL (анонимный пациент).
                    # Если дедуплицировать только по patient_id, все такие записи сольются в одну
                    # в рамках specialty+date. Поэтому используем устойчивый идентификатор:
                    # patient_id → phone (нормализованный) → patient_name (нормализованный) → id.
                    # ✅ ИСПРАВЛЕНО: Синхронизировано с frontend логикой дедупликации
                    entry_patient_id = None
                    if entry_data.patient_id:
                        entry_patient_id = entry_data.patient_id
                    elif entry_data.phone:
                        # Нормализуем телефон (только цифры) для совместимости с frontend
                        # ✅ ИСПРАВЛЕНО: import re перемещен на уровень модуля
                        normalized_phone = re.sub(r'\D', '', str(entry_data.phone))
                        if normalized_phone:
                            entry_patient_id = normalized_phone
                    elif entry_data.patient_name:
                        # Нормализуем ФИО (trim + lowercase) для совместимости с frontend
                        normalized_name = str(entry_data.patient_name).strip().lower()
                        if normalized_name:
                            entry_patient_id = normalized_name
                    # ✅ ИСПРАВЛЕНО: Используем entry_data.id только если все остальные поля пустые
                    # Это гарантирует, что backend и frontend используют одинаковые ключи дедупликации
                    if not entry_patient_id:
                        entry_patient_id = entry_data.id
                    entry_date = today  # OnlineQueueEntry всегда на сегодня
                else:  # appointment
                    entry_record_id = entry_data.id
                    entry_patient_id = entry_data.patient_id
                    entry_date = getattr(entry_data, 'appointment_date', today)

                # ✅ ИСПРАВЛЕНО: Создаем уникальный ключ дедупликации
                # Для online_queue записей НЕ включаем specialty (как на frontend),
                # чтобы записи одного пациента к разным специалистам объединялись
                # Для других типов записей включаем specialty для разделения по отделениям
                if entry_type == "online_queue":
                    # ⭐ FIX: Включаем ID записи, чтобы разрешить несколько услуг (разные тикеты для одного пациента)
                    entry_key = f"{entry_patient_id}_{entry_date}_{entry_record_id}"
                else:
                    # Для visit/appointment: patient_id + specialty + date
                    entry_key = f"{entry_patient_id}_{specialty}_{entry_date}"

                # Пропускаем дубликаты
                if entry_key in seen_entry_keys:
                    logger.debug(
                        "get_today_queues: Пропущен дубликат: %s (тип: %s)",
                        entry_key,
                        entry_type,
                    )
                    continue

                seen_entry_keys.add(entry_key)

                # Инициализируем общие переменные
                patient_id = None
                patient_name = "Неизвестный пациент"
                phone = "Не указан"
                patient_birth_year = None
                address = None
                services = []
                service_codes = []
                service_details = []  # ✅ НОВОЕ: Полные данные услуг для редактирования
                total_cost = 0
                source = "desk"
                entry_status = "waiting"
                visit_time = None
                discount_mode = "none"
                record_id = None
                visit_department = (
                    None  # ✅ ДОБАВЛЕНО: для хранения department из Visit
                )

                if entry_type == "visit":
                    # Обработка Visit
                    visit = entry_data
                    record_id = visit.id
                    patient_id = visit.patient_id
                    visit_time = visit.visit_time
                    discount_mode = visit.discount_mode

                    # Загружаем пациента
                    patient = (
                        db.query(Patient).filter(Patient.id == visit.patient_id).first()
                    )
                    if patient:
                        # [OK] ИСПОЛЬЗУЕМ short_name() - теперь он всегда возвращает корректное значение
                        # Метод short_name() гарантирует, что всегда возвращается непустая строка
                        patient_name = patient.short_name()
                        phone = patient.phone or "Не указан"
                        if patient.birth_date:
                            patient_birth_year = patient.birth_date.year
                        address = patient.address
                    else:
                        # [OK] ЛОГИРОВАНИЕ: Пациент не найден
                        logger.warning(
                            "get_today_queues: Пациент не найден для Visit ID=%d, patient_id=%s",
                            visit.id,
                            visit.patient_id,
                        )
                        patient_name = (
                            f"Пациент ID={visit.patient_id}"
                            if visit.patient_id
                            else "Неизвестный пациент"
                        )

                    # Загружаем услуги визита
                    from app.models.visit import VisitService

                    all_visit_services = (
                        db.query(VisitService)
                        .filter(VisitService.visit_id == visit.id)
                        .all()
                    )

                    # [OK] Фильтруем услуги если есть флаг ecg_only или filter_services
                    ecg_only_flag = entry_wrapper.get("ecg_only", False)
                    filter_services_flag = entry_wrapper.get("filter_services", False)

                    visit_services = []
                    if filter_services_flag or ecg_only_flag:
                        # Фильтруем: показываем только ЭКГ услуги (для очереди echokg)
                        for vs in all_visit_services:
                            if hasattr(vs, 'service_id') and vs.service_id:
                                service = (
                                    db.query(Service)
                                    .filter(Service.id == vs.service_id)
                                    .first()
                                )
                                if service and service.queue_tag == 'ecg':
                                    visit_services.append(vs)
                        # Если нет ЭКГ услуг, не добавляем запись (это не должно произойти, но на всякий случай)
                        if not visit_services:
                            logger.warning(
                                "get_today_queues: Флаг ecg_only=True, но ЭКГ услуг не найдено для Visit %d",
                                visit.id,
                            )
                            continue  # Пропускаем эту запись, если нет ЭКГ услуг
                    else:
                        # Фильтруем: исключаем ЭКГ услуги (для очереди cardiology)
                        for vs in all_visit_services:
                            if hasattr(vs, 'service_id') and vs.service_id:
                                service = (
                                    db.query(Service)
                                    .filter(Service.id == vs.service_id)
                                    .first()
                                )
                                if service and service.queue_tag != 'ecg':
                                    visit_services.append(vs)
                        # Если не нашли не-ЭКГ услуг, значит это только ЭКГ визит - пропускаем для cardiology
                        if not visit_services:
                            logger.debug(
                                "get_today_queues: Пропущен Visit %d для specialty=%s: содержит только ЭКГ услуги",
                                visit.id,
                                specialty,
                            )
                            continue  # Пропускаем эту запись для кардиолога, если нет не-ЭКГ услуг

                    # Если нет отфильтрованных услуг, используем все (fallback)
                    if not visit_services:
                        visit_services = all_visit_services

                    for vs in visit_services:
                        # [OK] Используем service_code из справочника услуг для правильного формата (K01, D02, C03 и т.д.)
                        # [OK] SSOT: Используем service_mapping.get_service_code() вместо дублирующей логики
                        service_code_to_use = None
                        if hasattr(vs, 'service_id') and vs.service_id:
                            # Получаем полные данные услуги из БД
                            svc = (
                                db.query(Service)
                                .filter(Service.id == vs.service_id)
                                .first()
                            )
                            if svc:
                                service_code_to_use = get_service_code(
                                    {
                                        'code': svc.code,
                                        'service_code': getattr(
                                            svc, 'service_code', None
                                        ),
                                        'category_code': getattr(
                                            svc, 'category_code', None
                                        ),
                                    }
                                )

                        # Если не нашли через service_id, используем vs.code как fallback
                        if not service_code_to_use and vs.code:
                            service_code_to_use = vs.code

                        # Если всё ещё нет кода, используем название (нежелательно)
                        if service_code_to_use:
                            services.append(service_code_to_use)
                            service_codes.append(service_code_to_use)
                        elif vs.name:
                            services.append(vs.name)

                        # ✅ НОВОЕ: Собираем полные данные услуг для service_details
                        if svc:
                            service_details.append({
                                "id": svc.id,
                                "code": service_code_to_use or svc.code,
                                "name": svc.name,
                                "price": float(svc.price) if svc.price else 0
                            })

                        if vs.price:
                            total_cost += float(vs.price) * (vs.qty or 1)

                    # ✅ SSOT: Используем visit.source напрямую
                    # Больше никаких эвристик через confirmed_by!
                    source = getattr(visit, 'source', None) or 'desk'

                    # Определяем статус визита в терминах очереди
                    status_mapping = {
                        "confirmed": "waiting",
                        "pending_confirmation": "waiting",
                        "in_progress": "called",
                        "completed": "served",
                        "cancelled": "no_show",
                    }
                    entry_status = status_mapping.get(visit.status, "waiting")

                    # [OK] Используем единый сервис для определения оплаты (Single Source of Truth)
                    from app.services.billing_service import (
                        BillingService,
                        get_discount_mode_for_visit,
                    )

                    # Определяем статус оплаты через SSOT
                    billing_service = BillingService(db)
                    is_paid = billing_service.is_visit_paid(visit)

                    # Обновляем discount_mode в БД если визит оплачен
                    if is_paid:
                        billing_service.update_visit_discount_mode(visit)

                    # Получаем discount_mode для ответа API
                    discount_mode = get_discount_mode_for_visit(db, visit)

                    # ✅ ДОБАВЛЕНО: Сохраняем department из модели Visit для использования ниже
                    # Это нужно для новых записей из сценария 5
                    visit_department = getattr(visit, 'department', None)

                elif entry_type == "appointment":
                    # Обработка Appointment
                    appointment = entry_data
                    record_id = appointment.id
                    patient_id = appointment.patient_id
                    visit_time = (
                        str(appointment.appointment_time)
                        if hasattr(appointment, 'appointment_time')
                        else None
                    )

                    # Загружаем пациента
                    patient = (
                        db.query(Patient)
                        .filter(Patient.id == appointment.patient_id)
                        .first()
                    )
                    if patient:
                        # [OK] ИСПОЛЬЗУЕМ short_name() - теперь он всегда возвращает корректное значение
                        # Метод short_name() гарантирует, что всегда возвращается непустая строка
                        patient_name = patient.short_name()
                        phone = patient.phone or "Не указан"
                        if patient.birth_date:
                            patient_birth_year = patient.birth_date.year
                        address = patient.address
                    else:
                        # [OK] ЛОГИРОВАНИЕ: Пациент не найден
                        logger.warning(
                            "get_today_queues: Пациент не найден для Appointment ID=%d, patient_id=%s",
                            appointment.id,
                            appointment.patient_id,
                        )
                        patient_name = (
                            f"Пациент ID={appointment.patient_id}"
                            if appointment.patient_id
                            else "Неизвестный пациент"
                        )

                    # Загружаем услуги из appointment
                    if hasattr(appointment, 'services') and appointment.services:
                        if isinstance(appointment.services, list):
                            # [OK] Оставляем services как есть (уже должны быть коды), но дублируем в service_codes
                            services = appointment.services
                            # Если services содержит коды услуг (например, "ECG-001" или "C01"), добавляем их в service_codes
                            for service in services:
                                # Проверяем, является ли это кодом (формат "C01", "D02", "ECG-001" или просто код)
                                if isinstance(service, str):
                                    # Если это код (короткая строка, не похожая на полное название), добавляем в service_codes
                                    if (
                                        len(service) <= 10
                                        or '-' in service
                                        or service.isalnum()
                                    ):
                                        service_codes.append(service)
                                    # Если это полное название (длинное, с пробелами), не добавляем в service_codes
                                    # но это означает, что данные приходят в неправильном формате

                    # Стоимость
                    if (
                        hasattr(appointment, 'payment_amount')
                        and appointment.payment_amount
                    ):
                        total_cost = float(appointment.payment_amount)

                    # Определяем статус записи
                    status_mapping = {
                        "scheduled": "waiting",
                        "pending": "waiting",
                        "confirmed": "waiting",
                        "paid": "waiting",  # Оплачено, но еще в очереди
                        "in_progress": "called",
                        "in_visit": "called",
                        "completed": "served",
                        "cancelled": "no_show",
                    }
                    entry_status = status_mapping.get(appointment.status, "waiting")

                    # [OK] Используем единый сервис для определения оплаты (Single Source of Truth)
                    from app.services.billing_service import (
                        get_discount_mode_for_appointment,
                        is_appointment_paid,
                        update_appointment_payment_status,
                    )

                    # Определяем статус оплаты через единый сервис
                    is_paid = is_appointment_paid(db, appointment)

                    # Обновляем visit_type в БД если appointment оплачен
                    if is_paid:
                        update_appointment_payment_status(db, appointment)

                    # Получаем discount_mode для ответа API
                    discount_mode = get_discount_mode_for_appointment(db, appointment)

                    source = "desk"  # Appointment обычно создается регистратором

                elif entry_type == "online_queue":
                    # ✅ SSOT FIX: entry_data может быть OnlineQueueEntry или Visit (для QR-визитов)
                    is_visit_object = hasattr(entry_data, 'visit_date') and not hasattr(entry_data, 'queue_id')

                    if is_visit_object:
                        # entry_data это Visit с source='online'
                        visit = entry_data
                        # ✅ SSOT FIX: Для QR-визитов нужно получить данные из OnlineQueueEntry
                        # Frontend использует этот ID для вызова full-update endpoint
                        queue_entry_for_visit = db.execute(
                            text("SELECT id, number, queue_time, total_amount FROM queue_entries WHERE visit_id = :visit_id LIMIT 1"),
                            {"visit_id": visit.id}
                        ).first()
                        if queue_entry_for_visit:
                            record_id = queue_entry_for_visit.id
                            # ⭐ PHASE 1 FIX: Сохраняем данные из OQE для использования позже
                            entry_wrapper["oqe_number"] = queue_entry_for_visit.number
                            entry_wrapper["oqe_total_amount"] = queue_entry_for_visit.total_amount or 0
                            entry_wrapper["oqe_queue_time"] = queue_entry_for_visit.queue_time
                        else:
                            record_id = visit.id
                        # Также сохраняем visit_id для обратной совместимости
                        entry_wrapper["visit_id"] = visit.id
                        entry_wrapper["queue_entry_id"] = queue_entry_for_visit.id if queue_entry_for_visit else None
                        patient_id = visit.patient_id
                        entry_status = visit.status or "waiting"
                        source = visit.source or "online"  # SSOT: Visit.source
                        discount_mode = visit.discount_mode or "none"
                        visit_time = str(visit.visit_time) if hasattr(visit, 'visit_time') and visit.visit_time else None

                        # Загружаем пациента для получения данных
                        patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
                        if patient:
                            patient_name = patient.short_name()
                            phone = patient.phone or "Не указан"
                            patient_birth_year = patient.birth_date.year if patient.birth_date else None
                            address = patient.address
                        else:
                            patient_name = "Неизвестный пациент"
                            phone = "Не указан"
                            patient_birth_year = None
                            address = None
                    else:
                        # entry_data это OnlineQueueEntry (обычный случай)
                        online_entry = entry_data
                        record_id = online_entry.id
                        patient_id = online_entry.patient_id
                        patient_name = online_entry.patient_name or "Неизвестный пациент"
                        phone = online_entry.phone or "Не указан"
                        patient_birth_year = online_entry.birth_year
                        address = online_entry.address
                        entry_status = online_entry.status  # waiting, called, served, no_show
                        source = online_entry.source or "online"
                        discount_mode = online_entry.discount_mode or "none"
                        visit_time = None

                    # Получаем услуги - зависит от типа entry_data
                    if is_visit_object:
                        # Для Visit загружаем услуги из VisitService
                        from app.models.visit import VisitService
                        visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
                        for vs in visit_services:
                            svc = db.query(Service).filter(Service.id == vs.service_id).first()
                            if svc:
                                service_codes.append(svc.service_code or svc.code or "")
                                services.append({
                                    "service_id": svc.id,
                                    "name": svc.name,
                                    "code": svc.service_code or svc.code,
                                    "price": float(vs.price) if vs.price else 0,
                                    "quantity": vs.qty or 1
                                })
                    elif hasattr(entry_data, 'services') and entry_data.services:
                        online_entry = entry_data
                        if isinstance(online_entry.services, list):
                            services = online_entry.services
                            # Извлекаем коды услуг
                            for service in services:
                                if isinstance(service, dict):
                                    if service.get("code"):
                                        service_codes.append(service["code"])
                                    elif service.get("service_code"):
                                        service_codes.append(service["service_code"])
                                elif isinstance(service, str):
                                    service_codes.append(service)
                        elif isinstance(online_entry.services, str):
                            # Если это JSON строка, парсим
                            import json

                            try:
                                services = json.loads(online_entry.services)
                                if isinstance(services, list):
                                    for service in services:
                                        if isinstance(service, dict) and service.get(
                                            "code"
                                        ):
                                            service_codes.append(service["code"])
                            except Exception:
                                pass

                    # ✅ ИСПРАВЛЕНО: Определяем service_name для отображения в таблице и мастере
                    # Приоритет: 1. Имя из первой услуги 2. Fallback на специальность
                    service_name = None
                    if services and len(services) > 0:
                        first = services[0]
                        if isinstance(first, dict):
                            service_name = first.get("name") or first.get(
                                "service_name"
                            )
                        elif isinstance(first, str):
                            service_name = first

                    if not service_name:
                        # ✅ SSOT: Используем единственный источник истины для маппинга
                        from app.services.service_mapping import (
                            get_default_service_by_specialty,
                        )

                        default_service = get_default_service_by_specialty(db, specialty)
                        if default_service:
                            service_name = default_service["name"]
                            # ✅ ВАЖНО: Добавляем service_id для правильной работы визарда
                            entry_wrapper["service_id"] = default_service["id"]
                            entry_wrapper["service_code"] = default_service["service_code"]
                        else:
                            # Fallback если услуга не найдена в БД
                            service_name = f"Консультация ({specialty})"

                    entry_wrapper["service_name"] = service_name
                    # Добавляем также в data для надежности (frontend может читать из data)
                    if isinstance(entry_data, dict):
                         entry_data["service_name"] = service_name
                    elif hasattr(entry_data, "__dict__"):
                         try:
                             # Не можем менять объект модели SQLAlchemy, но можем попробовать
                             # setattr(entry_data, "service_name", service_name)
                             # Лучше не трогать модель, а полагаться на entry_wrapper
                             pass
                         except:
                             pass

                    # ⭐ PHASE 1 FIX: Проверяем service_codes из entry_data (не online_entry!)
                    if hasattr(entry_data, 'service_codes') and entry_data.service_codes:
                        if isinstance(entry_data.service_codes, list):
                            service_codes.extend(entry_data.service_codes)
                        elif isinstance(entry_data.service_codes, str):
                            import json

                            try:
                                parsed = json.loads(entry_data.service_codes)
                                if isinstance(parsed, list):
                                    service_codes.extend(parsed)
                            except:
                                pass

                    # ⭐ PHASE 1 FIX: total_cost - приоритет: oqe_total_amount, entry_data.total_amount, VisitService
                    total_cost = entry_wrapper.get("oqe_total_amount") or getattr(entry_data, 'total_amount', 0) or 0

                    # ⭐ PHASE 1 FIX: Для desk записей total_amount=0 — вычисляем из VisitService
                    if total_cost == 0:
                        linked_visit_id = getattr(entry_data, 'visit_id', None) or entry_wrapper.get("visit_id")
                        if linked_visit_id:
                            try:
                                cost_row = db.execute(
                                    text("SELECT SUM(price * qty) as total FROM visit_services WHERE visit_id = :vid"),
                                    {"vid": linked_visit_id}
                                ).first()
                                if cost_row and cost_row.total:
                                    total_cost = float(cost_row.total)
                            except Exception:
                                pass  # Fallback на 0

                    appointment_id_value = record_id

                    # ⭐ PHASE 1 FIX: Формируем service_details из entry_data.services (не online_entry!)
                    if hasattr(entry_data, 'services') and entry_data.services:
                        parsed_services = entry_data.services
                        if isinstance(parsed_services, str):
                            import json
                            try:
                                parsed_services = json.loads(parsed_services)
                            except:
                                parsed_services = []

                        if isinstance(parsed_services, list):
                            for svc in parsed_services:
                                if isinstance(svc, dict):
                                    service_details.append({
                                        "id": svc.get("id") or svc.get("service_id"),
                                        "code": svc.get("code") or svc.get("service_code"),
                                        "name": svc.get("name") or svc.get("service_name"),
                                        "price": float(svc.get("price", 0)) if svc.get("price") else 0
                                    })
                                elif isinstance(svc, str):
                                    # Если только название - добавляем как есть
                                    service_details.append({
                                        "id": None,
                                        "code": None,
                                        "name": svc,
                                        "price": 0
                                    })

                # [OK] УПРОЩЕНО: Добавляем appointment_id для Visit (если был создан соответствующий Appointment)
                # Используем проверки вместо try/except (Single Source of Truth)
                appointment_id_value = record_id
                if entry_type == "visit" and patient_id:
                    # Проверяем, есть ли Appointment для этого Visit
                    visit_date = getattr(entry_data, 'visit_date', None) or today
                    doctor_id = getattr(entry_data, 'doctor_id', None)

                    if visit_date and doctor_id:
                        existing_appointment = (
                            db.query(Appointment)
                            .filter(
                                and_(
                                    Appointment.patient_id == patient_id,
                                    Appointment.appointment_date == visit_date,
                                    Appointment.doctor_id == doctor_id,
                                )
                            )
                            .first()
                        )
                        if existing_appointment:
                            appointment_id_value = existing_appointment.id

                # ✅ ИСПРАВЛЕНО: Получаем РЕАЛЬНЫЙ номер и queue_time из queue_entries
                # Используем Table reflection вместо ORM модели для избежания конфликта DailyQueue
                queue_entry_number = idx  # По умолчанию используем idx
                queue_entry_time = None  # По умолчанию нет queue_time

                # Пробуем получить номер и queue_time из таблицы queue_entries через Table reflection
                if record_id:
                    try:
                        # Используем прямой SQL запрос через Table reflection (без импорта модели)
                        from sqlalchemy import text

                        # Используем прямой SQL для избежания конфликта с моделями
                        if entry_type == "online_queue":
                            # ✅ SSOT FIX: entry_data может быть Visit (для QR-записей) или OnlineQueueEntry
                            # Проверяем тип объекта
                            is_visit_object = hasattr(entry_data, 'visit_date') and not hasattr(entry_data, 'queue_id')

                            if is_visit_object:
                                # ⭐ PHASE 1 FIX: Используем уже полученные данные из entry_wrapper
                                queue_entry_number = entry_wrapper.get("oqe_number") or idx
                                queue_entry_time = entry_wrapper.get("oqe_queue_time")
                            else:
                                # ⭐ PHASE 1 FIX: Для OnlineQueueEntry номер и queue_time из entry_data
                                queue_entry_number = (
                                    entry_data.number
                                    if hasattr(entry_data, 'number') and entry_data.number is not None
                                    else idx
                                )
                                logger.debug(
                                    "PHASE1 DEBUG: entry_data.id=%s, entry_data.number=%s, queue_entry_number=%s, idx=%s",
                                    getattr(entry_data, 'id', 'N/A'),
                                    getattr(entry_data, 'number', 'N/A'),
                                    queue_entry_number,
                                    idx
                                )
                                queue_entry_time = (
                                    entry_data.queue_time
                                    if hasattr(entry_data, 'queue_time')
                                    and entry_data.queue_time
                                    else None
                                )
                            logger.debug(
                                "get_today_queues: OnlineQueue номер: ID=%d, number=%d, queue_time=%s, patient=%s",
                                record_id,
                                queue_entry_number,
                                queue_entry_time,
                                patient_name,
                            )
                        elif entry_type == "visit":
                            # Ищем запись по visit_id
                            queue_entry_row = db.execute(
                                text(
                                    "SELECT number, queue_time FROM queue_entries WHERE visit_id = :visit_id LIMIT 1"
                                ),
                                {"visit_id": record_id},
                            ).first()
                            if queue_entry_row:
                                queue_entry_number = queue_entry_row.number
                                queue_entry_time = queue_entry_row.queue_time
                        elif entry_type == "appointment" and patient_id:
                            # Для Appointment ищем по patient_id
                            queue_entry_row = db.execute(
                                text(
                                    "SELECT number, queue_time FROM queue_entries WHERE patient_id = :patient_id AND visit_id IS NULL ORDER BY created_at DESC LIMIT 1"
                                ),
                                {"patient_id": patient_id},
                            ).first()
                            if queue_entry_row:
                                queue_entry_number = queue_entry_row.number
                                queue_entry_time = queue_entry_row.queue_time
                    except Exception as e:
                        # Логируем ошибку, но продолжаем работу с дефолтным номером
                        # Это не критично - порядковые номера работают как fallback
                        logger.debug(
                            "get_today_queues: Ошибка получения queue_time: %s", str(e)
                        )
                        pass  # Тихая ошибка - порядковые номера достаточно

                # [OK] ДОБАВЛЯЕМ department_key и department для фронтенда
                entry_department_key = None
                entry_department = None
                if entry_type == "visit":
                    # Для Visit используем department, который был сохранен выше
                    entry_department = visit_department

                    # Для Visit получаем department_key из услуг
                    from app.models.visit import VisitService

                    visit_services_for_dept = (
                        db.query(VisitService)
                        .filter(VisitService.visit_id == record_id)
                        .all()
                    )
                    for vs in visit_services_for_dept:
                        if vs.service_id:
                            svc = (
                                db.query(Service)
                                .filter(Service.id == vs.service_id)
                                .first()
                            )
                            if svc and svc.department_key:
                                entry_department_key = svc.department_key
                                break
                elif entry_type == "appointment":
                    # Для Appointment получаем из услуг или напрямую
                    appointment_obj = entry_data
                    if (
                        hasattr(appointment_obj, 'services')
                        and appointment_obj.services
                    ):
                        for service_item in appointment_obj.services:
                            svc = None
                            if isinstance(service_item, dict):
                                service_id = service_item.get('id')
                                if service_id:
                                    svc = (
                                        db.query(Service)
                                        .filter(Service.id == service_id)
                                        .first()
                                    )
                            elif isinstance(service_item, int):
                                svc = (
                                    db.query(Service)
                                    .filter(Service.id == service_item)
                                    .first()
                                )
                            elif isinstance(service_item, str):
                                # [OK] ДОБАВЛЕНО: Поиск услуги по названию (Appointment.services - это JSON строк)
                                svc = (
                                    db.query(Service)
                                    .filter(Service.name == service_item)
                                    .first()
                                )

                            if svc and svc.department_key:
                                entry_department_key = svc.department_key
                                break

                # ✅ ИСПРАВЛЕНО: Определяем queue_time для ответа (приоритет: из queue_entries > из entry_wrapper > created_at)
                entry_queue_time = queue_entry_time
                if not entry_queue_time and entry_wrapper.get("queue_time"):
                    entry_queue_time = entry_wrapper["queue_time"]
                if not entry_queue_time:
                    entry_queue_time = entry_wrapper.get("created_at")

                # ✅ ИСПРАВЛЕНО: Правильная обработка queue_time (может быть datetime или строкой)
                queue_time_str = None
                if entry_queue_time:
                    if isinstance(entry_queue_time, datetime):
                        queue_time_str = entry_queue_time.isoformat() + "Z"
                    elif isinstance(entry_queue_time, str):
                        # Уже строка, используем как есть (может быть уже в ISO формате)
                        queue_time_str = (
                            entry_queue_time
                            if entry_queue_time.endswith("Z")
                            else entry_queue_time + "Z"
                        )
                    elif hasattr(entry_queue_time, 'isoformat'):
                        # Другой datetime-like объект
                        queue_time_str = entry_queue_time.isoformat() + "Z"

                entries.append(
                    {
                        "id": record_id,
                        "appointment_id": appointment_id_value,  # Явно добавляем appointment_id
                        "number": queue_entry_number,  # [OK] ИСПРАВЛЕНО: реальный номер из queue_entries
                        "patient_id": patient_id,
                        "patient_name": patient_name,
                        "patient_birth_year": patient_birth_year,
                        "phone": phone,
                        "address": address,
                        "services": services,
                        "service_codes": service_codes,
                        "service_details": service_details,  # ✅ НОВОЕ: Полные данные услуг для редактирования
                        "service_name": entry_wrapper.get("service_name"),  # ✅ НОВОЕ: Название услуги для отображения
                        "service_id": entry_wrapper.get("service_id"),  # ✅ SSOT: ID услуги из БД
                        "cost": total_cost,
                        "payment_status": (
                            "paid" if discount_mode == "paid" else "pending"
                        ),
                        "source": source,
                        "status": entry_status,
                        "created_at": (
                            entry_wrapper["created_at"].isoformat() + "Z"
                            if entry_wrapper["created_at"]
                            else None
                        ),  # [OK] Добавляем 'Z' для UTC
                        "queue_time": queue_time_str,  # ✅ ИСПРАВЛЕНО: Правильно обработанный queue_time
                        "called_at": None,
                        "visit_time": visit_time,
                        "discount_mode": discount_mode,
                        "type": entry_type,  # ✅ ИСПРАВЛЕНО: Добавляем type для frontend (online_queue, visit, appointment)
                        "record_type": entry_type,  # Добавляем тип записи: 'visit' или 'appointment' (для совместимости)
                        "queue_entry_id": entry_wrapper.get("queue_entry_id"),  # ✅ SSOT FIX: ID OnlineQueueEntry для QR-записей
                        "department_key": entry_department_key,  # [OK] ДОБАВЛЯЕМ department_key для динамических отделений
                        "department": entry_department,  # ✅ ДОБАВЛЕНО: department из модели Visit (для новых записей из сценария 5)
                        "session_id": getattr(entry_data, 'session_id', None),  # ⭐ NEW: Session grouping for frontend
                    }
                )

            queue_data = {
                "queue_id": queue_number,
                # ✅ ИСПРАВЛЕНО: specialist_id должен быть doctor.id для совместимости с frontend
                # Frontend передает doctor.id в URL параметре ?view=queue&doctor=X
                # Поэтому в ответе API specialist_id должен быть doctor.id, а не user_id
                "specialist_id": data["doctor_id"],  # Это уже doctor.id из queues_by_specialty
                "specialist_name": (
                    doctor.user.full_name if doctor and doctor.user else "Врач"
                ),
                "specialty": specialty,
                "cabinet": doctor.cabinet if doctor else "N/A",
                "opened_at": datetime.now().isoformat(),
                "entries": entries,
                "stats": {
                    "total": len(entries),
                    "waiting": len([e for e in entries if e["status"] == "waiting"]),
                    "called": len([e for e in entries if e["status"] == "called"]),
                    "served": len([e for e in entries if e["status"] == "served"]),
                    "online_entries": len(
                        [e for e in entries if e["source"] == "online"]
                    ),
                },
            }

            result.append(queue_data)
            queue_number += 1

        return {
            "queues": result,
            "total_queues": len(result),
            "date": today.isoformat(),
        }

    except Exception as e:
        logger.error(
            "get_today_queues: КРИТИЧЕСКАЯ ОШИБКА: %s: %s",
            type(e).__name__,
            e,
            exc_info=True,
        )
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения очередей: {str(e)}",
        )


# ===================== КАЛЕНДАРЬ ЗАПИСЕЙ =====================


@router.get("/registrar/calendar")
def get_registrar_calendar(
    start_date: date = Query(..., description="Начальная дата"),
    end_date: date = Query(..., description="Конечная дата"),
    doctor_id: int | None = Query(None, description="Фильтр по врачу"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Календарь записей для регистратуры
    Из detail.md стр. 174-181: календарь с цветовыми статусами
    """
    try:
        # Здесь будет логика получения записей из таблицы appointments/visits
        # Пока возвращаем заглушку

        return {
            "appointments": [],
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "status_colors": {
                "plan": "#6c757d",  # серый — план
                "confirmed": "#007bff",  # синий — подтверждено
                "queued": "#28a745",  # зеленый — в очереди
                "in_cabinet": "#fd7e14",  # оранжевый — в кабинете
                "done": "#20c997",  # зеленый тёмный — завершён
                "cancelled": "#dc3545",  # красный — отменен
                "no_show": "#dc3545",  # красный — неявка
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения календаря: {str(e)}",
        )


# ===================== МАССОВОЕ СОЗДАНИЕ ОЧЕРЕДЕЙ =====================


# Pydantic schemas для batch endpoint
class BatchServiceItem(BaseModel):
    """Услуга для массового создания очередей"""

    specialist_id: int = Field(
        ..., description="ID специалиста (user_id, не doctor_id)"
    )
    service_id: int = Field(..., description="ID услуги")
    quantity: int = Field(default=1, ge=1, description="Количество")

    # ⚠️ ВАЖНО: specialist_id должен быть user_id (ForeignKey на users.id), а не doctor_id!
    # Если передается doctor_id, нужно конвертировать его в user_id на backend


class BatchQueueEntriesRequest(BaseModel):
    """Запрос на массовое создание записей в очереди"""

    patient_id: int = Field(..., description="ID пациента")
    source: Literal["online", "desk", "morning_assignment"] = Field(
        ..., description="Источник регистрации: 'online', 'desk', 'morning_assignment'"
    )
    services: list[BatchServiceItem] = Field(
        ..., min_length=1, description="Список услуг с указанием специалистов"
    )


class BatchQueueEntryResponse(BaseModel):
    """Ответ с информацией о созданной записи в очереди"""

    specialist_id: int
    queue_id: int
    number: int
    queue_time: str


class BatchQueueEntriesResponse(BaseModel):
    """Ответ на массовое создание очередей"""

    success: bool
    entries: list[BatchQueueEntryResponse]
    message: str


@router.post(
    "/registrar-integration/queue/entries/batch",
    response_model=BatchQueueEntriesResponse,
)
def create_queue_entries_batch(
    request: BatchQueueEntriesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Массовое создание записей в очереди (при добавлении новых услуг)

    Endpoint: POST /api/v1/registrar-integration/queue/entries/batch
    Из ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md стр. 271-306

    Use case: Регистратор редактирует существующую запись пациента и добавляет новые услуги.
    Для каждой новой услуги создается запись в соответствующей очереди специалиста.

    ВАЖНО:
    - Сохраняет оригинальный source из запроса (не меняет на "desk")
    - Устанавливает queue_time = текущее время (справедливое присвоение номера)
    - Проверяет дубликаты (пациент уже в очереди к специалисту на сегодня)
    - Использует SSOT queue_service.py для создания записей

    Требуемые роли: Admin, Registrar
    """
    service = QueueBatchService(db)
    service_items = [
        QueueBatchServiceItem(
            specialist_id=item.specialist_id,
            service_id=item.service_id,
            quantity=item.quantity,
        )
        for item in request.services
    ]

    try:
        result = service.create_entries(
            patient_id=request.patient_id,
            source=request.source,
            services=service_items,
        )
        return BatchQueueEntriesResponse(
            success=result.success,
            entries=[
                BatchQueueEntryResponse(
                    specialist_id=entry.specialist_id,
                    queue_id=entry.queue_id,
                    number=entry.number,
                    queue_time=entry.queue_time,
                )
                for entry in result.entries
            ],
            message=result.message,
        )
    except QueueBatchDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


# ===================== КОНВЕРТАЦИЯ DOCTOR_ID → USER_ID =====================


@router.get("/registrar-integration/doctors/{doctor_id}/user-id")
def get_doctor_user_id(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Получить user_id по doctor_id

    Используется для конвертации doctor_id в user_id при создании записей в очереди,
    так как DailyQueue.specialist_id требует user_id, а не doctor_id.

    Args:
        doctor_id: ID врача из таблицы doctors

    Returns:
        user_id: ID пользователя из таблицы users

    Raises:
        HTTPException 404: Если врач не найден или у врача нет user_id
    """
    try:
        from app.models.clinic import Doctor

        doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач с ID {doctor_id} не найден",
            )

        if not doctor.user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"У врача с ID {doctor_id} не установлен user_id",
            )

        return {
            "doctor_id": doctor_id,
            "user_id": doctor.user_id,
            "doctor_name": doctor.user.full_name if doctor.user else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения user_id для doctor_id={doctor_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения user_id: {str(e)}",
        )
