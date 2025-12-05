"""
Интеграция с PayMe платежной системой (Узбекистан)
"""

import base64
import hashlib
import hmac
import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

import requests

from .base import BasePaymentProvider, PaymentResult, PaymentStatus


class PayMeProvider(BasePaymentProvider):
    """Провайдер для PayMe платежной системы"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

        # Конфигурация PayMe
        self.merchant_id = config.get("merchant_id")
        self.secret_key = config.get("secret_key")
        self.base_url = config.get("base_url", "https://checkout.paycom.uz")
        self.api_url = config.get("api_url", "https://api.paycom.uz")

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
                success=False, error_message=f"Ошибка создания платежа PayMe: {str(e)}"
            )

    def check_payment_status(self, payment_id: str) -> PaymentResult:
        """Проверка статуса платежа в PayMe через JSON-RPC API"""

        try:
            # PayMe JSON-RPC API для проверки статуса
            url = f"{self.api_url}"

            # Формируем запрос GetStatement для поиска транзакций
            request_data = {
                "jsonrpc": "2.0",
                "method": "GetStatement",
                "params": {
                    "from": int(
                        (datetime.now().timestamp() - 86400) * 1000
                    ),  # 24 часа назад
                    "to": int(datetime.now().timestamp() * 1000),  # сейчас
                },
                "id": 1,
            }

            # Аутентификация через Basic Auth
            auth_string = f"Paycom:{self.secret_key}"
            auth_header = base64.b64encode(auth_string.encode()).decode()

            headers = {
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                url, json=request_data, headers=headers, timeout=30
            )
            response.raise_for_status()

            data = response.json()

            if "error" in data:
                self.log_error(
                    "check_payment_status",
                    f"PayMe API error: {data['error']}",
                    {"payment_id": payment_id},
                )
                return PaymentResult(
                    success=False, error_message=f"Ошибка PayMe API: {data['error']}"
                )

            # Ищем транзакцию по order_id в account
            transactions = data.get("result", {}).get("transactions", [])
            target_transaction = None

            for transaction in transactions:
                account = transaction.get("account", {})
                if account.get("order_id") == payment_id:
                    target_transaction = transaction
                    break

            if not target_transaction:
                # Транзакция не найдена - возможно еще не создана
                return PaymentResult(
                    success=True,
                    payment_id=payment_id,
                    status=PaymentStatus.PENDING,
                    provider_data={"message": "Transaction not found, still pending"},
                )

            # Маппинг статусов PayMe
            payme_state = target_transaction.get("state", 0)
            status_mapping = {
                1: PaymentStatus.PROCESSING,  # Создана
                2: PaymentStatus.COMPLETED,  # Успешно завершена
                -1: PaymentStatus.CANCELLED,  # Отменена до perform
                -2: PaymentStatus.FAILED,  # Отменена после perform
            }

            our_status = status_mapping.get(payme_state, PaymentStatus.PENDING)

            self.log_operation(
                "check_status",
                {
                    "payment_id": payment_id,
                    "payme_state": payme_state,
                    "our_status": our_status,
                    "transaction_id": target_transaction.get("id"),
                },
            )

            return PaymentResult(
                success=True,
                payment_id=payment_id,
                status=our_status,
                provider_data={
                    "transaction": target_transaction,
                    "payme_transaction_id": target_transaction.get("id"),
                    "state": payme_state,
                },
            )

        except Exception as e:
            self.log_error("check_payment_status", str(e), {"payment_id": payment_id})
            return PaymentResult(
                success=False, error_message=f"Ошибка проверки статуса PayMe: {str(e)}"
            )

    def process_webhook(self, webhook_data: Dict[str, Any]) -> PaymentResult:
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
                success=False, error_message=f"Ошибка обработки webhook PayMe: {str(e)}"
            )

    def validate_webhook_signature(
        self, webhook_data: Dict[str, Any], signature: str = None, auth_header: str = None
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
                self.log_error("validate_webhook_signature", "Invalid Authorization header format", {"header": auth_header[:20]})
                return False
            
            # Декодируем base64
            encoded = auth_header[6:]  # Убираем "Basic "
            decoded = base64.b64decode(encoded).decode('utf-8')
            
            # Проверяем формат "Paycom:secret_key"
            if not decoded.startswith("Paycom:"):
                self.log_error("validate_webhook_signature", "Invalid Basic Auth format", {"decoded": decoded[:20]})
                return False
            
            # Извлекаем secret_key из заголовка
            received_secret = decoded[7:]  # Убираем "Paycom:"
            
            # Сравниваем с нашим secret_key
            if received_secret != self.secret_key:
                self.log_error("validate_webhook_signature", "Secret key mismatch", {})
                return False
            
            self.log_operation("validate_webhook_signature", {"status": "valid"})
            return True
            
        except Exception as e:
            self.log_error("validate_webhook_signature", str(e), {"auth_header": auth_header[:20] if auth_header else None})
            return False

    def _generate_auth_header(self) -> str:
        """Генерация заголовка авторизации для PayMe API"""
        auth_string = f"Paycom:{self.secret_key}"
        return base64.b64encode(auth_string.encode()).decode()

    def cancel_payment(self, payment_id: str) -> PaymentResult:
        """Отмена платежа в PayMe"""

        try:
            # Сначала найдем транзакцию
            status_result = self.check_payment_status(payment_id)

            if not status_result.success:
                return status_result

            transaction_data = status_result.provider_data.get("transaction")
            if not transaction_data:
                return PaymentResult(
                    success=False, error_message="Транзакция не найдена для отмены"
                )

            transaction_id = transaction_data.get("id")
            if not transaction_id:
                return PaymentResult(
                    success=False, error_message="ID транзакции не найден"
                )

            # Отменяем транзакцию через API
            url = f"{self.api_url}"

            request_data = {
                "jsonrpc": "2.0",
                "method": "CancelTransaction",
                "params": {
                    "id": transaction_id,
                    "reason": 1,  # Отмена по инициативе мерчанта
                },
                "id": 1,
            }

            headers = {
                "Authorization": f"Basic {self._generate_auth_header()}",
                "Content-Type": "application/json",
            }

            response = requests.post(
                url, json=request_data, headers=headers, timeout=30
            )
            response.raise_for_status()

            data = response.json()

            if "error" in data:
                return PaymentResult(
                    success=False, error_message=f"Ошибка отмены PayMe: {data['error']}"
                )

            self.log_operation(
                "cancel_payment",
                {"payment_id": payment_id, "transaction_id": transaction_id},
            )

            return PaymentResult(
                success=True,
                payment_id=payment_id,
                status=PaymentStatus.CANCELLED,
                provider_data=data.get("result", {}),
            )

        except Exception as e:
            self.log_error("cancel_payment", str(e), {"payment_id": payment_id})
            return PaymentResult(
                success=False, error_message=f"Ошибка отмены платежа PayMe: {str(e)}"
            )
