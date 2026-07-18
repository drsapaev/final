"""Split from app.api.v1.endpoints.user_management.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.user_management._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.user_management._helpers import (
    _coerce_json_mapping,
    _normalize_theme,
    router,
)  # noqa: F401


@router.get("/me/preferences", response_model=dict[str, Any])
async def get_current_user_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получить настройки текущего пользователя.
    Используется фронтендом для загрузки EMR preferences.
    """
    try:
        preferences = user_preferences.get_by_user_id(db, current_user.id)

        if not preferences:
            # Возвращаем дефолтные настройки если нет записи
            return {
                "theme": "auto",
                "language": "ru",
                "compact_mode": False,
                "emr_smart_field_mode": "ghost",
                "emr_show_mode_switcher": True,
                "emr_debounce_ms": 500,
                "emr_recent_icd10": [],
                "emr_recent_templates": [],
                "emr_favorite_templates": {},
                "emr_custom_templates": [],
                "security_settings": {},
            }

        # Возвращаем все поля из preferences + EMR-специфичные
        result = {
            "id": preferences.id,
            "user_id": preferences.user_id,
            "theme": _normalize_theme(preferences.theme),
            "language": preferences.language or "ru",
            "timezone": preferences.timezone,
            "compact_mode": preferences.compact_mode or False,
            "sidebar_collapsed": preferences.sidebar_collapsed or False,
        }

        # Добавляем EMR-специфичные поля из JSON или дефолты
        emr_data = _coerce_json_mapping(getattr(preferences, 'emr_settings', None))
        security_settings = _coerce_json_mapping(
            getattr(preferences, 'security_settings', None)
        )

        result.update({
            "emr_smart_field_mode": emr_data.get("emr_smart_field_mode", "ghost"),
            "emr_show_mode_switcher": emr_data.get("emr_show_mode_switcher", True),
            "emr_debounce_ms": emr_data.get("emr_debounce_ms", 500),
            "emr_recent_icd10": emr_data.get("emr_recent_icd10", []),
            "emr_recent_templates": emr_data.get("emr_recent_templates", []),
            "emr_favorite_templates": emr_data.get("emr_favorite_templates", {}),
            "emr_custom_templates": emr_data.get("emr_custom_templates", []),
            "security_settings": security_settings,
        })

        return result

    except Exception as e:
        # Логируем, но возвращаем дефолты вместо 500
        import logging
        logging.warning(f"Failed to get preferences for user {current_user.id}: {e}")
        return {
            "theme": "auto",
            "language": "ru",
            "compact_mode": False,
            "emr_smart_field_mode": "ghost",
            "emr_show_mode_switcher": True,
            "emr_debounce_ms": 500,
            "emr_recent_icd10": [],
            "emr_recent_templates": [],
            "emr_favorite_templates": {},
            "emr_custom_templates": []
        }


@router.put("/me/preferences", response_model=dict[str, Any])
async def update_current_user_preferences(
    preferences_data: UserPreferencesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Обновить настройки текущего пользователя.
    Принимает произвольный JSON с настройками.
    """
    try:
        return UserManagementApiService(db).update_current_user_preferences(
            current_user_id=current_user.id,
            preferences_data=preferences_data.model_dump(exclude_none=True),
        )

    except Exception as e:
        import logging
        logging.error(f"Failed to update preferences for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


