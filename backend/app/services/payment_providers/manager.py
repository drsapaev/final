"""
Менеджер для работы с провайдерами платежей
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from .base import BasePaymentProvider, PaymentResult
from .click import ClickProvider
from .kaspi import KaspiProvider
from .payme import PayMeProvider

logger = logging.getLogger(__name__)


class PaymentProviderManager:
    """Менеджер для управления провайдерами платежей"""

    def __init__(self, config: Dict[str, Dict[str, Any]]):
        """
        Инициализация менеджера

        Args:
            config: Конфигурация провайдеров
            {
                "click": {"service_id": "...", "merchant_id": "...", "secret_key": "..."},
                "payme": {"merchant_id": "...", "secret_key": "..."},
                "kaspi": {"merchant_id": "...", "secret_key": "..."}
            }
        """
        self.providers: Dict[str, BasePaymentProvider] = {}
        self.config = config

        # Инициализируем провайдеры
        self._initialize_providers()

    def _initialize_providers(self):
        """Инициализация всех настроенных провайдеров"""

        provider_classes = {
            "click": ClickProvider,
            "payme": PayMeProvider,
            "kaspi": KaspiProvider,
        }

        for provider_name, provider_class in provider_classes.items():
            provider_config = self.config.get(provider_name)

            if provider_config and provider_config.get("enabled", True):
                try:
                    self.providers[provider_name] = provider_class(provider_config)
                    logger.info(f"Провайдер {provider_name} инициализирован успешно")
                except Exception as e:
                    logger.error(
                        f"Ошибка инициализации провайдера {provider_name}: {e}"
                    )

    def get_provider(self, provider_name: str) -> Optional[BasePaymentProvider]:
        """
        Получение провайдера по имени

        Args:
            provider_name: Имя провайдера (click, payme, kaspi)

        Returns:
            BasePaymentProvider или None
        """
        return self.providers.get(provider_name.lower())

    def get_available_providers(self) -> list[str]:
        """Получение списка доступных провайдеров"""
        return list(self.providers.keys())

    def get_providers_for_currency(self, currency: str) -> list[str]:
        """
        Получение провайдеров, поддерживающих валюту

        Args:
            currency: Код валюты (UZS, KZT, USD)

        Returns:
            Список имен провайдеров
        """
        currency_providers = {
            "UZS": ["click", "payme"],
            "KZT": ["kaspi"],
            "USD": [],  # Пока не поддерживается
        }

        supported_providers = currency_providers.get(currency.upper(), [])
        return [p for p in supported_providers if p in self.providers]

    def create_payment(
        self,
        provider_name: str,
        amount: Decimal,
        currency: str,
        order_id: str,
        description: str,
        return_url: str = None,
        cancel_url: str = None,
        **kwargs,
    ) -> PaymentResult:
        """
        Создание платежа через указанный провайдер

        Args:
            provider_name: Имя провайдера
            amount: Сумма платежа
            currency: Валюта
            order_id: ID заказа
            description: Описание платежа
            return_url: URL возврата при успехе
            cancel_url: URL возврата при отмене
            **kwargs: Дополнительные параметры

        Returns:
            PaymentResult: Результат создания платежа
        """
        provider = self.get_provider(provider_name)

        if not provider:
            return PaymentResult(
                success=False,
                error_message=f"Провайдер {provider_name} не найден или не настроен",
            )

        return provider.create_payment(
            amount=amount,
            currency=currency,
            order_id=order_id,
            description=description,
            return_url=return_url,
            cancel_url=cancel_url,
            **kwargs,
        )

    def check_payment_status(
        self, provider_name: str, payment_id: str
    ) -> PaymentResult:
        """
        Проверка статуса платежа

        Args:
            provider_name: Имя провайдера
            payment_id: ID платежа у провайдера

        Returns:
            PaymentResult: Статус платежа
        """
        provider = self.get_provider(provider_name)

        if not provider:
            return PaymentResult(
                success=False, error_message=f"Провайдер {provider_name} не найден"
            )

        return provider.check_payment_status(payment_id)

    def process_webhook(
        self, provider_name: str, webhook_data: Dict[str, Any]
    ) -> PaymentResult:
        """
        Обработка webhook от провайдера

        Args:
            provider_name: Имя провайдера
            webhook_data: Данные webhook

        Returns:
            PaymentResult: Результат обработки
        """
        provider = self.get_provider(provider_name)

        if not provider:
            return PaymentResult(
                success=False, error_message=f"Провайдер {provider_name} не найден"
            )

        return provider.process_webhook(webhook_data)

    def cancel_payment(self, provider_name: str, payment_id: str) -> PaymentResult:
        """
        Отмена платежа

        Args:
            provider_name: Имя провайдера
            payment_id: ID платежа у провайдера

        Returns:
            PaymentResult: Результат отмены
        """
        provider = self.get_provider(provider_name)

        if not provider:
            return PaymentResult(
                success=False, error_message=f"Провайдер {provider_name} не найден"
            )

        return provider.cancel_payment(payment_id)

    def refund_payment(
        self, provider_name: str, payment_id: str, amount: Decimal = None
    ) -> PaymentResult:
        """
        Возврат платежа

        Args:
            provider_name: Имя провайдера
            payment_id: ID платежа у провайдера
            amount: Сумма возврата (None = полный возврат)

        Returns:
            PaymentResult: Результат возврата
        """
        provider = self.get_provider(provider_name)

        if not provider:
            return PaymentResult(
                success=False, error_message=f"Провайдер {provider_name} не найден"
            )

        return provider.refund_payment(payment_id, amount)

    def validate_webhook_signature(
        self, provider_name: str, webhook_data: Dict[str, Any], signature: str = None, auth_header: str = None
    ) -> bool:
        """
        Валидация подписи webhook

        Args:
            provider_name: Имя провайдера
            webhook_data: Данные webhook
            signature: Подпись от провайдера (для Click, Kaspi)
            auth_header: Authorization header (для PayMe)

        Returns:
            bool: True если подпись валидна
        """
        provider = self.get_provider(provider_name)

        if not provider:
            logger.error(f"Провайдер {provider_name} не найден для валидации подписи")
            return False

        # PayMe uses auth_header, others use signature
        if provider_name.lower() == "payme":
            return provider.validate_webhook_signature(webhook_data, signature, auth_header)
        else:
            return provider.validate_webhook_signature(webhook_data, signature)

    def get_provider_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Получение информации о провайдерах

        Returns:
            Словарь с информацией о каждом провайдере
        """
        info = {}

        for name, provider in self.providers.items():
            info[name] = {
                "name": name,
                "class": provider.__class__.__name__,
                "supported_currencies": self._get_provider_currencies(name),
                "features": self._get_provider_features(provider),
            }

        return info

    def _get_provider_currencies(self, provider_name: str) -> list[str]:
        """Получение поддерживаемых валют для провайдера"""
        currency_map = {"click": ["UZS"], "payme": ["UZS"], "kaspi": ["KZT"]}
        return currency_map.get(provider_name, [])

    def _get_provider_features(self, provider: BasePaymentProvider) -> Dict[str, bool]:
        """Получение поддерживаемых функций провайдера"""
        return {
            "create_payment": True,
            "check_status": True,
            "webhook": True,
            "cancel": hasattr(provider, 'cancel_payment')
            and provider.cancel_payment.__func__ != BasePaymentProvider.cancel_payment,
            "refund": hasattr(provider, 'refund_payment')
            and provider.refund_payment.__func__ != BasePaymentProvider.refund_payment,
        }
