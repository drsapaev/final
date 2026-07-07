"""
API endpoints для интеграции регистратуры с админ панелью
Основа: detail.md стр. 85-183
"""

import logging
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, text
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import clinic as crud_clinic
from app.crud import online_queue as crud_queue
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
        dt = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
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

    except Exception:
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

    except (ValueError, AttributeError):
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

    except (ValueError, AttributeError):
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
            "current_time": datetime.now(UTC).isoformat(),
        }

    except (ValueError, AttributeError):
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Internal server error")
    except Exception:
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

    except Exception:
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

            changed_at = datetime.now(UTC)
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
    except Exception:
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




def _detect_ecg_services(services: list) -> tuple[bool, int, int]:
    """R-22: Detect ECG services in a visit's service list.

    Checks by queue_tag, service name, and service code.

    Returns:
        tuple of (has_ecg, ecg_count, non_ecg_count)
    """

    has_ecg = False
    ecg_count = 0
    non_ecg_count = 0

    for service in services:
        is_ecg = False

        # Check by queue_tag
        if service.queue_tag == 'ecg':
            is_ecg = True

        # Check by service name
        elif service.name:
            name_lower = str(service.name).lower()
            if 'экг' in name_lower or 'ecg' in name_lower:
                is_ecg = True

        # Check by service code
        if not is_ecg and service.service_code:
            code_upper = str(service.service_code).upper()
            if 'ECG' in code_upper or 'ЭКГ' in code_upper:
                is_ecg = True

        if is_ecg:
            has_ecg = True
            ecg_count += 1
        else:
            non_ecg_count += 1

    return has_ecg, ecg_count, non_ecg_count


def _ensure_specialty_queue(
    queues_by_specialty: dict,
    specialty: str,
    doctor_id: int | None,
) -> None:
    """R-22: Ensure a specialty queue exists in the grouping dict."""
    if specialty not in queues_by_specialty:
        queues_by_specialty[specialty] = {
            "entries": [],
            "doctor": None,
            "doctor_id": doctor_id,
        }


def _get_visit_queue_time(
    db: Session, visit: Any
) -> Any:
    """R-22: Get queue_time from linked OnlineQueueEntry for a visit."""
    from app.models.online_queue import OnlineQueueEntry
    try:
        queue_entry = (
            db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.visit_id == visit.id,
                OnlineQueueEntry.patient_id == visit.patient_id,
            )
            .order_by(OnlineQueueEntry.id.asc())
            .first()
        )
        if queue_entry and queue_entry.queue_time:
            return queue_entry.queue_time
    except Exception:
        pass
    return None


def _get_visit_created_at(visit: Any) -> Any:
    """R-22: Get created_at from visit, preferring confirmed_at if available."""
    if hasattr(visit, 'confirmed_at') and visit.confirmed_at:
        return visit.confirmed_at
    return visit.created_at



# ===================== R-22 Phase 3: Online entries + Appointment processing =====================


_SPECIALTY_MAPPING = {
    "cardio": "cardiology",
    "cardiology": "cardiology",
    "derma": "dermatology",
    "dermatology": "dermatology",
    "dentist": "stomatology",
    "stomatology": "stomatology",
    "lab": "laboratory",
    "laboratory": "laboratory",
    "ecg": "echokg",
    "echokg": "echokg",
}


def _process_online_queue_entries(
    db: Session,
    online_entries: list,
    visits: list,
    queues_by_specialty: dict,
    seen_visit_ids: set,
) -> None:
    """R-22 Phase 3: Process OnlineQueueEntry records into specialty queues."""
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue

    for online_entry in online_entries:
        if online_entry.visit_id and online_entry.visit_id in seen_visit_ids:
            continue

        if not online_entry.visit_id and online_entry.patient_id:
            is_qr_entry = online_entry.source in ('online', 'confirmation')
            if not is_qr_entry:
                patient_has_visit = any(
                    v.patient_id == online_entry.patient_id for v in visits
                )
                if patient_has_visit:
                    continue

        daily_queue = (
            db.query(DailyQueue)
            .filter(DailyQueue.id == online_entry.queue_id)
            .first()
        )
        if not daily_queue:
            continue

        doctor = db.query(Doctor).filter(Doctor.id == daily_queue.specialist_id).first()
        integrity_warnings: list[str] = []
        if not doctor:
            integrity_warnings.append("linked_doctor_missing")

        specialty = None
        if daily_queue.queue_tag:
            specialty = daily_queue.queue_tag.lower()
        elif doctor and doctor.department:
            specialty = doctor.department.lower()
        else:
            specialty = "general"

        specialty = _SPECIALTY_MAPPING.get(specialty, specialty)

        if doctor and not doctor.user_id:
            integrity_warnings.append("doctor_without_user")
        if doctor and doctor.user and not doctor.user.is_active:
            integrity_warnings.append("doctor_user_inactive")
        if doctor and not doctor.active:
            integrity_warnings.append("doctor_inactive")
        if doctor and not doctor.cabinet:
            integrity_warnings.append("doctor_cabinet_missing")

        _ensure_specialty_queue(queues_by_specialty, specialty, doctor.id if doctor else daily_queue.specialist_id)
        bucket = queues_by_specialty[specialty]
        bucket.setdefault("integrity_warnings", [])
        for warning in integrity_warnings:
            if warning not in bucket["integrity_warnings"]:
                bucket["integrity_warnings"].append(warning)

        if doctor and doctor.id:
            bucket["doctor"] = doctor
            bucket["doctor_id"] = doctor.id

        entry_time = (
            online_entry.queue_time
            if online_entry.queue_time
            else (online_entry.created_at if online_entry.created_at else datetime.now())
        )

        bucket["entries"].append({
            "type": "online_queue",
            "data": online_entry,
            "created_at": online_entry.created_at if online_entry.created_at else datetime.now(),
            "queue_time": entry_time,
        })


