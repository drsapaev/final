from __future__ import annotations

from typing import Any

from app.api.v1.endpoints.registrar_wizard._cart import BenefitSettingsResponse
from app.api.v1.endpoints.registrar_wizard._helpers import *  # noqa


@router.get("/admin/benefit-settings", summary="Получить настройки льгот", response_model=BenefitSettingsResponse)
def get_benefit_settings(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
) -> BenefitSettingsResponse:
    """
    Получить текущие настройки льгот и повторных визитов
    """
    try:
        # Получаем настройки из базы данных
        settings = {}

        # Окно повторного визита (дни)
        repeat_days_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "repeat_visit_days")
            .first()
        )
        settings['repeat_visit_days'] = (
            int(repeat_days_setting.value) if repeat_days_setting else 21
        )

        # Скидка на повторный визит (%)
        repeat_discount_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "repeat_visit_discount")
            .first()
        )
        settings['repeat_visit_discount'] = (
            int(repeat_discount_setting.value) if repeat_discount_setting else 0
        )

        # Льготные консультации бесплатны
        benefit_free_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "benefit_consultation_free")
            .first()
        )
        settings['benefit_consultation_free'] = (
            bool(benefit_free_setting.value) if benefit_free_setting else True
        )

        # Автоодобрение All Free заявок
        auto_approve_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "all_free_auto_approve")
            .first()
        )
        settings['all_free_auto_approve'] = (
            bool(auto_approve_setting.value) if auto_approve_setting else False
        )

        # Время последнего обновления
        latest_update = (
            db.query(ClinicSettings)
            .filter(
                ClinicSettings.key.in_(
                    [
                        "repeat_visit_days",
                        "repeat_visit_discount",
                        "benefit_consultation_free",
                        "all_free_auto_approve",
                    ]
                )
            )
            .order_by(ClinicSettings.updated_at.desc())
            .first()
        )

        updated_at = latest_update.updated_at if latest_update else datetime.now(UTC)

        return BenefitSettingsResponse(
            repeat_visit_days=settings['repeat_visit_days'],
            repeat_visit_discount=settings['repeat_visit_discount'],
            benefit_consultation_free=settings['benefit_consultation_free'],
            all_free_auto_approve=settings['all_free_auto_approve'],
            updated_at=updated_at,
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/admin/benefit-settings", summary="Обновить настройки льгот", response_model=dict[str, Any])
def update_benefit_settings(
    settings_data: BenefitSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> dict[str, Any]:
    """
    Обновить настройки льгот и повторных визитов
    """
    try:
        # Список настроек для обновления
        settings_to_update = [
            {
                "key": "repeat_visit_days",
                "value": settings_data.repeat_visit_days,
                "description": "Окно повторного визита в днях",
            },
            {
                "key": "repeat_visit_discount",
                "value": settings_data.repeat_visit_discount,
                "description": "Скидка на повторный визит в процентах",
            },
            {
                "key": "benefit_consultation_free",
                "value": settings_data.benefit_consultation_free,
                "description": "Льготные консультации бесплатны",
            },
            {
                "key": "all_free_auto_approve",
                "value": settings_data.all_free_auto_approve,
                "description": "Автоматическое одобрение All Free заявок",
            },
        ]

        # Обновляем каждую настройку
        for setting_data in settings_to_update:
            setting = (
                db.query(ClinicSettings)
                .filter(ClinicSettings.key == setting_data["key"])
                .first()
            )

            if setting:
                # Обновляем существующую настройку
                setting.value = setting_data["value"]
                setting.updated_by = current_user.id
                setting.updated_at = datetime.now(UTC)
            else:
                # Создаём новую настройку
                setting = ClinicSettings(
                    key=setting_data["key"],
                    value=setting_data["value"],
                    category="benefits",
                    description=setting_data["description"],
                    updated_by=current_user.id,
                )
                db.add(setting)

        db.commit()

        return {
            "success": True,
            "message": "Настройки льгот обновлены успешно",
            "settings": {
                "repeat_visit_days": settings_data.repeat_visit_days,
                "repeat_visit_discount": settings_data.repeat_visit_discount,
                "benefit_consultation_free": settings_data.benefit_consultation_free,
                "all_free_auto_approve": settings_data.all_free_auto_approve,
            },
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ==================== НАСТРОЙКИ МАСТЕРА РЕГИСТРАЦИИ ====================


class WizardSettingsResponse(BaseModel):
    use_new_wizard: bool
    updated_at: datetime


class WizardSettingsRequest(BaseModel):
    use_new_wizard: bool = Field(
        default=False, description="Использовать новый мастер регистрации"
    )


@router.get("/admin/wizard-settings", summary="Получить настройки мастера регистрации", response_model=dict[str, Any])
def get_wizard_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """Получить настройки мастера регистрации"""
    try:
        # Получаем настройку использования нового мастера
        use_new_wizard_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "wizard_use_new_version")
            .first()
        )

        use_new_wizard = False
        updated_at = datetime.now(UTC)

        if use_new_wizard_setting:
            use_new_wizard = (
                use_new_wizard_setting.value.get("enabled", False)
                if use_new_wizard_setting.value
                else False
            )
            updated_at = use_new_wizard_setting.updated_at or updated_at

        return WizardSettingsResponse(
            use_new_wizard=use_new_wizard, updated_at=updated_at
        )

    except Exception as e:
        logger.error(f"Error getting wizard settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при получении настроек мастера",
        )


@router.post("/admin/wizard-settings", summary="Обновить настройки мастера регистрации", response_model=dict[str, Any])
def update_wizard_settings(
    settings_data: WizardSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Обновить настройки мастера регистрации"""
    try:
        # Обновляем или создаем настройку
        use_new_wizard_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "wizard_use_new_version")
            .first()
        )

        if not use_new_wizard_setting:
            use_new_wizard_setting = ClinicSettings(
                key="wizard_use_new_version",
                category="wizard",
                description="Использовать новый мастер регистрации вместо старого",
            )
            db.add(use_new_wizard_setting)

        use_new_wizard_setting.value = {
            "enabled": settings_data.use_new_wizard,
            "updated_by": current_user.id,
        }
        use_new_wizard_setting.updated_by = current_user.id
        use_new_wizard_setting.updated_at = datetime.now(UTC)

        db.commit()
        db.refresh(use_new_wizard_setting)

        settings_response = WizardSettingsResponse(
            use_new_wizard=settings_data.use_new_wizard,
            updated_at=use_new_wizard_setting.updated_at,
        )

        return {
            "success": True,
            "message": f"Настройки мастера обновлены. {'Включен новый мастер' if settings_data.use_new_wizard else 'Включен старый мастер'}",
            "settings": settings_response,
        }

    except Exception as e:
        logger.error(f"Error updating wizard settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при обновлении настроек мастера",
        )


# ===================== ЭНДПОИНТ ДЛЯ ПОЛУЧЕНИЯ ЗАПИСЕЙ ИЗ VISITS =====================


class VisitResponse(BaseModel):
    id: int
    patient_id: int
    patient_fio: str | None = None
    patient_phone: str | None = None
    doctor_id: int | None = None
    doctor_name: str | None = None
    doctor_specialty: str | None = None
    department: str | None = None
    visit_date: date | None = None
    visit_time: str | None = None
    status: str
    discount_mode: str
    approval_status: str
    services: list[str] | None = None
    notes: str | None = None
    created_at: datetime

