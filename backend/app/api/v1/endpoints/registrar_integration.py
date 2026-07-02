"""
API endpoints для интеграции регистратуры с админ панелью
Основа: detail.md стр. 85-183
"""

import logging
import re  # ✅ ДОБАВЛЕНО: для нормализации телефонов в дедупликации
import traceback
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import clinic as crud_clinic, online_queue as crud_queue
from app.models.department import Department, DepartmentService
from app.models.service import Service
from app.models.user import User
from app.services.canonical_visit_service import (
    CanonicalVisitResolutionError,
    CanonicalVisitService,
)
from app.services.queue_service import queue_service
from app.services.service_mapping import get_service_code, resolve_queue_group_key

# [OK] Используем прямой SQL вместо импорта модели для избежания конфликта DailyQueue
# Проблема: DailyQueue определен в двух местах (queue_old.py и online_queue.py)
# Решение: используем прямой SQL запрос через text() для доступа к queue_entries без импорта модели

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_queue_status_for_registrar(raw_status: str | None) -> str:
    """Keep payment state out of the operational queue status shown to registrars."""
    if not raw_status or raw_status == "paid":
        return "waiting"
    return raw_status


REGISTRAR_PAYMENT_ROLES = {"admin", "registrar", "cashier"}
REGISTRAR_DOCTOR_ACTION_ROLES = {
    "doctor",
    "cardio",
    "cardiology",
    "cardiologist",
    "derma",
    "dermatologist",
    "dentist",
    "lab",
}
REGISTRAR_START_VISIT_ROLES = REGISTRAR_DOCTOR_ACTION_ROLES
REGISTRAR_PRINT_TICKET_ROLES = {"admin", "registrar", "cashier", "doctor"}
REGISTRAR_COMPLETE_ROLES = REGISTRAR_DOCTOR_ACTION_ROLES
REGISTRAR_CANCEL_ROLES = {"admin", "registrar", "cashier", "receptionist", "doctor"}
REGISTRAR_DOCTOR_SECONDARY_ACTION_ROLES = REGISTRAR_DOCTOR_ACTION_ROLES
REGISTRAR_START_STATUSES = {"waiting", "queued"}
REGISTRAR_PRINT_STATUSES = {"waiting", "queued"}
REGISTRAR_COMPLETE_STATUSES = {"called", "in_cabinet", "in_progress"}
REGISTRAR_CANCEL_BLOCKED_STATUSES = {"canceled", "cancelled", "completed", "done", "served"}
REGISTRAR_HIDDEN_QUEUE_STATUSES = {"canceled", "cancelled", "no_show"}
REGISTRAR_VIEW_EMR_STATUSES = {"completed", "done", "served"}
REGISTRAR_SCHEDULE_NEXT_STATUSES = {"completed", "done", "served"}


def _registrar_user_role_names(user: User | None) -> set[str]:
    role_names: set[str] = set()
    primary_role = getattr(user, "role", None)
    if primary_role:
        role_names.add(str(primary_role).strip().lower())

    for role in getattr(user, "roles", None) or []:
        role_name = getattr(role, "name", None)
        if role_name:
            role_names.add(str(role_name).strip().lower())

    return role_names


def _registrar_can_mark_paid(user: User | None, payment_status: str | None) -> bool:
    if str(payment_status or "").strip().lower() == "paid":
        return False
    return bool(_registrar_user_role_names(user) & REGISTRAR_PAYMENT_ROLES)


def _registrar_can_start_visit(user: User | None, queue_status: str | None) -> bool:
    normalized_status = str(queue_status or "").strip().lower()
    return (
        normalized_status in REGISTRAR_START_STATUSES
        and bool(_registrar_user_role_names(user) & REGISTRAR_START_VISIT_ROLES)
    )


def _registrar_can_print_ticket(
    user: User | None,
    *,
    payment_status: str | None,
    queue_status: str | None,
) -> bool:
    normalized_payment_status = str(payment_status or "").strip().lower()
    normalized_queue_status = str(queue_status or "").strip().lower()
    return (
        (
            normalized_payment_status == "paid"
            or normalized_queue_status in REGISTRAR_PRINT_STATUSES
        )
        and bool(_registrar_user_role_names(user) & REGISTRAR_PRINT_TICKET_ROLES)
    )


def _registrar_can_complete(user: User | None, queue_status: str | None) -> bool:
    normalized_status = str(queue_status or "").strip().lower()
    return (
        normalized_status in REGISTRAR_COMPLETE_STATUSES
        and bool(_registrar_user_role_names(user) & REGISTRAR_COMPLETE_ROLES)
    )


def _registrar_can_cancel(user: User | None, queue_status: str | None) -> bool:
    normalized_status = str(queue_status or "").strip().lower()
    return (
        normalized_status not in REGISTRAR_CANCEL_BLOCKED_STATUSES
        and bool(_registrar_user_role_names(user) & REGISTRAR_CANCEL_ROLES)
    )


def _registrar_can_view_emr(
    user: User | None,
    *,
    payment_status: str | None,
    queue_status: str | None,
    visit_id: int | None,
) -> bool:
    normalized_status = str(queue_status or "").strip().lower()
    normalized_payment_status = str(payment_status or "").strip().lower()
    status_allows_view = (
        normalized_status in REGISTRAR_VIEW_EMR_STATUSES
        or (normalized_status == "in_visit" and normalized_payment_status == "paid")
    )
    return (
        visit_id is not None
        and status_allows_view
        and bool(
            _registrar_user_role_names(user)
            & REGISTRAR_DOCTOR_SECONDARY_ACTION_ROLES
        )
    )


def _registrar_can_schedule_next(
    user: User | None,
    *,
    queue_status: str | None,
    patient_id: int | None,
) -> bool:
    normalized_status = str(queue_status or "").strip().lower()
    return (
        patient_id is not None
        and normalized_status in REGISTRAR_SCHEDULE_NEXT_STATUSES
        and bool(
            _registrar_user_role_names(user)
            & REGISTRAR_DOCTOR_SECONDARY_ACTION_ROLES
        )
    )