def _process_legacy_appointments(
    db: Session,
    appointments: list,
    queues_by_specialty: dict,
    seen_appointment_ids: set,
    today: "date",
) -> None:
    """R-22 Phase 3: Process legacy Appointment records into specialty queues."""
    from app.models.service import Service
    from app.models.visit import Visit

    for appointment in appointments:
        if appointment.id in seen_appointment_ids:
            continue
        seen_appointment_ids.add(appointment.id)

        specialty = None
        appointment_date = getattr(appointment, 'appointment_date', today)
        patient_id = getattr(appointment, 'patient_id', None)

        if hasattr(appointment, 'services') and appointment.services:
            for service_item in appointment.services:
                service = None
                if isinstance(service_item, dict):
                    service_id = service_item.get('id')
                    if service_id:
                        service = db.query(Service).filter(Service.id == service_id).first()
                elif isinstance(service_item, int):
                    service = db.query(Service).filter(Service.id == service_item).first()
                elif isinstance(service_item, str):
                    service = db.query(Service).filter(Service.name == service_item).first()
                if service and service.department_key:
                    specialty = service.department_key
                    break

        if not specialty:
            specialty = getattr(appointment, 'department', None) or "general"

        visit_exists = False
        doctor_id = getattr(appointment, 'doctor_id', None)
        if patient_id and appointment_date:
            try:
                visit_filters = [
                    Visit.patient_id == patient_id,
                    Visit.visit_date == appointment_date,
                ]
                if doctor_id is not None:
                    visit_filters.append(Visit.doctor_id == doctor_id)
                else:
                    visit_filters.append(Visit.doctor_id.is_(None))
                existing_visit = db.query(Visit).filter(and_(*visit_filters)).first()
                if existing_visit:
                    visit_exists = True
            except Exception:
                pass

        if visit_exists:
            continue

        _ensure_specialty_queue(queues_by_specialty, specialty, doctor_id)

        appointment_queue_time = None
        try:
            if patient_id and appointment_date and doctor_id is not None:
                queue_entry_row = db.execute(
                    text("""
                        SELECT qe.queue_time
                        FROM queue_entries qe
                        JOIN daily_queues dq ON qe.queue_id = dq.id
                        WHERE qe.patient_id = :patient_id
                          AND qe.visit_id IS NULL
                          AND dq.day = :appointment_date
                          AND dq.specialist_id = :doctor_id
                        ORDER BY qe.created_at DESC
                        LIMIT 1
                    """),
                    {
                        "patient_id": patient_id,
                        "appointment_date": appointment_date,
                        "doctor_id": doctor_id,
                    },
                ).first()
                if queue_entry_row and queue_entry_row.queue_time:
                    appointment_queue_time = queue_entry_row.queue_time
        except Exception:
            pass

        queues_by_specialty[specialty]["entries"].append({
            "type": "appointment",
            "data": appointment,
            "created_at": appointment.created_at,
            "queue_time": appointment_queue_time,
        })

        if not queues_by_specialty[specialty]["doctor"]:
            appointment_doctor = getattr(appointment, 'doctor', None)
            if appointment_doctor:
                queues_by_specialty[specialty]["doctor"] = appointment_doctor



# ===================== R-22 Phase 4: Entry serialization + queue payload =====================


