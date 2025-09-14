"""
Интеграция с Kaspi Pay платежной системой (Казахстан)
"""
import hashlib
import hmac
import requests
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime
import json
import uuid

from .base import BasePaymentProvider, PaymentResult, PaymentStatus

class KaspiProvider(BasePaymentProvider):
    """Провайдер для Kaspi Pay платежной системы"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Конфигурация Kaspi
        self.merchant_id = config.get("merchant_id")
        self.secret_key = config.get("secret_key")
        self.base_url = config.get("base_url", "https://kaspi.kz/pay")
        self.api_url = config.get("api_url", "https://api.kaspi.kz/pay/v1")
        
        # Валидация конфигурации
        if not all([self.merchant_id, self.secret_key]):
            raise ValueError("Kaspi: Не все обязательные параметры настроены")
    
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
        """Создание платежа в Kaspi Pay"""
        
        try:
            # Kaspi работает только с KZT
            if currency != "KZT":
                return PaymentResult(
                    success=False,
                    error_message=f"Kaspi поддерживает только KZT, получен {currency}"
                )
            
            # Форматируем сумму (в тенге, без копеек для Kaspi)
            amount_kzt = int(amount)
            
            # Генерируем уникальный ID транзакции
            transaction_id = f"clinic_{order_id}_{uuid.uuid4().hex[:8]}"
            
            # Параметры для Kaspi
            params = {
                "merchant_id": self.merchant_id,
                "amount": amount_kzt,
                "currency": currency,
                "order_id": order_id,
                "transaction_id": transaction_id,
                "description": description[:255],  # Ограничение Kaspi
                "return_url": return_url or "",
                "cancel_url": cancel_url or "",
                "timestamp": int(datetime.now().timestamp())
            }
            
            # Генерируем подпись
            params["signature"] = self._generate_signature(params)
            
            # Формируем URL для оплаты
            payment_url = f"{self.base_url}/payment"
            query_params = "&".join([f"{k}={v}" for k, v in params.items()])
            full_payment_url = f"{payment_url}?{query_params}"
            
            self.log_operation("create_payment", {
                "order_id": order_id,
                "transaction_id": transaction_id,
                "amount": str(amount),
                "currency": currency
            })
            
            return PaymentResult(
                success=True,
                payment_id=transaction_id,
                status=PaymentStatus.PENDING,
                payment_url=full_payment_url,
                provider_data={
                    "merchant_id": self.merchant_id,
                    "transaction_id": transaction_id,
                    "order_id": order_id,
                    "amount_kzt": amount_kzt
                }
            )
            
        except Exception as e:
            self.log_error("create_payment", str(e), {"order_id": order_id})
            return PaymentResult(
                success=False,
                error_message=f"Ошибка создания платежа Kaspi: {str(e)}"
            )
    
    def check_payment_status(self, payment_id: str) -> PaymentResult:
        """Проверка статуса платежа в Kaspi"""
        
        try:
            # Kaspi API для проверки статуса
            url = f"{self.api_url}/payments/{payment_id}/status"
            
            # Подготавливаем заголовки с авторизацией
            timestamp = int(datetime.now().timestamp())
            signature = self._generate_api_signature("GET", url, "", timestamp)
            
            headers = {
                "Content-Type": "application/json",
                "X-Merchant-Id": self.merchant_id,
                "X-Timestamp": str(timestamp),
                "X-Signature": signature
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Маппинг статусов Kaspi
            status_mapping = {
                "CREATED": PaymentStatus.PENDING,
                "PENDING": PaymentStatus.PROCESSING,
                "SUCCESS": PaymentStatus.COMPLETED,
                "FAILED": PaymentStatus.FAILED,
                "CANCELLED": PaymentStatus.CANCELLED,
                "REFUNDED": PaymentStatus.REFUNDED
            }
            
            kaspi_status = data.get("status", "FAILED")
            our_status = status_mapping.get(kaspi_status, PaymentStatus.FAILED)
            
            self.log_operation("check_status", {
                "payment_id": payment_id,
                "kaspi_status": kaspi_status,
                "our_status": our_status
            })
            
            return PaymentResult(
                success=True,
                payment_id=payment_id,
                status=our_status,
                provider_data=data
            )
            
        except Exception as e:
            self.log_error("check_payment_status", str(e), {"payment_id": payment_id})
            return PaymentResult(
                success=False,
                error_message=f"Ошибка проверки статуса Kaspi: {str(e)}"
            )
    
    def process_webhook(self, webhook_data: Dict[str, Any]) -> PaymentResult:
        """Обработка webhook от Kaspi"""
        
        try:
            # Извлекаем данные
            transaction_id = webhook_data.get("transaction_id")
            order_id = webhook_data.get("order_id")
            amount = webhook_data.get("amount")
            currency = webhook_data.get("currency", "KZT")
            status = webhook_data.get("status")
            timestamp = webhook_data.get("timestamp")
            signature = webhook_data.get("signature")
            
            # Валидация подписи
            if not self.validate_webhook_signature(webhook_data, signature):
                self.log_error("process_webhook", "Неверная подпись", webhook_data)
                return PaymentResult(
                    success=False,
                    error_message="Неверная подпись webhook"
                )
            
            # Маппинг статусов
            status_mapping = {
                "SUCCESS": PaymentStatus.COMPLETED,
                "FAILED": PaymentStatus.FAILED,
                "CANCELLED": PaymentStatus.CANCELLED,
                "REFUNDED": PaymentStatus.REFUNDED
            }
            
            our_status = status_mapping.get(status, PaymentStatus.FAILED)
            
            # Парсим сумму
            amount_decimal = Decimal(str(amount)) if amount else Decimal("0")
            
            self.log_operation("process_webhook", {
                "transaction_id": transaction_id,
                "order_id": order_id,
                "status": status,
                "our_status": our_status,
                "amount": str(amount_decimal)
            })
            
            return PaymentResult(
                success=True,
                payment_id=transaction_id,
                status=our_status,
                provider_data={
                    "transaction_id": transaction_id,
                    "order_id": order_id,
                    "amount": amount_decimal,
                    "currency": currency,
                    "kaspi_status": status,
                    "timestamp": timestamp
                }
            )
            
        except Exception as e:
            self.log_error("process_webhook", str(e), webhook_data)
            return PaymentResult(
                success=False,
                error_message=f"Ошибка обработки webhook Kaspi: {str(e)}"
            )
    
    def refund_payment(
        self, 
        payment_id: str, 
        amount: Decimal = None
    ) -> PaymentResult:
        """Возврат платежа в Kaspi"""
        
        try:
            url = f"{self.api_url}/payments/{payment_id}/refund"
            
            # Подготавливаем данные для возврата
            refund_data = {
                "transaction_id": payment_id,
                "refund_id": f"refund_{uuid.uuid4().hex[:8]}",
                "timestamp": int(datetime.now().timestamp())
            }
            
            if amount:
                refund_data["amount"] = int(amount)
            
            # Генерируем подпись
            timestamp = refund_data["timestamp"]
            signature = self._generate_api_signature("POST", url, json.dumps(refund_data), timestamp)
            
            headers = {
                "Content-Type": "application/json",
                "X-Merchant-Id": self.merchant_id,
                "X-Timestamp": str(timestamp),
                "X-Signature": signature
            }
            
            response = requests.post(url, json=refund_data, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            self.log_operation("refund_payment", {
                "payment_id": payment_id,
                "refund_amount": str(amount) if amount else "full",
                "refund_id": refund_data["refund_id"]
            })
            
            return PaymentResult(
                success=True,
                payment_id=payment_id,
                status=PaymentStatus.REFUNDED,
                provider_data=data
            )
            
        except Exception as e:
            self.log_error("refund_payment", str(e), {"payment_id": payment_id})
            return PaymentResult(
                success=False,
                error_message=f"Ошибка возврата платежа Kaspi: {str(e)}"
            )
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Генерация подписи для параметров"""
        
        # Сортируем параметры по ключу (исключая signature)
        sorted_params = sorted(
            [(k, v) for k, v in params.items() if k != "signature"]
        )
        
        # Формируем строку для подписи
        sign_string = "&".join([f"{k}={v}" for k, v in sorted_params])
        sign_string += f"&secret_key={self.secret_key}"
        
        # Генерируем SHA256 хеш
        return hashlib.sha256(sign_string.encode()).hexdigest()
    
    def _generate_api_signature(
        self, 
        method: str, 
        url: str, 
        body: str, 
        timestamp: int
    ) -> str:
        """Генерация подписи для API запросов"""
        
        # Формируем строку для подписи
        sign_string = f"{method}\n{url}\n{body}\n{timestamp}\n{self.secret_key}"
        
        # Генерируем HMAC-SHA256
        return hmac.new(
            self.secret_key.encode(),
            sign_string.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def validate_webhook_signature(
        self, 
        webhook_data: Dict[str, Any], 
        signature: str
    ) -> bool:
        """Валидация подписи webhook"""
        
        # Создаем копию данных без подписи
        data_copy = {k: v for k, v in webhook_data.items() if k != "signature"}
        
        # Генерируем ожидаемую подпись
        expected_signature = self._generate_signature(data_copy)
        
        return signature == expected_signature
