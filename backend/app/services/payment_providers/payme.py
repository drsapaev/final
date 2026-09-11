"""
Интеграция с PayMe платежной системой (Узбекистан)
"""

import base64
import hmac
from decimal import Decimal
from typing import Any

from .base import BasePaymentProvider, PaymentResult, PaymentStatus


class PayMeProvider(BasePaymentProvider):
    """Провайдер для PayMe платежной системы"""

    supports_status_check = False

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)

        # Конфигурация PayMe
        self.merchant_id = config.get("merchant_id")
        self.secret_key = config.get("secret_key")
        self.base_url = config.get("base_url", "https://checkout.paycom.uz")

        # Валидация конфигурации
        if not all([self.merchant_id, self.secret_key]):
            raise ValueError("PayMe: Не все обязательные параметры настроены")

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
        """Создание платежа в PayMe"""

        try:
            # PayMe работает только с UZS
            if currency != "UZS":
                return PaymentResult(
                    success=False,
                    error_message=f"PayMe поддерживает только UZS, получен {currency}",
                )

            # Форматируем сумму (в тийинах)
            amount_tiyin = self.format_amount(amount, currency)

            # Параметры для PayMe
            params = {
                "m": self.merchant_id,  # merchant_id
                "ac.order_id": order_id,  # account параметр
                "a": amount_tiyin,  # amount в тийинах
                "c": return_url or "",  # callback URL
                "cr": cancel_url or "",  # cancel/return URL
                "l": "ru",  # язык интерфейса
            }

            # Формируем URL для оплаты
            payment_url = f"{self.base_url}/"
            query_params = "&".join([f"{k}={v}" for k, v in params.items()])
            full_payment_url = f"{payment_url}?{query_params}"

            self.log_operation(
                "create_payment",
                {"order_id": order_id, "amount": str(amount), "currency": currency},
            )

            return PaymentResult(
                success=True,
                payment_id=order_id,  # PayMe использует наш order_id
                status=PaymentStatus.PENDING,
                payment_url=full_payment_url,
                provider_data={
                    "merchant_id": self.merchant_id,
                    "amount_tiyin": amount_tiyin,
                    "account": {"order_id": order_id},
                },
            )

        except Exception as e:
            self.log_error("create_payment", str(e), {"order_id": order_id})
            return PaymentResult(
                success=False, error_message="Внутренняя ошибка"
            )

    def check_payment_status(self, payment_id: str) -> PaymentResult:
        """Keep Checkout status local; Merchant API calls flow Payme -> clinic."""
        return PaymentResult(
            success=False,
            payment_id=payment_id,
            error_message=(
                "Исходящая проверка статуса недоступна для Payme Checkout; "
                "статус обновляется входящими Merchant API запросами"
            ),
            provider_data={"status_source": "merchant_api_webhook"},
        )

    def process_webhook(self, webhook_data: dict[str, Any]) -> PaymentResult:
        """Обработка webhook от PayMe (JSON-RPC методы)"""

        try:
            method = webhook_data.get("method")
            params = webhook_data.get("params", {})

            if not method:
                return PaymentResult(
                    success=False, error_message="Метод не указан в webhook"
                )

            # Извлекаем данные транзакции
            account = params.get("account", {})
            order_id = account.get("order_id")
            amount = params.get("amount")
            transaction_id = params.get("id")

            if not order_id:
                return PaymentResult(
                    success=False, error_message="order_id не найден в account"
                )

            # Определяем статус по методу
            if method == "CheckPerformTransaction":
                # Проверка возможности проведения транзакции
                status = PaymentStatus.PENDING
            elif method == "CreateTransaction":
                # Создание транзакции
                status = PaymentStatus.PROCESSING
            elif method == "PerformTransaction":
                # Проведение транзакции (успешная оплата)
                status = PaymentStatus.COMPLETED
            elif method == "CancelTransaction":
                # Отмена транзакции
                reason = params.get("reason", 0)
                if reason == 1:  # Отмена до perform
                    status = PaymentStatus.CANCELLED
                else:  # Отмена после perform (возврат)
                    status = PaymentStatus.REFUNDED
            else:
                status = PaymentStatus.PENDING

            # Парсим сумму
            amount_decimal = (
                self.parse_amount(amount, "UZS") if amount else Decimal("0")
            )

            self.log_operation(
                "process_webhook",
                {
                    "method": method,
                    "order_id": order_id,
                    "transaction_id": transaction_id,
                    "amount": str(amount_decimal),
                    "status": status,
                },
            )

            return PaymentResult(
                success=True,
                payment_id=order_id,
                status=status,
                provider_data={
                    "method": method,
                    "transaction_id": transaction_id,
                    # Храним сумму в JSON‑совместимом виде (без Decimal)
                    "amount": float(amount_decimal),
                    "params": params,
                },
            )

        except Exception as e:
            self.log_error("process_webhook", str(e), webhook_data)
            return PaymentResult(
                success=False, error_message="Внутренняя ошибка"
            )

    def validate_webhook_signature(
        self, webhook_data: dict[str, Any], signature: str = None, auth_header: str = None
    ) -> bool:
        """
        Валидация webhook PayMe
        PayMe использует Basic Auth в Authorization header для аутентификации webhook

        Args:
            webhook_data: Данные webhook
            signature: Не используется для PayMe (оставлен для совместимости)
            auth_header: Значение заголовка Authorization (формат: "Basic base64(Paycom:secret_key)")

        Returns:
            bool: True если авторизация валидна
        """
        if not auth_header:
            self.log_error("validate_webhook_signature", "Missing Authorization header", webhook_data)
            return False

        try:
            # PayMe использует Basic Auth: "Basic base64(Paycom:secret_key)"
            import base64

            # Проверяем формат Basic Auth
            if not auth_header.startswith("Basic "):
                self.log_error(
                    "validate_webhook_signature",
                    "Invalid Authorization header format",
                    {
                        "header_present": bool(auth_header),
                        "header_scheme": (
                            auth_header.split(" ", 1)[0] if auth_header else None
                        ),
                        "header_length": len(auth_header or ""),
                    },
                )
                return False

            # Декодируем base64
            encoded = auth_header[6:]  # Убираем "Basic "
            decoded = base64.b64decode(encoded).decode('utf-8')

            # Проверяем формат "Paycom:secret_key"
            if not decoded.startswith("Paycom:"):
                self.log_error(
                    "validate_webhook_signature",
                    "Invalid Basic Auth format",
                    {
                        "decoded_present": bool(decoded),
                        "decoded_length": len(decoded or ""),
                    },
                )
                return False

            # Извлекаем secret_key из заголовка
            received_secret = decoded[7:]  # Убираем "Paycom:"

            # Сравниваем с нашим secret_key
            if not hmac.compare_digest(received_secret, self.secret_key or ""):
                self.log_error("validate_webhook_signature", "Secret key mismatch", {})
                return False

            self.log_operation("validate_webhook_signature", {"status": "valid"})
            return True

        except Exception as e:
            self.log_error(
                "validate_webhook_signature",
                str(e),
                {
                    "auth_header_present": bool(auth_header),
                    "auth_header_length": len(auth_header or ""),
                },
            )
            return False

    def _generate_auth_header(self) -> str:
        """Генерация заголовка авторизации для PayMe API"""
        auth_string = f"Paycom:{self.secret_key}"
        return base64.b64encode(auth_string.encode()).decode()