def _serialize_queue_entry(
    *,
    entry_type: str,
    record_id: int | None,
    source: str,
    appointment_id_value: int | None,
    entry_visit_id: int | None,
    queue_entry_number: int,
    patient_id: int | None,
    patient_name: str,
    patient_birth_year: int | None,
    phone: str,
    address: str | None,
    services: list,
    service_codes: list,
    service_details: list,
    entry_wrapper: dict,
    total_cost: float | int,
    payment_status: str | None,
    payment_type: str | None,
    available_actions: list,
    canonical_status: str,
    entry_queue_time: Any,
    entry_updated_at: Any,
    entry_display_time_kind: str,
    visit_time: str | None,
    discount_mode: str,
    entry_data: Any,
    latest_lab_report: dict | None,
    entry_department_key: str | None,
    entry_department: str | None,
) -> dict:
    """R-22 Phase 4: Serialize a single queue entry into the API response dict."""
    can_mark_paid = "mark_paid" in available_actions
    can_start_visit = "start_visit" in available_actions
    can_print_ticket = "print_ticket" in available_actions
    can_complete = "complete" in available_actions
    can_cancel = "cancel" in available_actions
    can_view_emr = "view_emr" in available_actions
    can_schedule_next = "schedule_next" in available_actions

    return {
        "id": record_id,
        "canonical_record_id": record_id,
        "record_kind": entry_type,
        "source_kind": source,
        "appointment_id": appointment_id_value,
        "visit_id": entry_visit_id,
        "number": queue_entry_number,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "patient_birth_year": patient_birth_year,
        "phone": phone,
        "address": address,
        "services": services,
        "service_codes": service_codes,
        "service_details": service_details,
        "service_name": entry_wrapper.get("service_name"),
        "service_id": entry_wrapper.get("service_id"),
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
        "created_at": _serialize_registrar_datetime(entry_wrapper.get("created_at")),
        "queue_time": _serialize_registrar_datetime(entry_queue_time),
        "updated_at": _serialize_registrar_datetime(entry_updated_at),
        "last_changed_at": _serialize_registrar_datetime(entry_updated_at),
        "display_time_kind": entry_display_time_kind,
        "timezone": "Asia/Tashkent",
        "called_at": None,
        "visit_time": visit_time,
        "discount_mode": discount_mode,
        "approval_status": getattr(entry_data, "approval_status", None),
        "latest_lab_report": latest_lab_report,
        "type": entry_type,
        "record_type": entry_type,
        "queue_entry_id": entry_wrapper.get("queue_entry_id"),
        "department_key": entry_department_key,
        "department": entry_department,
        "session_id": getattr(entry_data, 'session_id', None),
    }


def _build_queue_payload(
    *,
    queue_data: dict,
    specialty: str,
    queue_number: int,
    entries: list,
) -> dict:
    """R-22 Phase 4: Build the final queue payload wrapper with stats."""
    return {
        "queue_id": queue_number,
        "specialist_id": queue_data["doctor_id"],
        "specialist_name": (
            queue_data["doctor"].user.full_name
            if queue_data.get("doctor") and queue_data["doctor"].user
            else f"Специалист #{queue_data['doctor_id']}"
        ),
        "specialty": specialty,
        "timezone": "Asia/Tashkent",
        "cabinet": queue_data["doctor"].cabinet if queue_data.get("doctor") else "N/A",
        "integrity_warnings": list(dict.fromkeys(queue_data.get("integrity_warnings", []))),
        "has_integrity_warnings": bool(queue_data.get("integrity_warnings")),
        "opened_at": datetime.now(UTC).isoformat(),
        "entries": entries,
        "stats": {
            "total": len(entries),
            "waiting": len([e for e in entries if e.get("status") == "waiting"]),
            "called": len([e for e in entries if e.get("status") == "called"]),
            "served": len([e for e in entries if e.get("status") == "served"]),
            "online_entries": len(
                [e for e in entries if e.get("source") == "online"]
            ),
        },
    }



# ===================== R-22 Phase 5: Queue entry lookup =====================


def _same_patient_queue_entry_for_visit_id(
    db: Session,
    visit_id: int | None,
    patient_id: int | None,
):
    """R-22 Phase 5: Find the OnlineQueueEntry linked to a visit by visit_id + patient_id.

    Returns None if either id is None or no entry is found.
    """
    from app.models.online_queue import OnlineQueueEntry
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


def _same_patient_queue_entry_for_visit(db: Session, visit):
    """R-22 Phase 5: Convenience wrapper around _same_patient_queue_entry_for_visit_id."""
    return _same_patient_queue_entry_for_visit_id(
        db,
        visit.id,
        visit.patient_id,
    )


