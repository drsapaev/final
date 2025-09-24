"""
API для управления настройками платежных провайдеров
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.models.clinic import ClinicSettings
from app.services.payment_providers.click import ClickProvider
from app.services.payment_providers.payme import PayMeProvider
from decimal import Decimal
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================== PYDANTIC МОДЕЛИ =====================

class ProviderConfig(BaseModel):
    enabled: bool = True
    test_mode: bool = True
    
class ClickConfig(ProviderConfig):
    service_id: str = ""
    merchant_id: str = ""
    secret_key: str = ""
    base_url: str = "https://api.click.uz/v2"

class PayMeConfig(ProviderConfig):
    merchant_id: str = ""
    secret_key: str = ""
    base_url: str = "https://checkout.paycom.uz"
    api_url: str = "https://api.paycom.uz"

class PaymentProviderSettings(BaseModel):
    default_provider: str = Field(default="click", pattern="^(click|payme)$")
    enabled_providers: list[str] = Field(default=["click"])
    click: ClickConfig = Field(default_factory=ClickConfig)
    payme: PayMeConfig = Field(default_factory=PayMeConfig)

class TestProviderRequest(BaseModel):
    provider: str = Field(pattern="^(click|payme)$")
    config: Dict[str, Any]

class TestProviderResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================

def get_payment_settings(db: Session) -> PaymentProviderSettings:
    """Получение настроек платежных провайдеров"""
    
    # Получаем настройки из БД
    settings_record = db.query(ClinicSettings).filter(
        ClinicSettings.key == "payment_providers"
    ).first()
    
    if settings_record and settings_record.value:
        try:
            settings_data = json.loads(settings_record.value)
            return PaymentProviderSettings(**settings_data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Ошибка парсинга настроек платежных провайдеров: {e}")
    
    # Возвращаем настройки по умолчанию
    return PaymentProviderSettings()

def save_payment_settings(db: Session, settings: PaymentProviderSettings) -> None:
    """Сохранение настроек платежных провайдеров"""
    
    settings_record = db.query(ClinicSettings).filter(
        ClinicSettings.key == "payment_providers"
    ).first()
    
    settings_json = settings.model_dump_json()
    
    if settings_record:
        settings_record.value = settings_json
    else:
        settings_record = ClinicSettings(
            key="payment_providers",
            value=settings_json,
            description="Настройки платежных провайдеров"
        )
        db.add(settings_record)
    
    db.commit()

# ===================== API ENDPOINTS =====================

@router.get("/admin/payment-provider-settings", response_model=PaymentProviderSettings)
def get_payment_provider_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Получение настроек платежных провайдеров
    """
    return get_payment_settings(db)