def _registrar_available_actions(
    *,
    user: User | None,
    payment_status: str | None,
    queue_status: str | None,
    visit_id: int | None = None,
    patient_id: int | None = None,
) -> list[str]:
    actions: list[str] = []
    if _registrar_can_mark_paid(user, payment_status):
        actions.append("mark_paid")
    if _registrar_can_start_visit(user, queue_status):
        actions.append("start_visit")
    if _registrar_can_print_ticket(
        user,
        payment_status=payment_status,
        queue_status=queue_status,
    ):
        actions.append("print_ticket")
    if _registrar_can_complete(user, queue_status):
        actions.append("complete")
    if _registrar_can_cancel(user, queue_status):
        actions.append("cancel")
    if _registrar_can_view_emr(
        user,
        payment_status=payment_status,
        queue_status=queue_status,
        visit_id=visit_id,
    ):
        actions.append("view_emr")
    if _registrar_can_schedule_next(
        user,
        queue_status=queue_status,
        patient_id=patient_id,
    ):
        actions.append("schedule_next")
    return actions


REGISTRATION_DISCOUNT_MODES = {"none", "repeat", "benefit", "all_free"}


def _normalize_registration_discount_mode(raw_value: str | None) -> str:
    """Registrar payloads expose registration type only, never payment markers."""
    normalized = str(raw_value or "none").strip().lower()
    if normalized in REGISTRATION_DISCOUNT_MODES:
        return normalized
    return "none"


def _serialize_registrar_datetime(value: Any) -> str | None:
    """Serialize registrar timestamps without corrupting timezone semantics."""
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            return normalized
        if "T" in normalized:
            try:
                parsed = datetime.fromisoformat(normalized)
                return parsed.isoformat()
            except ValueError:
                return normalized
        return normalized

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return None

    return str(value)


def _is_newer_lab_report_instance(candidate: Any, current: Any | None) -> bool:
    if current is None:
        return True

    def sort_key(instance: Any) -> tuple[float, int]:
        created_at = getattr(instance, "created_at", None)
        if isinstance(created_at, datetime):
            timestamp = created_at.timestamp()
        else:
            timestamp = 0.0
        return (timestamp, getattr(instance, "id", 0) or 0)

    return sort_key(candidate) > sort_key(current)


def _lab_report_summary_for_registrar(service: Any, instance: Any) -> dict[str, Any]:
    sections = service.materialize_instance(instance)
    severity = service.summarize_instance_severity(sections)
    available_actions = service.instance_available_actions(instance)
    template = getattr(instance, "template", None)
    return {
        "id": instance.id,
        "status": instance.status,
        "template_id": instance.template_id,
        "template_version_id": instance.template_version_id,
        "template_name": getattr(template, "name", None),
        "created_at": _serialize_registrar_datetime(instance.created_at),
        "finalized_at": _serialize_registrar_datetime(instance.finalized_at),
        "printed_at": _serialize_registrar_datetime(instance.printed_at),
        "flagged_findings_count": severity["flagged_findings_count"],
        "critical_findings_count": severity["critical_findings_count"],
        "max_flag_severity": severity["max_flag_severity"],
        "available_actions": available_actions,
        **service.instance_action_flags(instance),
    }


def _latest_lab_report_summaries_by_visit(
    db: Session,
    visit_ids: set[int],
) -> dict[int, dict[str, Any]]:
    if not visit_ids:
        return {}

    from app.services.lab_reporting_service import LabReportingService

    service = LabReportingService(db)
    instances = service.list_instances(
        patient_id=None,
        visit_ids=sorted(visit_ids),
        status=None,
        limit=max(len(visit_ids) * 20, 500),
        offset=0,
    )
    latest_by_visit: dict[int, Any] = {}
    for instance in instances:
        visit_id = getattr(instance, "visit_id", None)
        if not visit_id:
            continue
        if _is_newer_lab_report_instance(instance, latest_by_visit.get(visit_id)):
            latest_by_visit[visit_id] = instance

    return {
        visit_id: _lab_report_summary_for_registrar(service, instance)
        for visit_id, instance in latest_by_visit.items()
    }


def _resolve_payment_truth(
    db: Session,
    *,
    visit_id: int | None = None,
    legacy_paid_at: datetime | None = None,
) -> tuple[str, str | None]:
    """Resolve payment status/method from payments, with a narrow legacy fallback."""
    if visit_id:
        try:
            from app.models.payment import Payment

            payment = (
                db.query(Payment)
                .filter(Payment.visit_id == visit_id)
                .order_by(Payment.created_at.desc())
                .first()
            )
            if payment:
                status = (
                    "paid"
                    if (
                        str(getattr(payment, "status", "") or "").lower() == "paid"
                        or getattr(payment, "paid_at", None)
                    )
                    else "pending"
                )
                method = getattr(payment, "method", None) or None
                return status, method
        except Exception:
            logger.debug(
                "registrar_integration: failed to resolve payment truth for visit",
                exc_info=True,
            )

    return ("paid", None) if legacy_paid_at else ("pending", None)


def _raise_registrar_internal_error(action: str, exc: Exception) -> None:
    if isinstance(exc, HTTPException):
        raise exc

    logger.exception(
        "registrar_integration: unexpected error during %s (%s)",
        action,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )

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
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
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
        from app.models.queue_profile import QueueProfile, INITIAL_QUEUE_PROFILES
        
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
        logger.error("Error fetching queue profiles", exc_info=True)
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
        from app.models.queue_profile import QueueProfile, INITIAL_QUEUE_PROFILES
        
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
        logger.error("Error fetching queue profiles for QR page", exc_info=True)
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


from pydantic import BaseModel, Field
from typing import List