def _resolve_queue_entry_metadata(
    *,
    db: Session,
    entry_type: str,
    entry_data: Any,
    entry_wrapper: dict,
    record_id: int | None,
    patient_id: int | None,
    appointment_date: Any,
    doctor_id: int | None,
    idx: int,
) -> tuple[int, Any, Any]:
    """R-22 Phase 5: Resolve (queue_entry_number, queue_entry_time, queue_entry_updated_at).

    Lookup priority depends on entry_type:
    - online_queue: read directly from OnlineQueueEntry (or entry_wrapper for QR-visits)
    - visit: lookup via _same_patient_queue_entry_for_visit_id
    - appointment: SQL query against queue_entries table (same patient + day + doctor)
    Falls back to (idx, None, None) on any error.
    """
    queue_entry_number = idx
    queue_entry_time = None
    queue_entry_updated_at = None

    if not record_id:
        return queue_entry_number, queue_entry_time, queue_entry_updated_at

    try:
        if entry_type == "online_queue":
            # entry_data may be Visit (for QR-visits) or OnlineQueueEntry
            is_visit_object = hasattr(entry_data, 'visit_date') and not hasattr(entry_data, 'queue_id')

            if is_visit_object:
                queue_entry_number = entry_wrapper.get("oqe_number") or idx
                queue_entry_time = entry_wrapper.get("oqe_queue_time")
                queue_entry_updated_at = entry_wrapper.get("oqe_updated_at")
            else:
                queue_entry_number = (
                    entry_data.number
                    if hasattr(entry_data, 'number') and entry_data.number is not None
                    else idx
                )
                queue_entry_time = (
                    entry_data.queue_time
                    if hasattr(entry_data, 'queue_time') and entry_data.queue_time
                    else None
                )
                queue_entry_updated_at = getattr(entry_data, 'updated_at', None)
        elif entry_type == "visit":
            queue_entry_row = _same_patient_queue_entry_for_visit_id(
                db,
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
        logger.debug(
            "get_today_queues: Ошибка получения queue_time: %s", str(e)
        )

    return queue_entry_number, queue_entry_time, queue_entry_updated_at



# ===================== R-22 Phase 6: Per-type entry processing =====================


_APPOINTMENT_STATUS_MAPPING = {
    "scheduled": "waiting",
    "pending": "waiting",
    "confirmed": "waiting",
    "paid": "waiting",
    "in_progress": "called",
    "in_visit": "called",
    "completed": "served",
    "cancelled": "no_show",
    "canceled": "no_show",
    "no_show": "no_show",
}


def _process_appointment_entry(
    *,
    db: Session,
    entry_data: Any,
    entry_wrapper: dict,
    today: "date",
) -> dict | None:
    """R-22 Phase 6: Process an Appointment row into entry fields.

    Returns a dict with the populated fields, or None to signal "skip this entry"
    (caller should `continue` to the next iteration).
    """
    if entry_data is None:
        logger.warning("get_today_queues: appointment entry with None data, skipping")
        return None

    from app.models.patient import Patient

    appointment = entry_data
    record_id = appointment.id
    patient_id = appointment.patient_id
    appointment_date = getattr(appointment, 'appointment_date', today)
    doctor_id = getattr(appointment, 'doctor_id', None)
    visit_time = (
        str(appointment.appointment_time)
        if hasattr(appointment, 'appointment_time')
        else None
    )

    patient_name = "Неизвестный пациент"
    phone = "Не указан"
    patient_birth_year = None
    address = None

    patient = (
        db.query(Patient)
        .filter(Patient.id == appointment.patient_id)
        .first()
    )
    if patient:
        patient_name = patient.short_name()
        phone = patient.phone or "Не указан"
        if patient.birth_date:
            patient_birth_year = patient.birth_date.year
        address = patient.address
    else:
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

    services: list = []
    service_codes: list = []
    if hasattr(appointment, 'services') and appointment.services:
        if isinstance(appointment.services, list):
            services = appointment.services
            for service in services:
                if isinstance(service, str):
                    if (
                        len(service) <= 10
                        or '-' in service
                        or service.isalnum()
                    ):
                        service_codes.append(service)

    total_cost = 0.0
    if (
        hasattr(appointment, 'payment_amount')
        and appointment.payment_amount
    ):
        total_cost = float(appointment.payment_amount)

    entry_status = _APPOINTMENT_STATUS_MAPPING.get(appointment.status, "waiting")
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

    return {
        "record_id": record_id,
        "patient_id": patient_id,
        "appointment_date": appointment_date,
        "doctor_id": doctor_id,
        "visit_time": visit_time,
        "patient_name": patient_name,
        "phone": phone,
        "patient_birth_year": patient_birth_year,
        "address": address,
        "services": services,
        "service_codes": service_codes,
        "total_cost": total_cost,
        "entry_status": entry_status,
        "discount_mode": discount_mode,
        "source": source,
    }



def _process_online_queue_entry(
    *,
    db: Session,
    entry_data: Any,
    entry_wrapper: dict,
    specialty: str,
) -> dict | None:
    """R-22 Phase 7: Process an OnlineQueueEntry (or QR-Visit) into entry fields.

    Returns a dict with the populated fields, or None to signal "skip this entry"
    (caller should `continue` to the next iteration).
    Mutates `entry_wrapper` in place: sets queue_entry_id, visit_id, oqe_*, service_name, service_id, service_code.
    """
    if entry_data is None:
        logger.warning("get_today_queues: online_queue entry with None data, skipping")
        return None

    from app.models.patient import Patient
    from app.models.service import Service
    from app.models.visit import VisitService
    from app.services.service_mapping import get_default_service_by_specialty

    # entry_data может быть OnlineQueueEntry или Visit (для QR-визитов)
    is_visit_object = hasattr(entry_data, 'visit_date') and not hasattr(entry_data, 'queue_id')

    services: list = []
    service_codes: list = []
    service_details: list = []

    if is_visit_object:
        # entry_data это Visit с source='online'
        visit = entry_data
        queue_entry_for_visit = _same_patient_queue_entry_for_visit(db, visit)
        if queue_entry_for_visit:
            record_id = queue_entry_for_visit.id
            entry_wrapper["oqe_number"] = queue_entry_for_visit.number
            entry_wrapper["oqe_total_amount"] = queue_entry_for_visit.total_amount or 0
            entry_wrapper["oqe_queue_time"] = queue_entry_for_visit.queue_time
            entry_wrapper["oqe_updated_at"] = queue_entry_for_visit.updated_at
        else:
            record_id = visit.id
        entry_wrapper["visit_id"] = visit.id
        entry_wrapper["queue_entry_id"] = queue_entry_for_visit.id if queue_entry_for_visit else None
        patient_id = visit.patient_id
        entry_status = visit.status or "waiting"
        source = visit.source or "online"
        discount_mode = visit.discount_mode or "none"
        visit_time = str(visit.visit_time) if hasattr(visit, 'visit_time') and visit.visit_time else None

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

        # Услуги из VisitService
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
                    "quantity": vs.qty or 1,
                })
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
        entry_status = online_entry.status
        source = online_entry.source or "online"
        discount_mode = online_entry.discount_mode or "none"
        visit_time = None

        # Услуги из online_entry.services (list или JSON string)
        if hasattr(online_entry, 'services') and online_entry.services:
            if isinstance(online_entry.services, list):
                services = online_entry.services
                for service in services:
                    if isinstance(service, dict):
                        if service.get("code"):
                            service_codes.append(service["code"])
                        elif service.get("service_code"):
                            service_codes.append(service["service_code"])
                    elif isinstance(service, str):
                        service_codes.append(service)
            elif isinstance(online_entry.services, str):
                import json
                try:
                    services = json.loads(online_entry.services)
                    if isinstance(services, list):
                        for service in services:
                            if isinstance(service, dict) and service.get("code"):
                                service_codes.append(service["code"])
                except Exception:
                    pass

    # service_name: приоритет — имя из первой услуги, затем SSOT lookup по specialty
    service_name = None
    if services and len(services) > 0:
        first = services[0]
        if isinstance(first, dict):
            service_name = first.get("name") or first.get("service_name")
        elif isinstance(first, str):
            service_name = first

    if not service_name:
        default_service = get_default_service_by_specialty(db, specialty)
        if default_service:
            service_name = default_service["name"]
            entry_wrapper["service_id"] = default_service["id"]
            entry_wrapper["service_code"] = default_service["service_code"]

    entry_wrapper["service_name"] = service_name

    # service_codes из entry_data.service_codes (дополнительно)
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

    # total_cost: приоритет oqe_total_amount > entry_data.total_amount > VisitService SUM
    total_cost = entry_wrapper.get("oqe_total_amount") or getattr(entry_data, 'total_amount', 0) or 0
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

    # service_details из entry_data.services
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
                        "price": float(svc.get("price", 0)) if svc.get("price") else 0,
                    })
                elif isinstance(svc, str):
                    service_details.append({
                        "id": None,
                        "code": None,
                        "name": svc,
                        "price": 0,
                    })

    return {
        "record_id": record_id,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "phone": phone,
        "patient_birth_year": patient_birth_year,
        "address": address,
        "entry_status": entry_status,
        "source": source,
        "discount_mode": discount_mode,
        "visit_time": visit_time,
        "services": services,
        "service_codes": service_codes,
        "service_details": service_details,
        "total_cost": total_cost,
    }