@router.post("/admin/payment-provider-settings")
def update_payment_provider_settings(
    settings: PaymentProviderSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Обновление настроек платежных провайдеров
    """
    try:
        # Валидация настроек
        if settings.default_provider not in settings.enabled_providers:
            raise HTTPException(
                status_code=400,
                detail="Провайдер по умолчанию должен быть в списке включённых провайдеров"
            )
        
        if not settings.enabled_providers:
            raise HTTPException(
                status_code=400,
                detail="Должен быть включён хотя бы один провайдер"
            )
        
        # Проверяем, что у включённых провайдеров заполнены обязательные поля
        for provider_name in settings.enabled_providers:
            provider_config = getattr(settings, provider_name, None)
            if not provider_config or not provider_config.enabled:
                continue
                
            if provider_name == "click":
                if not all([
                    provider_config.service_id,
                    provider_config.merchant_id,
                    provider_config.secret_key
                ]):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Для провайдера {provider_name} не заполнены обязательные поля"
                    )
            elif provider_name == "payme":
                if not all([
                    provider_config.merchant_id,
                    provider_config.secret_key
                ]):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Для провайдера {provider_name} не заполнены обязательные поля"
                    )
        
        # Сохраняем настройки
        save_payment_settings(db, settings)
        
        logger.info(f"Настройки платежных провайдеров обновлены пользователем {current_user.username}")
        
        return {"success": True, "message": "Настройки сохранены успешно"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек платежных провайдеров: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@router.post("/admin/test-payment-provider", response_model=TestProviderResponse)
def test_payment_provider(
    test_request: TestProviderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Тестирование настроек платежного провайдера
    """
    try:
        provider_name = test_request.provider
        config = test_request.config
        
        # Проверяем обязательные поля
        if provider_name == "click":
            required_fields = ["service_id", "merchant_id", "secret_key"]
            missing_fields = [field for field in required_fields if not config.get(field)]
            
            if missing_fields:
                return TestProviderResponse(
                    success=False,
                    message=f"Не заполнены обязательные поля: {', '.join(missing_fields)}"
                )
            
            # Создаём провайдер и тестируем
            try:
                provider = ClickProvider({
                    "service_id": config["service_id"],
                    "merchant_id": config["merchant_id"],
                    "secret_key": config["secret_key"],
                    "base_url": config.get("base_url", "https://api.click.uz/v2")
                })
                
                # Тестовый платёж
                result = provider.create_payment(
                    amount=Decimal("1000"),  # 1000 тийин = 10 сум
                    currency="UZS",
                    order_id="test_payment_123",
                    description="Тестовый платёж",
                    return_url="https://example.com/success",
                    cancel_url="https://example.com/cancel"
                )
                
                if result.success:
                    return TestProviderResponse(
                        success=True,
                        message="Тест прошёл успешно. Провайдер настроен корректно.",
                        details={
                            "payment_url_created": bool(result.payment_url),
                            "payment_id": result.payment_id
                        }
                    )
                else:
                    return TestProviderResponse(
                        success=False,
                        message=f"Ошибка создания тестового платежа: {result.error_message}"
                    )
                    
            except Exception as e:
                return TestProviderResponse(
                    success=False,
                    message=f"Ошибка инициализации провайдера: {str(e)}"
                )
        
        elif provider_name == "payme":
            required_fields = ["merchant_id", "secret_key"]
            missing_fields = [field for field in required_fields if not config.get(field)]
            
            if missing_fields:
                return TestProviderResponse(
                    success=False,
                    message=f"Не заполнены обязательные поля: {', '.join(missing_fields)}"
                )
            
            # Создаём провайдер и тестируем
            try:
                provider = PayMeProvider({
                    "merchant_id": config["merchant_id"],
                    "secret_key": config["secret_key"],
                    "base_url": config.get("base_url", "https://checkout.paycom.uz"),
                    "api_url": config.get("api_url", "https://api.paycom.uz")
                })
                
                # Тестовый платёж
                result = provider.create_payment(
                    amount=Decimal("1000"),  # 1000 тийин = 10 сум
                    currency="UZS",
                    order_id="test_payment_123",
                    description="Тестовый платёж",
                    return_url="https://example.com/success",
                    cancel_url="https://example.com/cancel"
                )
                
                if result.success:
                    return TestProviderResponse(
                        success=True,
                        message="Тест прошёл успешно. Провайдер настроен корректно.",
                        details={
                            "payment_url_created": bool(result.payment_url),
                            "payment_id": result.payment_id
                        }
                    )
                else:
                    return TestProviderResponse(
                        success=False,
                        message=f"Ошибка создания тестового платежа: {result.error_message}"
                    )
                    
            except Exception as e:
                return TestProviderResponse(
                    success=False,
                    message=f"Ошибка инициализации провайдера: {str(e)}"
                )
        
        else:
            return TestProviderResponse(
                success=False,
                message=f"Неподдерживаемый провайдер: {provider_name}"
            )
            
    except Exception as e:
        logger.error(f"Ошибка тестирования провайдера {test_request.provider}: {e}")
        return TestProviderResponse(
            success=False,
            message=f"Внутренняя ошибка: {str(e)}"
        )

@router.get("/admin/payment-providers-info")
def get_payment_providers_info(
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Получение информации о доступных провайдерах
    """
    return {
        "available_providers": [
            {
                "name": "click",
                "display_name": "Click",
                "description": "Узбекская платёжная система Click",
                "supported_currencies": ["UZS"],
                "features": ["create_payment", "check_status", "webhook"],
                "required_fields": ["service_id", "merchant_id", "secret_key"],
                "optional_fields": ["base_url"]
            },
            {
                "name": "payme",
                "display_name": "PayMe",
                "description": "Узбекская платёжная система PayMe",
                "supported_currencies": ["UZS"],
                "features": ["create_payment", "check_status", "webhook", "cancel"],
                "required_fields": ["merchant_id", "secret_key"],
                "optional_fields": ["base_url", "api_url"]
            }
        ],
        "default_urls": {
            "click": {
                "production": "https://api.click.uz/v2",
                "test": "https://api.click.uz/v2"
            },
            "payme": {
                "production": {
                    "base_url": "https://checkout.paycom.uz",
                    "api_url": "https://api.paycom.uz"
                },
                "test": {
                    "base_url": "https://checkout.test.paycom.uz",
                    "api_url": "https://api.test.paycom.uz"
                }
            }
        }
    }