class QueueProfileCreate(BaseModel):
    """Schema for creating a new QueueProfile"""
    key: str = Field(..., min_length=1, max_length=50, description="Unique key (e.g., 'cardiology')")
    title: str = Field(..., min_length=1, max_length=100, description="English title")
    title_ru: Optional[str] = Field(None, max_length=100, description="Russian title")
    queue_tags: List[str] = Field(default=[], description="List of queue_tag values for this profile")
    department_key: Optional[str] = Field(None, max_length=50)
    display_order: int = Field(default=0, ge=0)
    is_active: bool = Field(default=True)
    show_on_qr_page: bool = Field(default=True, description="Show this profile on QR join page")
    icon: Optional[str] = Field(None, max_length=50, description="Lucide icon name (e.g., 'Heart')")
    color: Optional[str] = Field(None, max_length=20, description="Hex color (e.g., '#E53E3E')")


class QueueProfileUpdate(BaseModel):
    """Schema for updating an existing QueueProfile"""
    title: Optional[str] = Field(None, max_length=100)
    title_ru: Optional[str] = Field(None, max_length=100)
    queue_tags: Optional[List[str]] = None
    department_key: Optional[str] = Field(None, max_length=50)
    display_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    show_on_qr_page: Optional[bool] = Field(None, description="Show this profile on QR join page")
    icon: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=20)


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
        _raise_registrar_internal_error("create queue profile", e)


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
        _raise_registrar_internal_error("update queue profile", e)


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
        _raise_registrar_internal_error("delete queue profile", e)


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
        _raise_registrar_internal_error("reorder queue profiles", e)


# ===================== СПРАВОЧНИК УСЛУГ (СТАРЫЙ) =====================


@router.get("/registrar/services")
def get_registrar_services(
    specialty: Optional[str] = Query(None, description="Фильтр по специальности"),
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
        queue_group_to_registrar_group = {
            "cardiology": "cardiology",
            "ecg": "cardiology",
            "dermatology": "dermatology",
            "dental": "stomatology",
            "laboratory": "laboratory",
            "procedures": "procedures",
        }

        # Простая логика распределения услуг по трём группам
        for service in services:
            service_data = {
                "id": service.id,
                "name": service.name,
                "code": service.service_code or get_service_code(service.id, db),
                "price": float(service.price) if service.price else 0,
                "currency": service.currency or "UZS",
                "duration_minutes": service.duration_minutes or 30,
                "category_id": service.category_id,
                "doctor_id": service.doctor_id,
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

            # [OK] НОВАЯ ЛОГИКА: определяем группу только по явному routing truth
            resolved_queue_group = resolve_queue_group_key(
                service_code=service_data["service_code"],
                queue_tag=service_data["queue_tag"],
                department_key=service_data["department_key"],
            )

            if resolved_queue_group:
                registrar_group = queue_group_to_registrar_group.get(
                    resolved_queue_group, "procedures"
                )
                service_data["group"] = registrar_group
                grouped_services[registrar_group].append(service_data)
                continue

            # Без явного routing truth держим нейтральную группу, а не угадываем по category/name.
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
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )
    except Exception as e:
        # Остальные ошибки (БД, сеть и т.д.)
        from sqlalchemy.exc import SQLAlchemyError

        if isinstance(e, SQLAlchemyError):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Внутренняя ошибка сервера. Подробности в журнале.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )


# ===================== ВРАЧИ И РАСПИСАНИЯ =====================