_VISIT_STATUS_MAPPING = {
    "confirmed": "waiting",
    "pending_confirmation": "waiting",
    "in_progress": "called",
    "completed": "served",
    "cancelled": "no_show",
    "canceled": "no_show",
    "no_show": "no_show",
}


def _process_visit_entry(
    *,
    db: Session,
    entry_data: Any,
    entry_wrapper: dict,
    specialty: str,
) -> dict | None:
    """R-22 Phase 8: Process a Visit row into entry fields.

    Returns a dict with the populated fields, or None to signal "skip this entry"
    (caller should `continue` to the next iteration). Skipping happens when:
    - entry_data is None
    - ecg_only flag set but no ECG services found
    - non-ECG filter and visit has only ECG services
    """
    if entry_data is None:
        logger.warning("get_today_queues: visit entry with None data, skipping")
        return None

    from app.models.patient import Patient
    from app.models.service import Service
    from app.models.visit import VisitService
    from app.services.service_mapping import get_service_code

    visit = entry_data
    record_id = visit.id
    patient_id = visit.patient_id
    visit_time = visit.visit_time
    discount_mode = visit.discount_mode

    patient_name = "Неизвестный пациент"
    phone = "Не указан"
    patient_birth_year = None
    address = None

    patient = (
        db.query(Patient).filter(Patient.id == visit.patient_id).first()
    )
    if patient:
        patient_name = patient.short_name()
        phone = patient.phone or "Не указан"
        if patient.birth_date:
            patient_birth_year = patient.birth_date.year
        address = patient.address
    else:
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

    all_visit_services = (
        db.query(VisitService)
        .filter(VisitService.visit_id == visit.id)
        .all()
    )

    ecg_only_flag = entry_wrapper.get("ecg_only", False)
    filter_services_flag = entry_wrapper.get("filter_services", False)

    visit_services = []
    if filter_services_flag or ecg_only_flag:
        # Показываем только ЭКГ услуги (для очереди echokg)
        for vs in all_visit_services:
            if hasattr(vs, 'service_id') and vs.service_id:
                service = (
                    db.query(Service)
                    .filter(Service.id == vs.service_id)
                    .first()
                )
                if service and service.queue_tag == 'ecg':
                    visit_services.append(vs)
        if not visit_services:
            logger.warning(
                "get_today_queues: Флаг ecg_only=True, но ЭКГ услуг не найдено для Visit %d",
                visit.id,
            )
            return None
    else:
        # Исключаем ЭКГ услуги (для очереди cardiology)
        for vs in all_visit_services:
            if hasattr(vs, 'service_id') and vs.service_id:
                service = (
                    db.query(Service)
                    .filter(Service.id == vs.service_id)
                    .first()
                )
                if service and service.queue_tag != 'ecg':
                    visit_services.append(vs)
        if not visit_services:
            logger.debug(
                "get_today_queues: Пропущен Visit %d для specialty=%s: содержит только ЭКГ услуги",
                visit.id,
                specialty,
            )
            return None

    # Fallback на все услуги если фильтр пустой
    if not visit_services:
        visit_services = all_visit_services

    services: list = []
    service_codes: list = []
    service_details: list = []
    total_cost = 0.0

    for vs in visit_services:
        service_code_to_use = None
        svc = None
        if hasattr(vs, 'service_id') and vs.service_id:
            svc = (
                db.query(Service)
                .filter(Service.id == vs.service_id)
                .first()
            )
            if svc:
                service_code_to_use = get_service_code(
                    {
                        'service_code': getattr(svc, 'service_code', None),
                    }
                )

        if service_code_to_use:
            services.append(service_code_to_use)
            service_codes.append(service_code_to_use)
        elif vs.name:
            services.append(vs.name)

        if svc:
            service_details.append({
                "id": svc.id,
                "code": service_code_to_use or svc.code,
                "name": svc.name,
                "price": float(svc.price) if svc.price else 0,
            })

        if vs.price:
            total_cost += float(vs.price) * (vs.qty or 1)

    source = getattr(visit, 'source', None) or 'desk'
    entry_status = _VISIT_STATUS_MAPPING.get(visit.status, "waiting")
    discount_mode = _normalize_registration_discount_mode(
        getattr(visit, "discount_mode", None)
    )
    visit_department = getattr(visit, 'department', None)

    return {
        "record_id": record_id,
        "patient_id": patient_id,
        "visit_time": visit_time,
        "patient_name": patient_name,
        "phone": phone,
        "patient_birth_year": patient_birth_year,
        "address": address,
        "services": services,
        "service_codes": service_codes,
        "service_details": service_details,
        "total_cost": total_cost,
        "entry_status": entry_status,
        "discount_mode": discount_mode,
        "source": source,
        "visit_department": visit_department,
    }



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


        # R-22 Phase 5: _same_patient_queue_entry_for_visit_id and _same_patient_queue_entry_for_visit
        # promoted to module-level helpers (take db as first parameter).

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
            has_queue_entry = _same_patient_queue_entry_for_visit(db, visit)
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

            # R-22: ECG detection extracted to helper
            has_ecg, ecg_services_count, non_ecg_services_count = _detect_ecg_services(services)

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
            visit_date = visit.visit_date or today  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
            patient_id = visit.patient_id

            if has_ecg and not has_only_ecg:
                # Визит содержит и ЭКГ и другие услуги - разделяем:
                # 1. Создаем запись для ЭКГ в очередь echokg (только ЭКГ услуги)
                specialty_ecg = "echokg"
                # R-22: ensure ECG queue exists
                _ensure_specialty_queue(queues_by_specialty, specialty_ecg, visit.doctor_id)

                # R-22: created_at extraction moved to helper
                visit_created_at = _get_visit_created_at(visit)

                # ✅ ИСПРАВЛЕНО: Получаем queue_time из связанной записи в queue_entries
                # R-22: queue_time extraction moved to helper
                visit_queue_time = _get_visit_queue_time(db, visit)

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
                # R-22: ensure queue exists
                _ensure_specialty_queue(queues_by_specialty, specialty, visit.doctor_id)
                # R-22: created_at extraction moved to helper
                visit_created_at = _get_visit_created_at(visit)

                # ✅ ИСПРАВЛЕНО: Получаем queue_time из связанной записи в queue_entries
                # R-22: queue_time extraction moved to helper
                visit_queue_time = _get_visit_queue_time(db, visit)

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

                # R-22: ensure queue exists
                _ensure_specialty_queue(queues_by_specialty, specialty, visit.doctor_id)

                # R-22: created_at extraction moved to helper
                visit_created_at = _get_visit_created_at(visit)

                # ✅ ИСПРАВЛЕНО: Получаем queue_time из связанной записи в queue_entries
                # R-22: queue_time extraction moved to helper
                visit_queue_time = _get_visit_queue_time(db, visit)

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
                queue_entry_row = _same_patient_queue_entry_for_visit(db, visit)
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

        # R-22 Phase 3: online entries processing extracted to helper
        _process_online_queue_entries(db, online_entries, visits, queues_by_specialty, seen_visit_ids)

        # R-22 Phase 3: appointment processing extracted to helper
        _process_legacy_appointments(db, appointments, queues_by_specialty, seen_appointment_ids, today)

        # Формируем результат
        result = []
        queue_number = 1
        seen_entry_keys = set()
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

        for specialty, queue_data in queues_by_specialty.items():
            specialty_key = str(specialty or "").strip().lower()
            if department_filter and specialty_key not in department_filter:
                continue

            entries_list = queue_data.get("entries", [])
            if not entries_list:
                continue

            # Сортируем записи по queue_time, затем по created_at
            entries_list.sort(
                key=lambda e: (
                    e.get("queue_time") or e.get("created_at") or datetime.max,
                    e.get("data").id if hasattr(e.get("data"), "id") else 0,
                )
            )

            # R-22 fix: separate output list to avoid in-place mutation during iteration
            entries = []
            for idx, entry in enumerate(entries_list):
                entry_type = entry.get("type")
                entry_data = entry.get("data")
                entry_id_val = getattr(entry_data, "id", "")
                entry_key = f"{entry_type}_{entry_id_val}"
                # R-22 fix: entry_wrapper is alias for entry (used in result serialization)
                entry_wrapper = entry
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
                appointment_date = None  # R-22 fix: для queue_entry lookup
                doctor_id = None  # R-22 fix: для queue_entry lookup

                if entry_type == "visit":
                    # R-22 Phase 8: visit processing extracted to helper
                    _vis = _process_visit_entry(
                        db=db,
                        entry_data=entry_data,
                        entry_wrapper=entry_wrapper,
                        specialty=specialty,
                    )
                    if _vis is None:
                        continue
                    record_id = _vis["record_id"]
                    patient_id = _vis["patient_id"]
                    visit_time = _vis["visit_time"]
                    patient_name = _vis["patient_name"]
                    phone = _vis["phone"]
                    patient_birth_year = _vis["patient_birth_year"]
                    address = _vis["address"]
                    services = _vis["services"]
                    service_codes = _vis["service_codes"]
                    service_details = _vis["service_details"]
                    total_cost = _vis["total_cost"]
                    entry_status = _vis["entry_status"]
                    discount_mode = _vis["discount_mode"]
                    source = _vis["source"]
                    visit_department = _vis["visit_department"]

                elif entry_type == "appointment":
                    # R-22 Phase 6: appointment processing extracted to helper
                    _appt = _process_appointment_entry(
                        db=db,
                        entry_data=entry_data,
                        entry_wrapper=entry_wrapper,
                        today=today,
                    )
                    if _appt is None:
                        continue
                    record_id = _appt["record_id"]
                    patient_id = _appt["patient_id"]
                    appointment_date = _appt["appointment_date"]
                    doctor_id = _appt["doctor_id"]
                    visit_time = _appt["visit_time"]
                    patient_name = _appt["patient_name"]
                    phone = _appt["phone"]
                    patient_birth_year = _appt["patient_birth_year"]
                    address = _appt["address"]
                    services = _appt["services"]
                    service_codes = _appt["service_codes"]
                    total_cost = _appt["total_cost"]
                    entry_status = _appt["entry_status"]
                    discount_mode = _appt["discount_mode"]
                    source = _appt["source"]

                elif entry_type == "online_queue":
                    # R-22 Phase 7: online_queue processing extracted to helper
                    _oqe = _process_online_queue_entry(
                        db=db,
                        entry_data=entry_data,
                        entry_wrapper=entry_wrapper,
                        specialty=specialty,
                    )
                    if _oqe is None:
                        continue
                    record_id = _oqe["record_id"]
                    patient_id = _oqe["patient_id"]
                    patient_name = _oqe["patient_name"]
                    phone = _oqe["phone"]
                    patient_birth_year = _oqe["patient_birth_year"]
                    address = _oqe["address"]
                    entry_status = _oqe["entry_status"]
                    source = _oqe["source"]
                    discount_mode = _oqe["discount_mode"]
                    visit_time = _oqe["visit_time"]
                    services = _oqe["services"]
                    service_codes = _oqe["service_codes"]
                    service_details = _oqe["service_details"]
                    total_cost = _oqe["total_cost"]

                # appointment_id must mean a real Appointment.id for this row.
                # Visit rows do not have an explicit Appointment FK, so a fuzzy
                # patient/date/doctor match can expose an unrelated appointment.
                appointment_id_value = record_id if entry_type == "appointment" else None

                # R-22 Phase 5: queue entry metadata lookup extracted to helper
                queue_entry_number, queue_entry_time, queue_entry_updated_at = _resolve_queue_entry_metadata(
                    db=db,
                    entry_type=entry_type,
                    entry_data=entry_data,
                    entry_wrapper=entry_wrapper,
                    record_id=record_id,
                    patient_id=patient_id,
                    appointment_date=appointment_date,
                    doctor_id=doctor_id,
                    idx=idx,
                )

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
                    if entry_data is None:
                        logger.warning("get_today_queues: appointment entry with None data, skipping")
                        continue
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
                # R-22 Phase 4: entry serialization extracted to helper
                # (can_* flags are computed inside _serialize_queue_entry)
                entries.append(
                    _serialize_queue_entry(
                        entry_type=entry_type,
                        record_id=record_id,
                        source=source,
                        appointment_id_value=appointment_id_value,
                        entry_visit_id=entry_visit_id,
                        queue_entry_number=queue_entry_number,
                        patient_id=patient_id,
                        patient_name=patient_name,
                        patient_birth_year=patient_birth_year,
                        phone=phone,
                        address=address,
                        services=services,
                        service_codes=service_codes,
                        service_details=service_details,
                        entry_wrapper=entry_wrapper,
                        total_cost=total_cost,
                        payment_status=payment_status,
                        payment_type=payment_type,
                        available_actions=available_actions,
                        canonical_status=canonical_status,
                        entry_queue_time=entry_queue_time,
                        entry_updated_at=entry_updated_at,
                        entry_display_time_kind=entry_display_time_kind,
                        visit_time=visit_time,
                        discount_mode=discount_mode,
                        entry_data=entry_data,
                        latest_lab_report=latest_lab_report,
                        entry_department_key=entry_department_key,
                        entry_department=entry_department,
                    )
                )

            # R-22 Phase 4: queue payload construction extracted to helper
            queue_data = _build_queue_payload(
                queue_data=queue_data,
                specialty=specialty,
                queue_number=queue_number,
                entries=entries,
            )

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

    except Exception:
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
        services_by_specialist: dict[int, list[BatchServiceItem]] = {}
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
                queue = (  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
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
