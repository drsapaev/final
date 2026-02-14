"""
API для управления настройками платежных провайдеров
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.schemas.payment_settings import (
    PaymentProviderSettings,
    TestProviderRequest,
    TestProviderResponse,
)
from app.services.payment_settings_service import (
    PaymentSettingsDomainError,
    PaymentSettingsService,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================== API ENDPOINTS =====================


@router.get("/admin/payment-provider-settings", response_model=PaymentProviderSettings)
def get_payment_provider_settings(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """
    Получение настроек платежных провайдеров
    """
    return PaymentSettingsService(db).get_payment_settings()


@router.post("/admin/payment-provider-settings")
def update_payment_provider_settings(
    settings: PaymentProviderSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Обновление настроек платежных провайдеров
    """
    try:
        return PaymentSettingsService(db).save_payment_settings(
            settings,
            username=current_user.username,
        )
    except PaymentSettingsDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек платежных провайдеров: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/admin/test-payment-provider", response_model=TestProviderResponse)
def test_payment_provider(
    test_request: TestProviderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Тестирование настроек платежного провайдера
    """
    try:
        service = PaymentSettingsService(db)
        result = service.test_payment_provider(
            provider_name=test_request.provider,
            config=test_request.config,
        )
        return TestProviderResponse(**result)
    except Exception as e:
        logger.error(f"Ошибка тестирования провайдера {test_request.provider}: {e}")
        return TestProviderResponse(
            success=False, message=f"Внутренняя ошибка: {str(e)}"
        )


@router.get("/admin/payment-providers-info")
def get_payment_providers_info(current_user: User = Depends(require_roles("Admin"))):
    """
    Получение информации о доступных провайдерах
    """
    return PaymentSettingsService.get_payment_providers_info()
