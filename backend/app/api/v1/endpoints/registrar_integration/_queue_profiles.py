from __future__ import annotations

from typing import Any

from app.api.v1.endpoints.registrar_integration._helpers import *  # noqa

from app.api.v1.endpoints.registrar_integration._helpers import (
    _raise_registrar_internal_error,
)  # noqa: F401
from app.schemas.misc_endpoints import ReorderQueueProfilesRequest


@router.get("/queues/profiles", response_model=dict[str, Any])
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


@router.get("/queues/profiles/public", response_model=dict[str, Any])
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


@router.post("/queues/profiles", response_model=dict[str, Any])
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
            show_on_qr_page=profile_data.show_on_qr_page,
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
                "show_on_qr_page": new_profile.show_on_qr_page,
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


@router.put("/queues/profiles/{profile_key}", response_model=dict[str, Any])
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


@router.delete("/queues/profiles/{profile_key}", response_model=dict[str, Any])
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


@router.post("/queues/profiles/reorder", response_model=dict[str, Any])
def reorder_queue_profiles(
    orders: ReorderQueueProfilesRequest,  # {"profile_key": new_order, ...}
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

