"""
Базовый класс для провайдеров платежей
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PaymentStatus:
    """Статусы платежей"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentResult:
    """Результат операции с платежом"""

    def __init__(
        self,
        success: bool,
        payment_id: str = None,
        status: str = None,
        payment_url: str = None,
        error_message: str = None,
        provider_data: Dict[str, Any] = None,
    ):
        self.success = success
        self.payment_id = payment_id
        self.status = status
        self.payment_url = payment_url
        self.error_message = error_message
        self.provider_data = provider_data or {}


class BasePaymentProvider(ABC):
    """Базовый класс для всех провайдеров платежей"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider_name = self.__class__.__name__.replace("Provider", "").lower()

    @abstractmethod
    def create_payment(
        self,
        amount: Decimal,
        currency: str,
        order_id: str,
        description: str,
        return_url: str = None,
        cancel_url: str = None,
        **kwargs,
    ) -> PaymentResult:
        """
        Создание платежа

        Args:
            amount: Сумма платежа
            currency: Валюта (UZS, USD, KZT)
            order_id: ID заказа в системе
            description: Описание платежа
            return_url: URL для возврата после успешной оплаты
            cancel_url: URL для возврата при отмене
            **kwargs: Дополнительные параметры

        Returns:
            PaymentResult: Результат создания платежа
        """
        pass

    @abstractmethod
    def check_payment_status(self, payment_id: str) -> PaymentResult:
        """
        Проверка статуса платежа

        Args:
            payment_id: ID платежа у провайдера

        Returns:
            PaymentResult: Текущий статус платежа
        """
        pass

    @abstractmethod
    def process_webhook(self, webhook_data: Dict[str, Any]) -> PaymentResult:
        """
        Обработка webhook от провайдера

        Args:
            webhook_data: Данные от провайдера

        Returns:
            PaymentResult: Результат обработки
        """
        pass

    def cancel_payment(self, payment_id: str) -> PaymentResult:
        """
        Отмена платежа (опционально)

        Args:
            payment_id: ID платежа у провайдера

        Returns:
            PaymentResult: Результат отмены
        """
        return PaymentResult(
            success=False,
            error_message=f"Отмена платежей не поддерживается провайдером {self.provider_name}",
        )

    def refund_payment(
        self, payment_id: str, amount: Optional[Decimal] = None
    ) -> PaymentResult:
        """
        Возврат платежа (опционально)

        Args:
            payment_id: ID платежа у провайдера
            amount: Сумма возврата (None = полный возврат)

        Returns:
            PaymentResult: Результат возврата
        """
        return PaymentResult(
            success=False,
            error_message=f"Возврат платежей не поддерживается провайдером {self.provider_name}",
        )

    def validate_webhook_signature(
        self, webhook_data: Dict[str, Any], signature: str = None, auth_header: str = None
    ) -> bool:
        """
        Валидация подписи webhook (опционально)

        Args:
            webhook_data: Данные webhook
            signature: Подпись от провайдера (для Click, Kaspi)
            auth_header: Authorization header (для PayMe)

        Returns:
            bool: True если подпись валидна
        """
        logger.warning(f"Валидация подписи не реализована для {self.provider_name}")
        return True

    def format_amount(self, amount: Decimal, currency: str) -> int:
        """
        Форматирование суммы для провайдера

        Args:
            amount: Сумма в десятичном виде
            currency: Валюта

        Returns:
            int: Сумма в копейках/тийинах
        """
        # Большинство провайдеров работают с копейками/тийинами
        return int(amount * 100)

    def parse_amount(self, amount: int, currency: str) -> Decimal:
        """
        Парсинг суммы от провайдера

        Args:
            amount: Сумма в копейках/тийинах
            currency: Валюта

        Returns:
            Decimal: Сумма в десятичном виде
        """
        return Decimal(amount) / 100

    def log_operation(self, operation: str, data: Dict[str, Any]):
        """Логирование операций"""
        logger.info(f"[{self.provider_name.upper()}] {operation}: {data}")

    def log_error(self, operation: str, error: str, data: Dict[str, Any] = None):
        """Логирование ошибок"""
        logger.error(f"[{self.provider_name.upper()}] {operation} ERROR: {error}")
        if data:
            logger.error(f"[{self.provider_name.upper()}] Data: {data}")
