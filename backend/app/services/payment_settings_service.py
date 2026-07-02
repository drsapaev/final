"""Service layer for payment provider settings endpoints."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.repositories.payment_settings_repository import PaymentSettingsRepository
from app.schemas.payment_settings import PaymentProviderSettings
from app.services.payment_providers.click import ClickProvider
from app.services.payment_providers.payme import PayMeProvider

logger = logging.getLogger(__name__)


@dataclass
class PaymentSettingsDomainError(Exception):
    status_code: int
    detail: str


class PaymentSettingsService:
    """Orchestrates payment provider settings operations."""

    SETTINGS_KEY = "payment_providers"
    SETTINGS_DESCRIPTION = "Настройки платежных провайдеров"

    def __init__(self, db):  # type: ignore[no-untyped-def]
        self.repository = PaymentSettingsRepository(db)

    def get_payment_settings(self) -> PaymentProviderSettings:
        settings_record = self.repository.get_by_key(self.SETTINGS_KEY)
        if settings_record and settings_record.value:
            try:
                settings_data = json.loads(settings_record.value)
                return PaymentProviderSettings(**settings_data)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("Ошибка парсинга настроек платежных провайдеров: %s", exc)

        return PaymentProviderSettings()

    def save_payment_settings(
        self, settings: PaymentProviderSettings, *, username: str | None
    ) -> dict[str, Any]:
        self._validate_settings(settings)
        self.repository.save_by_key(
            key=self.SETTINGS_KEY,
            value=settings.model_dump_json(),
            description=self.SETTINGS_DESCRIPTION,
        )
        if username:
            logger.info(
                "Настройки платежных провайдеров обновлены пользователем %s", username
            )
        return {"success": True, "message": "Настройки сохранены успешно"}

    def test_payment_provider(
        self, *, provider_name: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            if provider_name == "click":
                return self._test_click_provider(config)
            if provider_name == "payme":
                return self._test_payme_provider(config)
            return {
                "success": False,
                "message": f"Неподдерживаемый провайдер: {provider_name}",
            }
        except Exception as exc:
            logger.error("Ошибка тестирования провайдера %s: %s", provider_name, exc)
            return {"success": False, "message": f"Внутренняя ошибка: {exc}"}

    @staticmethod
    def get_payment_providers_info() -> dict[str, Any]:
        return {
            "available_providers": [
                {
                    "name": "click",
                    "display_name": "Click",
                    "description": "Узбекская платёжная система Click",
                    "supported_currencies": ["UZS"],
                    "features": ["create_payment", "check_status", "webhook"],
                    "required_fields": ["service_id", "merchant_id", "secret_key"],
                    "optional_fields": ["base_url"],
                },
                {
                    "name": "payme",
                    "display_name": "PayMe",
                    "description": "Узбекская платёжная система PayMe",
                    "supported_currencies": ["UZS"],
                    "features": ["create_payment", "check_status", "webhook", "cancel"],
                    "required_fields": ["merchant_id", "secret_key"],
                    "optional_fields": ["base_url", "api_url"],
                },
            ],
            "default_urls": {
                "click": {
                    "production": "https://api.click.uz/v2",
                    "test": "https://api.click.uz/v2",
                },
                "payme": {
                    "production": {
                        "base_url": "https://checkout.paycom.uz",
                        "api_url": "https://api.paycom.uz",
                    },
                    "test": {
                        "base_url": "https://checkout.test.paycom.uz",
                        "api_url": "https://api.test.paycom.uz",
                    },
                },
            },
        }

    def _validate_settings(self, settings: PaymentProviderSettings) -> None:
        if settings.default_provider not in settings.enabled_providers:
            raise PaymentSettingsDomainError(
                status_code=400,
                detail=(
                    "Провайдер по умолчанию должен быть в списке включённых провайдеров"
                ),
            )

        if not settings.enabled_providers:
            raise PaymentSettingsDomainError(
                status_code=400, detail="Должен быть включён хотя бы один провайдер"
            )

        for provider_name in settings.enabled_providers:
            provider_config = getattr(settings, provider_name, None)
            if not provider_config or not provider_config.enabled:
                continue

            if provider_name == "click":
                if not all(
                    [
                        provider_config.service_id,
                        provider_config.merchant_id,
                        provider_config.secret_key,
                    ]
                ):
                    raise PaymentSettingsDomainError(
                        status_code=400,
                        detail=(
                            f"Для провайдера {provider_name} не заполнены обязательные поля"
                        ),
                    )
            elif provider_name == "payme":
                if not all([provider_config.merchant_id, provider_config.secret_key]):
                    raise PaymentSettingsDomainError(
                        status_code=400,
                        detail=(
                            f"Для провайдера {provider_name} не заполнены обязательные поля"
                        ),
                    )

    def _test_click_provider(self, config: dict[str, Any]) -> dict[str, Any]:
        required_fields = ["service_id", "merchant_id", "secret_key"]
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            return {
                "success": False,
                "message": f"Не заполнены обязательные поля: {', '.join(missing_fields)}",
            }

        try:
            provider = ClickProvider(
                {
                    "service_id": config["service_id"],
                    "merchant_id": config["merchant_id"],
                    "secret_key": config["secret_key"],
                    "base_url": config.get("base_url", "https://api.click.uz/v2"),
                }
            )

            result = provider.create_payment(
                amount=Decimal("1000"),
                currency="UZS",
                order_id="test_payment_123",
                description="Тестовый платёж",
                return_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

            if result.success:
                return {
                    "success": True,
                    "message": "Тест прошёл успешно. Провайдер настроен корректно.",
                    "details": {
                        "payment_url_created": bool(result.payment_url),
                        "payment_id": result.payment_id,
                    },
                }

            return {
                "success": False,
                "message": f"Ошибка создания тестового платежа: {result.error_message}",
            }
        except Exception as exc:
            return {
                "success": False,
                "message": f"Ошибка инициализации провайдера: {exc}",
            }

    def _test_payme_provider(self, config: dict[str, Any]) -> dict[str, Any]:
        required_fields = ["merchant_id", "secret_key"]
        missing_fields = [field for field in required_fields if not config.get(field)]
        if missing_fields:
            return {
                "success": False,
                "message": f"Не заполнены обязательные поля: {', '.join(missing_fields)}",
            }

        try:
            provider = PayMeProvider(
                {
                    "merchant_id": config["merchant_id"],
                    "secret_key": config["secret_key"],
                    "base_url": config.get("base_url", "https://checkout.paycom.uz"),
                    "api_url": config.get("api_url", "https://api.paycom.uz"),
                }
            )

            result = provider.create_payment(
                amount=Decimal("1000"),
                currency="UZS",
                order_id="test_payment_123",
                description="Тестовый платёж",
                return_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

            if result.success:
                return {
                    "success": True,
                    "message": "Тест прошёл успешно. Провайдер настроен корректно.",
                    "details": {
                        "payment_url_created": bool(result.payment_url),
                        "payment_id": result.payment_id,
                    },
                }

            return {
                "success": False,
                "message": f"Ошибка создания тестового платежа: {result.error_message}",
            }
        except Exception as exc:
            return {
                "success": False,
                "message": f"Ошибка инициализации провайдера: {exc}",
            }
