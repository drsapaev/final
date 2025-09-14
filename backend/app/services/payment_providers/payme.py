"""
Интеграция с Payme платежной системой (Узбекистан)
"""
import hashlib
import hmac
import requests
import base64
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime
import json

from .base import BasePaymentProvider, PaymentResult, PaymentStatus

class PaymeProvider(BasePaymentProvider):
    """Провайдер для Payme платежной системы"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Конфигурация Payme
        self.merchant_id = config.get("merchant_id")
        self.secret_key = config.get("secret_key")
        self.base_url = config.get("base_url", "https://checkout.paycom.uz")
        self.api_url = config.get("api_url", "https://api.paycom.uz")
        
        # Валидация конфигурации
        if not all([self.merchant_id, self.secret_key]):
            raise ValueError("Payme: Не все обязательные параметры настроены")
    
    def create_payment(
        self,
        amount: Decimal,
        currency: str,
        order_id: str,
        description: str,
        return_url: str = None,
        cancel_url: str = None,
        **kwargs
    ) -> PaymentResult:
        """Создание платежа в Payme"""
        
        try:
            # Payme работает только с UZS
            if currency != "UZS":
                return PaymentResult(
                    success=False,
                    error_message=f"Payme поддерживает только UZS, получен {currency}"
                )
            
            # Форматируем сумму (в тийинах)
            amount_tiyin = self.format_amount(amount, currency)
            
            # Кодируем параметры для Payme
            params = {
                "m": self.merchant_id,
                "ac.order_id": order_id,
                "a": amount_tiyin,
                "c": return_url or "",
                "cr": cancel_url or ""
            }
            
            # Кодируем параметры в base64
            params_string = ";".join([f"{k}={v}" for k, v in params.items()])
            encoded_params = base64.b64encode(params_string.encode()).decode()
            
            # Формируем URL для оплаты
            payment_url = f"{self.base_url}/{encoded_params}"
            
            self.log_operation("create_payment", {
                "order_id": order_id,
                "amount": str(amount),
                "currency": currency,
                "amount_tiyin": amount_tiyin
            })
            
            return PaymentResult(
                success=True,
                payment_id=order_id,  # Payme использует наш order_id
                status=PaymentStatus.PENDING,
                payment_url=payment_url,
                provider_data={
                    "merchant_id": self.merchant_id,
                    "amount_tiyin": amount_tiyin,
                    "encoded_params": encoded_params
                }
            )
            
        except Exception as e:
            self.log_error("create_payment", str(e), {"order_id": order_id})
            return PaymentResult(
                success=False,
                error_message=f"Ошибка создания платежа Payme: {str(e)}"
            )
    
    def check_payment_status(self, payment_id: str) -> PaymentResult:
        """Проверка статуса платежа в Payme через API"""
        
        try:
            # Payme JSON-RPC API
            url = f"{self.api_url}"
            
            # Подготавливаем запрос
            payload = {
                "method": "GetStatement",
                "params": {
                    "from": 0,  # Начало периода (timestamp)
                    "to": int(datetime.now().timestamp() * 1000),  # Текущее время
                    "account": {
                        "order_id": payment_id
                    }
                },
                "id": 1
            }
            
            # Авторизация через Basic Auth
            auth_string = f"Paycom:{self.secret_key}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Basic {auth_b64}"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if "error" in data:
                error = data["error"]
                self.log_error("check_payment_status", f"Payme API error: {error}")
                return PaymentResult(
                    success=False,
                    error_message=f"Ошибка Payme API: {error.get('message', 'Unknown error')}"
                )
            
            # Анализируем результат
            transactions = data.get("result", {}).get("transactions", [])
            
            if not transactions:
                # Транзакция не найдена - статус pending
                return PaymentResult(
                    success=True,
                    payment_id=payment_id,
                    status=PaymentStatus.PENDING,
                    provider_data={"transactions": []}
                )
            
            # Берем последнюю транзакцию
            last_transaction = transactions[-1]
            payme_status = last_transaction.get("state")
            
            # Маппинг статусов Payme
            status_mapping = {
                1: PaymentStatus.PROCESSING,   # Создана
                2: PaymentStatus.COMPLETED,    # Завершена
                -1: PaymentStatus.CANCELLED,   # Отменена (до завершения)
                -2: PaymentStatus.CANCELLED    # Отменена (после завершения)
            }
            
            our_status = status_mapping.get(payme_status, PaymentStatus.FAILED)
            
            self.log_operation("check_status", {
                "payment_id": payment_id,
                "payme_status": payme_status,
                "our_status": our_status,
                "transaction_count": len(transactions)
            })
            
            return PaymentResult(
                success=True,
                payment_id=payment_id,
                status=our_status,
                provider_data={
                    "transactions": transactions,
                    "last_transaction": last_transaction
                }
            )
            
        except Exception as e:
            self.log_error("check_payment_status", str(e), {"payment_id": payment_id})
            return PaymentResult(
                success=False,
                error_message=f"Ошибка проверки статуса Payme: {str(e)}"
            )
    
    def process_webhook(self, webhook_data: Dict[str, Any]) -> PaymentResult:
        """Обработка webhook от Payme (JSON-RPC)"""
        
        try:
            # Payme использует JSON-RPC протокол
            method = webhook_data.get("method")
            params = webhook_data.get("params", {})
            request_id = webhook_data.get("id")
            
            # Извлекаем данные транзакции
            account = params.get("account", {})
            order_id = account.get("order_id")
            amount = params.get("amount")
            
            # Определяем статус по методу
            status_mapping = {
                "CheckPerformTransaction": PaymentStatus.PENDING,
                "CreateTransaction": PaymentStatus.PROCESSING,
                "PerformTransaction": PaymentStatus.COMPLETED,
                "CancelTransaction": PaymentStatus.CANCELLED
            }
            
            status = status_mapping.get(method, PaymentStatus.PENDING)
            
            # Парсим сумму
            amount_decimal = self.parse_amount(amount, "UZS") if amount else Decimal("0")
            
            self.log_operation("process_webhook", {
                "method": method,
                "order_id": order_id,
                "amount": str(amount_decimal),
                "status": status,
                "request_id": request_id
            })
            
            return PaymentResult(
                success=True,
                payment_id=order_id,
                status=status,
                provider_data={
                    "method": method,
                    "params": params,
                    "request_id": request_id,
                    "amount": amount_decimal
                }
            )
            
        except Exception as e:
            self.log_error("process_webhook", str(e), webhook_data)
            return PaymentResult(
                success=False,
                error_message=f"Ошибка обработки webhook Payme: {str(e)}"
            )
    
    def validate_webhook_signature(
        self, 
        webhook_data: Dict[str, Any], 
        signature: str
    ) -> bool:
        """
        Валидация подписи webhook для Payme
        Payme использует Basic Auth, а не подписи
        """
        # Для Payme валидация происходит через Basic Auth в заголовках
        return True
    
    def cancel_payment(self, payment_id: str) -> PaymentResult:
        """Отмена платежа в Payme"""
        
        try:
            # Payme JSON-RPC API для отмены
            url = f"{self.api_url}"
            
            payload = {
                "method": "CancelTransaction",
                "params": {
                    "account": {
                        "order_id": payment_id
                    },
                    "reason": 1  # Причина отмены (1 = отмена пользователем)
                },
                "id": 1
            }
            
            # Авторизация
            auth_string = f"Paycom:{self.secret_key}"
            auth_bytes = auth_string.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Basic {auth_b64}"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if "error" in data:
                error = data["error"]
                return PaymentResult(
                    success=False,
                    error_message=f"Ошибка отмены Payme: {error.get('message', 'Unknown error')}"
                )
            
            self.log_operation("cancel_payment", {
                "payment_id": payment_id,
                "result": data.get("result")
            })
            
            return PaymentResult(
                success=True,
                payment_id=payment_id,
                status=PaymentStatus.CANCELLED,
                provider_data=data.get("result", {})
            )
            
        except Exception as e:
            self.log_error("cancel_payment", str(e), {"payment_id": payment_id})
            return PaymentResult(
                success=False,
                error_message=f"Ошибка отмены платежа Payme: {str(e)}"
            )