@router.get("/registrar/doctors")
def get_registrar_doctors(
    specialty: Optional[str] = Query(None, description="Фильтр по специальности"),
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
                for specialty in set(d["specialty"] for d in result)
            },
        }

    except (ValueError, AttributeError) as e:
        # Ошибки валидации или доступа к атрибутам
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )
    except Exception as e:
        # Остальные ошибки (БД, сеть и т.д.)
        from sqlalchemy.exc import SQLAlchemyError

        if isinstance(e, SQLAlchemyError):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Внутренняя ошибка сервера. Подробности в журнале.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
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
            "current_time": datetime.now(timezone.utc).isoformat(),
        }

    except (ValueError, AttributeError) as e:
        # Ошибки валидации или доступа к атрибутам
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )
    except Exception as e:
        # Остальные ошибки (БД, сеть и т.д.)
        from sqlalchemy.exc import SQLAlchemyError

        if isinstance(e, SQLAlchemyError):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Внутренняя ошибка сервера. Подробности в журнале.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
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
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
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
        result = crud_queue.open_daily_queue(db, day, specialist_id)

        return {
            "success": True,
            "message": "Прием открыт, онлайн-набор закрыт",
            "opened_at": result["opened_at"],
            "online_entries_transferred": result["online_entries_count"],
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
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
    Legacy queue endpoint accepts only OnlineQueueEntry IDs.
    """
    try:
        from app.models.online_queue import OnlineQueueEntry
        from app.models.visit import Visit

        queue_entry = (
            db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        )
        if not queue_entry:
            # This legacy queue route must not fall back to Visit or Appointment IDs:
            # numeric IDs can collide across tables and mutate the wrong record.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Queue entry not found",
            )

        if queue_entry:
            linked_visit = None
            if queue_entry.visit_id:
                linked_visit = (
                    db.query(Visit).filter(Visit.id == queue_entry.visit_id).first()
                )
                if linked_visit and linked_visit.patient_id != queue_entry.patient_id:
                    logger.warning(
                        "start_queue_visit: entry visit owner mismatch entry_id=%d visit_id=%d",
                        queue_entry.id,
                        linked_visit.id,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Queue entry visit does not belong to the queue patient",
                    )

            changed_at = datetime.now(timezone.utc)
            queue_entry.status = "in_progress"
            queue_entry.updated_at = changed_at
            if linked_visit:
                linked_visit.status = "in_progress"
                linked_visit.updated_at = changed_at

            logger.info(
                "start_queue_visit: started queue entry %d; linked_visit_id=%s; status=%s",
                queue_entry.id,
                queue_entry.visit_id,
                queue_entry.status,
            )

            db.commit()
            db.refresh(queue_entry)
            if linked_visit:
                db.refresh(linked_visit)

            return {
                "success": True,
                "message": "Прием начат успешно",
                "entry": {
                    "id": queue_entry.id,
                    "status": queue_entry.status,
                    "patient_id": queue_entry.patient_id,
                    "visit_id": queue_entry.visit_id,
                },
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )



# ===================== HELPERS ДЛЯ get_today_queues (R-22 decomposition) =====================


def _parse_queue_target_date(target_date: str | None) -> "date":
    """R-22: Парсинг даты для очереди. Возвращает today если невалидно."""
    from datetime import datetime
    if target_date:
        import re
        if re.match(r'^\d{4}-\d{2}-\d{2}$', target_date):
            try:
                return datetime.strptime(target_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
    return date.today()


def _normalize_department_filter(department: str | None) -> set[str] | None:
    """R-22: Нормализация department фильтра для очереди."""
    if not department:
        return None
    normalized = str(department).strip().lower()
    aliases = {
        "lab": {"lab", "laboratory"},
        "laboratory": {"lab", "laboratory"},
    }
    return aliases.get(normalized, {normalized})


def _load_queue_data_for_date(db: Session, target_day: "date") -> tuple:
    """R-22: Загрузка visits, appointments и online entries для даты.

    Returns:
        tuple of (visits, appointments, online_entries)
    """
    from app.models.appointment import Appointment
    from app.models.online_queue import DailyQueue, OnlineQueueEntry
    from app.models.visit import Visit

    visits = (
        db.query(Visit)
        .filter(
            Visit.visit_date == target_day,
            ~func.lower(func.coalesce(Visit.status, "")).in_(
                REGISTRAR_HIDDEN_QUEUE_STATUSES
            ),
        )
        .all()
    )

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.appointment_date == target_day,
            ~func.lower(func.coalesce(Appointment.status, "")).in_(
                REGISTRAR_HIDDEN_QUEUE_STATUSES
            ),
        )
        .all()
    )

    online_entries = (
        db.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(
            DailyQueue.day == target_day,
            OnlineQueueEntry.status.in_(["waiting", "called", "paid"]),
        )
        .order_by(OnlineQueueEntry.queue_time.asc(), OnlineQueueEntry.id.asc())
        .all()
    )

    return visits, appointments, online_entries


# ===================== ТЕКУЩИЕ ОЧЕРЕДИ =====================


@router.get("/registrar/queues/today")
def get_today_queues(
    target_date: Optional[str] = Query(
        None, description="Дата (YYYY-MM-DD), по умолчанию сегодня"
    ),
    department: Optional[str] = Query(None, description="Фильтр по отделению"),
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
        from app.models.online_queue import DailyQueue, OnlineQueueEntry
        from app.models.patient import Patient
        from app.models.visit import Visit

        def _same_patient_queue_entry_for_visit_id(
            visit_id: int | None,
            patient_id: int | None,
        ) -> OnlineQueueEntry | None:
            if visit_id is None or patient_id is None:
                return None
            return (
                db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.visit_id == visit_id,
                    OnlineQueueEntry.patient_id == patient_id,
                )
                .order_by(OnlineQueueEntry.id.asc())
                .first()
            )

        def _same_patient_queue_entry_for_visit(
            visit: Visit,
        ) -> OnlineQueueEntry | None:
            return _same_patient_queue_entry_for_visit_id(
                visit.id,
                visit.patient_id,
            )

        # R-22: date parsing + department filter extracted to helpers
        today = _parse_queue_target_date(target_date)
        department_filter = _normalize_department_filter(department)

        # R-22: data loading extracted to helper
        visits, appointments, online_entries = _load_queue_data_for_date(db, today)

        # Группируем записи по специальности
        queues_by_specialty = {}
        seen_visit_ids = set()  # Для отслеживания уже обработанных Visit
        seen_appointment_ids = set()  # Для отслеживания уже обработанных Appointment
        # Обрабатываем Visit (новая система)
        for visit in visits:
            # Пропускаем если уже обработан
            if visit.id in seen_visit_ids:
                continue
            # ⚠️ НЕ добавляем в seen_visit_ids здесь - сначала проверяем OQE

            # ⭐ PHASE 1.1: Пропускаем Visit если есть связанный OnlineQueueEntry
            # Очередь должна читаться ТОЛЬКО из OnlineQueueEntry (SSOT)
            has_queue_entry = _same_patient_queue_entry_for_visit(visit)
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
                            'service_code': getattr(service, 'service_code', None),
                        }
                    )
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
                    elif service.service_code:
                        service_code_upper = str(service.service_code).upper()
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

                visit_created_at = (
                    visit.confirmed_at or visit.created_at
                    if hasattr(visit, 'confirmed_at')
                    else visit.created_at
                )

                # ✅ ИСПРАВЛЕНО: Получаем queue_time из связанной записи в queue_entries
                visit_queue_time = None
                try:
                    queue_entry_row = _same_patient_queue_entry_for_visit(visit)
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

                # 2. Создаем запись для кардиолога в очередь cardiology (без ЭКГ услуг)
                specialty = "cardiology"
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
                    queue_entry_row = _same_patient_queue_entry_for_visit(visit)
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
                continue  # Переходим к следующему визиту
            elif has_ecg and has_only_ecg:
                # Только ЭКГ - идёт в echokg
                specialty = "echokg"

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
                    queue_entry_row = _same_patient_queue_entry_for_visit(visit)
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
                queue_entry_row = _same_patient_queue_entry_for_visit(visit)
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
        from app.models.clinic import Doctor
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
                        "get_today_queues: OnlineQueueEntry - QR-запись, НЕ пропускаем",
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

            # ✅ CANONICAL: DailyQueue.specialist_id должен указывать на Doctor.id.
            # Старые записи с user_id больше не auto-link'им: вместо этого оставляем
            # запись видимой и помечаем её как требующую deterministic repair.
            doctor = db.query(Doctor).filter(Doctor.id == daily_queue.specialist_id).first()
            integrity_warnings: list[str] = []
            if not doctor:
                integrity_warnings.append("linked_doctor_missing")
                logger.warning(
                    "get_today_queues: DailyQueue %d specialist_id=%s does not resolve to Doctor.id",
                    daily_queue.id,
                    daily_queue.specialist_id,
                )

            # [OK] ИСПРАВЛЕНО: Приоритет - queue_tag из DailyQueue, затем doctor.department
            # queue_tag - это точное указание очереди, созданное при регистрации
            specialty = None
            if daily_queue.queue_tag:
                specialty = daily_queue.queue_tag.lower()
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

            if doctor and not doctor.user_id:
                integrity_warnings.append("doctor_without_user")
            if doctor and doctor.user and not doctor.user.is_active:
                integrity_warnings.append("doctor_user_inactive")
            if doctor and not doctor.active:
                integrity_warnings.append("doctor_inactive")
            if doctor and not doctor.cabinet:
                integrity_warnings.append("doctor_cabinet_missing")

            if specialty not in queues_by_specialty:
                queues_by_specialty[specialty] = {
                    "entries": [],
                    "doctor": doctor,
                    "doctor_id": doctor.id if doctor else daily_queue.specialist_id,
                    "integrity_warnings": list(dict.fromkeys(integrity_warnings)),
                }
            else:
                # ✅ ИСПРАВЛЕНО: Обновляем doctor_id и doctor, если specialty уже существует
                # Приоритет у online_queue записей (они обрабатываются после visit и отражают актуальное состояние)
                # Это важно, когда для одной специальности есть записи от разных врачей
                bucket = queues_by_specialty[specialty]
                bucket.setdefault("integrity_warnings", [])
                for warning in integrity_warnings:
                    if warning not in bucket["integrity_warnings"]:
                        bucket["integrity_warnings"].append(warning)

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
        from app.models.payment import Payment

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

                if patient_id and appointment_date and doctor_id is not None:
                    queue_entry_row = db.execute(
                        text(
                            """
                            SELECT qe.queue_time
                            FROM queue_entries qe
                            JOIN daily_queues dq ON qe.queue_id = dq.id
                            WHERE qe.patient_id = :patient_id
                              AND qe.visit_id IS NULL
                              AND dq.day = :appointment_date
                              AND dq.specialist_id = :doctor_id
                            ORDER BY qe.created_at DESC
                            LIMIT 1
                            """
                        ),
                        {
                            "patient_id": patient_id,
                            "appointment_date": appointment_date,
                            "doctor_id": doctor_id,
                        },
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
        include_lab_report_summary = bool(
            department_filter and department_filter.intersection({"lab", "laboratory"})
        )
        visible_entry_wrappers = []
        if include_lab_report_summary:
            for specialty, data in queues_by_specialty.items():
                specialty_key = str(specialty or "").strip().lower()
                if department_filter and specialty_key not in department_filter:
                    continue
                visible_entry_wrappers.extend(data["entries"])

        visible_visit_ids: set[int] = set()
        for entry_wrapper in visible_entry_wrappers:
            entry_type = entry_wrapper.get("type")
            entry_data = entry_wrapper.get("data")
            entry_visit_id = (
                entry_wrapper.get("visit_id")
                or getattr(entry_data, "visit_id", None)
                or (
                    getattr(entry_data, "id", None)
                    if entry_type == "visit"
                    else None
                )
            )
            if entry_visit_id:
                visible_visit_ids.add(entry_visit_id)

        latest_lab_reports_by_visit = _latest_lab_report_summaries_by_visit(
            db,
            visible_visit_ids,
        )

        for specialty, data in queues_by_specialty.items():
            specialty_key = str(specialty or "").strip().lower()
            if department_filter and specialty_key not in department_filter:
                continue

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
                                from datetime import timezone

                                sort_time = sort_time.replace(tzinfo=timezone.utc)
                        elif isinstance(queue_time, str):
                            try:
                                # Пробуем разные форматы дат
                                if 'T' in queue_time:
                                    sort_time = datetime.fromisoformat(
                                        queue_time.replace('Z', '+00:00')
                                    )
                                else:
                                    # ✅ ИСПРАВЛЕНО Bug 3: strptime возвращает naive datetime, нормализуем к UTC
                                    from datetime import timezone

                                    sort_time = datetime.strptime(
                                        queue_time, '%Y-%m-%d %H:%M:%S'
                                    ).replace(tzinfo=timezone.utc)
                            except (ValueError, TypeError):
                                pass

                    # Если queue_time не сработал, пробуем created_at
                    if not sort_time and created_at:
                        if isinstance(created_at, datetime):
                            sort_time = created_at
                            # ✅ ИСПРАВЛЕНО Bug 3: Нормализуем naive datetime к timezone-aware UTC
                            if sort_time.tzinfo is None:
                                from datetime import timezone

                                sort_time = sort_time.replace(tzinfo=timezone.utc)
                        elif isinstance(created_at, str):
                            try:
                                if 'T' in created_at:
                                    sort_time = datetime.fromisoformat(
                                        created_at.replace('Z', '+00:00')
                                    )
                                else:
                                    # ✅ ИСПРАВЛЕНО Bug 3: strptime возвращает naive datetime, нормализуем к UTC
                                    from datetime import timezone

                                    sort_time = datetime.strptime(
                                        created_at, '%Y-%m-%d %H:%M:%S'
                                    ).replace(tzinfo=timezone.utc)
                            except (ValueError, TypeError):
                                pass

                    # ✅ ИСПРАВЛЕНО Bug 3: Если ничего не сработало, используем timezone-aware UTC datetime
                    # Это предотвращает TypeError при сравнении timezone-aware и naive datetime
                    if not sort_time:
                        from datetime import timezone

                        sort_time = datetime.now(timezone.utc)

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
                    # Для visit/appointment: дедуплицируем только идентичные записи,
                    # а не все записи одного пациента в одной specialty на один день.
                    entry_key = f"{entry_type}_{entry_record_id}"

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
                                        'service_code': getattr(
                                            svc, 'service_code', None
                                        ),
                                    }
                                )

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
                        "canceled": "no_show",
                        "no_show": "no_show",
                    }
                    entry_status = status_mapping.get(visit.status, "waiting")

                    # [OK] Используем единый сервис для определения оплаты (Single Source of Truth)
                    discount_mode = _normalize_registration_discount_mode(
                        getattr(visit, "discount_mode", None)
                    )

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
                        "canceled": "no_show",
                        "no_show": "no_show",
                    }
                    entry_status = status_mapping.get(appointment.status, "waiting")

                    # [OK] Используем единый сервис для определения оплаты (Single Source of Truth)
                    discount_mode = _normalize_registration_discount_mode(
                        getattr(appointment, "visit_type", None)
                    )

                    source = "desk"  # Appointment обычно создается регистратором
                    try:
                        entry_wrapper["visit_id"] = CanonicalVisitService(
                            db
                        ).resolve_canonical_visit(
                            appointment.id,
                            create_if_missing=False,
                        )
                    except CanonicalVisitResolutionError as exc:
                        if exc.status_code != 404:
                            logger.warning(
                                "get_today_queues: failed to resolve canonical visit for appointment_id=%s: %s",
                                appointment.id,
                                exc.detail,
                            )
                        entry_wrapper["visit_id"] = None

                elif entry_type == "online_queue":
                    # ✅ SSOT FIX: entry_data может быть OnlineQueueEntry или Visit (для QR-визитов)
                    is_visit_object = hasattr(entry_data, 'visit_date') and not hasattr(entry_data, 'queue_id')
                    
                    if is_visit_object:
                        # entry_data это Visit с source='online'
                        visit = entry_data
                        # ✅ SSOT FIX: Для QR-визитов нужно получить данные из OnlineQueueEntry
                        # Frontend использует этот ID для вызова full-update endpoint
                        queue_entry_for_visit = _same_patient_queue_entry_for_visit(visit)
                        if queue_entry_for_visit:
                            record_id = queue_entry_for_visit.id
                            # ⭐ PHASE 1 FIX: Сохраняем данные из OQE для использования позже
                            entry_wrapper["oqe_number"] = queue_entry_for_visit.number
                            entry_wrapper["oqe_total_amount"] = queue_entry_for_visit.total_amount or 0
                            entry_wrapper["oqe_queue_time"] = queue_entry_for_visit.queue_time
                            entry_wrapper["oqe_updated_at"] = queue_entry_for_visit.updated_at
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
                        entry_wrapper["queue_entry_id"] = online_entry.id
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

                    # ✅ ИСПРАВЛЕНО: Определяем service_name только из явной service truth
                    # Приоритет: 1. Имя из первой услуги 2. SSOT lookup по specialty
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
                        from app.services.service_mapping import get_default_service_by_specialty
                        
                        default_service = get_default_service_by_specialty(db, specialty)
                        if default_service:
                            service_name = default_service["name"]
                            # ✅ ВАЖНО: Добавляем service_id для правильной работы визарда
                            entry_wrapper["service_id"] = default_service["id"]
                            entry_wrapper["service_code"] = default_service["service_code"]

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
                         except Exception:
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
                            except Exception:
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
                            except Exception:
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

                # appointment_id must mean a real Appointment.id for this row.
                # Visit rows do not have an explicit Appointment FK, so a fuzzy
                # patient/date/doctor match can expose an unrelated appointment.
                appointment_id_value = record_id if entry_type == "appointment" else None

                # ✅ ИСПРАВЛЕНО: Получаем РЕАЛЬНЫЙ номер и queue_time из queue_entries
                # Используем Table reflection вместо ORM модели для избежания конфликта DailyQueue
                queue_entry_number = idx  # По умолчанию используем idx
                queue_entry_time = None  # По умолчанию нет queue_time

                # Пробуем получить номер и queue_time из таблицы queue_entries через Table reflection
                queue_entry_updated_at = None

                if record_id:
                    try:
                        # Используем прямой SQL запрос через Table reflection (без импорта модели)
                        from sqlalchemy import select, text

                        # Используем прямой SQL для избежания конфликта с моделями
                        if entry_type == "online_queue":
                            # ✅ SSOT FIX: entry_data может быть Visit (для QR-записей) или OnlineQueueEntry
                            # Проверяем тип объекта
                            is_visit_object = hasattr(entry_data, 'visit_date') and not hasattr(entry_data, 'queue_id')
                            
                            if is_visit_object:
                                # ⭐ PHASE 1 FIX: Используем уже полученные данные из entry_wrapper
                                queue_entry_number = entry_wrapper.get("oqe_number") or idx
                                queue_entry_time = entry_wrapper.get("oqe_queue_time")
                                queue_entry_updated_at = entry_wrapper.get("oqe_updated_at")
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
                                queue_entry_updated_at = getattr(entry_data, 'updated_at', None)
                            logger.debug(
                                "get_today_queues: OnlineQueue номер: ID=%d, number=%d, queue_time=%s, patient=%s",
                                record_id,
                                queue_entry_number,
                                queue_entry_time,
                                patient_name,
                            )
                        elif entry_type == "visit":
                            # Ищем запись по visit_id
                            queue_entry_row = _same_patient_queue_entry_for_visit_id(
                                record_id,
                                patient_id,
                            )
                            if queue_entry_row:
                                queue_entry_number = queue_entry_row.number
                                queue_entry_time = queue_entry_row.queue_time
                                queue_entry_updated_at = queue_entry_row.updated_at
                        elif (
                            entry_type == "appointment"
                            and patient_id
                            and appointment_date
                            and doctor_id is not None
                        ):
                            # Для Appointment используем только queue entry того же пациента, дня и врача.
                            queue_entry_row = db.execute(
                                text(
                                    """
                                    SELECT qe.number, qe.queue_time, qe.updated_at
                                    FROM queue_entries qe
                                    JOIN daily_queues dq ON qe.queue_id = dq.id
                                    WHERE qe.patient_id = :patient_id
                                      AND qe.visit_id IS NULL
                                      AND dq.day = :appointment_date
                                      AND dq.specialist_id = :doctor_id
                                    ORDER BY qe.created_at DESC
                                    LIMIT 1
                                    """
                                ),
                                {
                                    "patient_id": patient_id,
                                    "appointment_date": appointment_date,
                                    "doctor_id": doctor_id,
                                },
                            ).first()
                            if queue_entry_row:
                                queue_entry_number = queue_entry_row.number
                                queue_entry_time = queue_entry_row.queue_time
                                queue_entry_updated_at = queue_entry_row.updated_at
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
                entry_updated_at = (
                    queue_entry_updated_at
                    or entry_wrapper.get("oqe_updated_at")
                    or getattr(entry_data, "updated_at", None)
                    or entry_wrapper.get("created_at")
                )
                entry_display_time_kind = (
                    "queue_time" if queue_entry_time or entry_wrapper.get("queue_time") else "created_at"
                )

                entry_visit_id = (
                    entry_wrapper.get("visit_id")
                    or getattr(entry_data, "visit_id", None)
                    or (record_id if entry_type == "visit" else None)
                )
                latest_lab_report = (
                    latest_lab_reports_by_visit.get(entry_visit_id)
                    if entry_visit_id
                    else None
                )
                payment_status, payment_type = _resolve_payment_truth(
                    db,
                    visit_id=entry_visit_id,
                    legacy_paid_at=getattr(entry_data, "payment_processed_at", None),
                )
                canonical_status = _normalize_queue_status_for_registrar(entry_status)
                available_actions = _registrar_available_actions(
                    user=current_user,
                    payment_status=payment_status,
                    queue_status=canonical_status,
                    visit_id=entry_visit_id,
                    patient_id=patient_id,
                )
                can_mark_paid = "mark_paid" in available_actions
                can_start_visit = "start_visit" in available_actions
                can_print_ticket = "print_ticket" in available_actions
                can_complete = "complete" in available_actions
                can_cancel = "cancel" in available_actions
                can_view_emr = "view_emr" in available_actions
                can_schedule_next = "schedule_next" in available_actions

                entries.append(
                    {
                        "id": record_id,
                        "canonical_record_id": record_id,
                        "record_kind": entry_type,
                        "source_kind": source,
                        "appointment_id": appointment_id_value,  # Явно добавляем appointment_id
                        "visit_id": entry_visit_id,
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
                        "payment_status": payment_status,
                        "payment_type": payment_type,
                        "can_mark_paid": can_mark_paid,
                        "can_start_visit": can_start_visit,
                        "can_print_ticket": can_print_ticket,
                        "can_complete": can_complete,
                        "can_cancel": can_cancel,
                        "can_view_emr": can_view_emr,
                        "can_schedule_next": can_schedule_next,
                        "available_actions": available_actions,
                        "source": source,
                        "status": canonical_status,
                        "canonical_status": canonical_status,
                        "queue_status": canonical_status,
                        "queue_position": queue_entry_number,
                        "created_at": _serialize_registrar_datetime(
                            entry_wrapper.get("created_at")
                        ),
                        "queue_time": _serialize_registrar_datetime(entry_queue_time),
                        "updated_at": _serialize_registrar_datetime(entry_updated_at),
                        "last_changed_at": _serialize_registrar_datetime(entry_updated_at),
                        "display_time_kind": entry_display_time_kind,
                        "timezone": "Asia/Tashkent",
                        "called_at": None,
                        "visit_time": visit_time,
                        "discount_mode": discount_mode,
                        "approval_status": getattr(
                            entry_data, "approval_status", None
                        ),
                        "latest_lab_report": latest_lab_report,
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
                # Если doctor не найден, оставляем raw specialist_id видимым для repair.
                "specialist_id": data["doctor_id"],
                "specialist_name": (
                    doctor.user.full_name
                    if doctor and doctor.user
                    else f"Специалист #{data['doctor_id']}"
                ),
                "specialty": specialty,
                "timezone": "Asia/Tashkent",
                "cabinet": doctor.cabinet if doctor else "N/A",
                "integrity_warnings": list(dict.fromkeys(data.get("integrity_warnings", []))),
                "has_integrity_warnings": bool(data.get("integrity_warnings")),
                        "opened_at": datetime.now(timezone.utc).isoformat(),
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
            "timezone": "Asia/Tashkent",
        }

    except Exception as e:
        logger.error(
            "get_today_queues: КРИТИЧЕСКАЯ ОШИБКА: %s: %s",
            type(e).__name__,
            e,
            exc_info=True,
        )
        logger.exception("Registrar operation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )


# ===================== КАЛЕНДАРЬ ЗАПИСЕЙ =====================


@router.get("/registrar/calendar")
def get_registrar_calendar(
    start_date: date = Query(..., description="Начальная дата"),
    end_date: date = Query(..., description="Конечная дата"),
    doctor_id: Optional[int] = Query(None, description="Фильтр по врачу"),
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
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )


# ===================== МАССОВОЕ СОЗДАНИЕ ОЧЕРЕДЕЙ =====================


# Pydantic schemas для batch endpoint
class BatchServiceItem(BaseModel):
    """Услуга для массового создания очередей"""

    specialist_id: int = Field(
        ..., description="ID специалиста (Doctor.id)"
    )
    service_id: int = Field(..., description="ID услуги")
    quantity: int = Field(default=1, ge=1, description="Количество")


class BatchQueueEntriesRequest(BaseModel):
    """Запрос на массовое создание записей в очереди"""

    patient_id: int = Field(..., description="ID пациента")
    source: str = Field(
        ...,
        description="Источник регистрации: 'online', 'desk', 'morning_assignment'",
        pattern="^(online|desk|morning_assignment)$",
    )
    services: List[BatchServiceItem] = Field(
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
    entries: List[BatchQueueEntryResponse]
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
    import logging
    from zoneinfo import ZoneInfo

    from app.models.online_queue import DailyQueue, OnlineQueueEntry
    from app.models.patient import Patient

    logger = logging.getLogger(__name__)

    try:
        # Проверяем существование пациента
        patient = db.query(Patient).filter(Patient.id == request.patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пациент с ID {request.patient_id} не найден",
            )

        # Текущая дата и timezone
        timezone = ZoneInfo("Asia/Tashkent")
        today = date.today()
        current_time = datetime.now(timezone)

        # Группируем услуги по specialist_id (один врач = одна запись в очереди)
        services_by_specialist: Dict[int, List[BatchServiceItem]] = {}
        for service_item in request.services:
            service = db.query(Service).filter(Service.id == service_item.service_id).first()
            if not service:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Услуга с ID {service_item.service_id} не найдена",
                )

            specialist_id = service_item.specialist_id

            from app.models.clinic import Doctor

            doctor = db.query(Doctor).filter(Doctor.id == specialist_id).first()
            if not doctor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Врач с ID {specialist_id} не найден",
                )

            if specialist_id not in services_by_specialist:
                services_by_specialist[specialist_id] = []
            services_by_specialist[specialist_id].append(service_item)

        logger.debug(
            f"[create_queue_entries_batch] Группировка услуг: {len(services_by_specialist)} уникальных специалистов"
        )

        # Создаем записи в очереди для каждого специалиста
        created_entries = []
        reused_entries_count = 0

        for specialist_id, services_list in services_by_specialist.items():
            doctor = db.query(Doctor).filter(Doctor.id == specialist_id).first()
            if not doctor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Врач с ID {specialist_id} не найден",
                )

            queue_tag = None
            if services_list:
                first_service = db.query(Service).filter(Service.id == services_list[0].service_id).first()
                queue_tag = getattr(first_service, "queue_tag", None)

            daily_queue = queue_service.get_or_create_daily_queue(
                db,
                day=today,
                specialist_id=doctor.id,
                queue_tag=queue_tag,
                defaults={
                    "max_online_entries": doctor.max_online_per_day,
                    "cabinet_number": doctor.cabinet,
                },
            )

            # Проверяем дубликаты (для любых source)
            if daily_queue:
                existing_entry = (
                    db.query(OnlineQueueEntry)
                    .filter(
                        OnlineQueueEntry.queue_id == daily_queue.id,
                        OnlineQueueEntry.patient_id == request.patient_id,
                        OnlineQueueEntry.status.in_(
                            ["waiting", "called"]
                        ),  # Активные записи
                    )
                    .first()
                )

                if existing_entry:
                    logger.warning(
                        f"[create_queue_entries_batch] Пациент {request.patient_id} уже в очереди "
                        f"к специалисту {specialist_id} (queue_id={daily_queue.id}, entry_id={existing_entry.id})"
                    )
                    # Пропускаем создание дубликата, но добавляем существующую запись в ответ
                    created_entries.append(
                        BatchQueueEntryResponse(
                            specialist_id=specialist_id,
                            queue_id=daily_queue.id,
                            number=existing_entry.number,
                            queue_time=(
                                existing_entry.queue_time.isoformat()
                                if existing_entry.queue_time
                                else current_time.isoformat()
                            ),
                        )
                    )
                    reused_entries_count += 1
                    continue

            # [OK] Используем SSOT queue_service для создания записи
            # Это гарантирует правильную логику:
            # - Автоматическое создание DailyQueue если не существует
            # - Корректное присвоение номера в очереди
            # - Проверка дубликатов
            # - Установка queue_time

            try:
                # Получаем имя и телефон пациента
                patient_name = (
                    patient.short_name()
                    if hasattr(patient, 'short_name')
                    else f"{patient.last_name} {patient.first_name}"
                )
                patient_phone = patient.phone or None

                # Создаем запись через SSOT
                queue_entry = queue_service.create_queue_entry(
                    db,
                    daily_queue=daily_queue,
                    patient_id=request.patient_id,
                    patient_name=patient_name,
                    phone=patient_phone,
                    source=request.source,  # ⭐ Сохраняем оригинальный source!
                    queue_time=current_time,  # ⭐ Текущее время для справедливого присвоения номера
                    auto_number=True,
                    commit=False,
                )

                logger.info(
                    f"[create_queue_entries_batch] [OK] Создана запись: specialist_id={specialist_id}, "
                    f"queue_id={queue_entry.queue_id}, number={queue_entry.number}, source={request.source}"
                )

                # Получаем queue_id из созданной записи
                queue = (
                    db.query(DailyQueue)
                    .filter(DailyQueue.id == queue_entry.queue_id)
                    .first()
                )

                created_entries.append(
                    BatchQueueEntryResponse(
                        specialist_id=specialist_id,
                        queue_id=queue_entry.queue_id,
                        number=queue_entry.number,
                        queue_time=(
                            queue_entry.queue_time.isoformat()
                            if queue_entry.queue_time
                            else current_time.isoformat()
                        ),
                    )
                )

            except ValueError as ve:
                # queue_service может выбросить ValueError если что-то не так
                logger.error(f"[create_queue_entries_batch] Ошибка валидации: {ve}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ошибка создания записи для специалиста {specialist_id}: {str(ve)}",
                )

        db.commit()

        entries_count = len(created_entries)
        created_count = max(entries_count - reused_entries_count, 0)
        if reused_entries_count and created_count:
            message = (
                f"Создано {created_count} записей в очереди; "
                f"{reused_entries_count} запись уже существовала"
            )
        elif reused_entries_count:
            message = "Запись уже существовала в очереди"
        else:
            message = (
                f"Создано {entries_count} "
                f"{'записей' if entries_count != 1 else 'запись'} в очереди"
            )

        return BatchQueueEntriesResponse(
            success=True,
            entries=created_entries,
            message=message,
        )

    except HTTPException:
        # Пробрасываем HTTPException без изменений
        raise
    except Exception as e:
        # Логируем и оборачиваем непредвиденные ошибки
        logger.error(
            f"[create_queue_entries_batch] Непредвиденная ошибка: {type(e).__name__}: {e}"
        )
        import traceback

        logger.exception("Registrar operation failed")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )


# ===================== КОНВЕРТАЦИЯ DOCTOR_ID → USER_ID =====================


@router.get("/registrar-integration/doctors/{doctor_id}/user-id")
def get_doctor_user_id(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    DEPRECATED: legacy compatibility bridge for doctor -> user lookup.

    Operational queue flows canonically use Doctor.id. This endpoint remains
    only as a transitional bridge and should not be treated as the source of truth.

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
            "canonical_specialist_id": doctor.id,
            "user_id": doctor.user_id,
            "doctor_name": doctor.user.full_name if doctor.user else None,
            "deprecated": True,
            "note": "Use doctor_id as the canonical specialist identifier in queue flows.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения user_id для doctor_id={doctor_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )
