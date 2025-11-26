"""
Интеграция с Click платежной системой (Узбекистан)
"""
import hashlib
import hmac
import requests
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime
import json

from .base import BasePaymentProvider, PaymentResult, PaymentStatus

class ClickProvider(BasePaymentProvider):
    """Провайдер для Click платежной системы"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Конфигурация Click
        self.service_id = config.get("service_id")
        self.merchant_id = config.get("merchant_id") 
        self.secret_key = config.get("secret_key")
        self.base_url = config.get("base_url", "https://api.click.uz/v2")
        
        # Валидация конфигурации
        if not all([self.service_id, self.merchant_id, self.secret_key]):
            raise ValueError("Click: Не все обязательные параметры настроены")
    
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
        """Создание платежа в Click"""
        
        try:
            # Click работает только с UZS
            if currency != "UZS":
                return PaymentResult(
                    success=False,
                    error_message=f"Click поддерживает только UZS, получен {currency}"
                )
            
            # Форматируем сумму (в тийинах)
            amount_tiyin = self.format_amount(amount, currency)
            
            # Параметры для Click
            params = {
                "service_id": self.service_id,
                "merchant_id": self.merchant_id,
                "amount": amount_tiyin,
                "transaction_param": order_id,
                "return_url": return_url or "",
                "cancel_url": cancel_url or ""
            }
            
            # Генерируем подпись
            sign_string = f"{params['service_id']}{params['merchant_id']}{params['amount']}{params['transaction_param']}{self.secret_key}"
            params["sign"] = hashlib.md5(sign_string.encode()).hexdigest()
            
            # Формируем URL для оплаты
            payment_url = f"{self.base_url}/services/pay"
            query_params = "&".join([f"{k}={v}" for k, v in params.items()])
            full_payment_url = f"{payment_url}?{query_params}"
            
            self.log_operation("create_payment", {
                "order_id": order_id,
                "amount": str(amount),
                "currency": currency
            })
            
            return PaymentResult(
                success=True,
                payment_id=order_id,  # Click использует наш order_id
                status=PaymentStatus.PENDING,
                payment_url=full_payment_url,
                provider_data={
                    "service_id": self.service_id,
                    "merchant_id": self.merchant_id,
                    "amount_tiyin": amount_tiyin
                }
            )
            
        except Exception as e:
            self.log_error("create_payment", str(e), {"order_id": order_id})
            return PaymentResult(
                success=False,
                error_message=f"Ошибка создания платежа Click: {str(e)}"
            )
    
    def check_payment_status(self, payment_id: str) -> PaymentResult:
        """Проверка статуса платежа в Click"""
        
        try:
            # Click API для проверки статуса
            url = f"{self.base_url}/services/payment/status"
            
            params = {
                "service_id": self.service_id,
                "merchant_id": self.merchant_id,
                "transaction_param": payment_id
            }
            
            # Генерируем подпись для проверки
            sign_string = f"{params['service_id']}{params['merchant_id']}{params['transaction_param']}{self.secret_key}"
            params["sign"] = hashlib.md5(sign_string.encode()).hexdigest()
            
            response = requests.post(url, json=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Маппинг статусов Click
            status_mapping = {
                0: PaymentStatus.PENDING,      # Ожидает оплаты
                1: PaymentStatus.PROCESSING,   # В процессе
                2: PaymentStatus.COMPLETED,    # Успешно
                -1: PaymentStatus.FAILED,      # Ошибка
                -2: PaymentStatus.CANCELLED    # Отменен
            }
            
            click_status = data.get("status", -1)
            our_status = status_mapping.get(click_status, PaymentStatus.FAILED)
            
            self.log_operation("check_status", {
                "payment_id": payment_id,
                "click_status": click_status,
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
                error_message=f"Ошибка проверки статуса Click: {str(e)}"
            )
    
    def process_webhook(self, webhook_data: Dict[str, Any]) -> PaymentResult:
        """Обработка webhook от Click"""
        
        try:
            # Извлекаем данные
            click_trans_id = webhook_data.get("click_trans_id")
            service_id = webhook_data.get("service_id")
            merchant_id = webhook_data.get("merchant_id")
            amount = webhook_data.get("amount")
            action = webhook_data.get("action")
            error = webhook_data.get("error")
            error_note = webhook_data.get("error_note", "")
            sign_time = webhook_data.get("sign_time")
            sign_string = webhook_data.get("sign_string")
            transaction_param = webhook_data.get("merchant_trans_id")
            
            # Валидация подписи
            expected_sign = self._generate_webhook_signature(webhook_data)
            if sign_string != expected_sign:
                self.log_error("process_webhook", "Неверная подпись", webhook_data)
                return PaymentResult(
                    success=False,
                    error_message="Неверная подпись webhook"
                )
            
            # Определяем статус по action и error
            if action == 0:  # prepare
                status = PaymentStatus.PROCESSING
            elif action == 1:  # complete
                if error == 0:
                    status = PaymentStatus.COMPLETED
                else:
                    status = PaymentStatus.FAILED
            else:
                status = PaymentStatus.FAILED
            
            # Парсим сумму
            amount_decimal = self.parse_amount(amount, "UZS") if amount else Decimal("0")
            
            self.log_operation("process_webhook", {
                "click_trans_id": click_trans_id,
                "transaction_param": transaction_param,
                "action": action,
                "error": error,
                "status": status,
                "amount": str(amount_decimal)
            })
            
            return PaymentResult(
                success=True,
                payment_id=transaction_param,
                status=status,
                provider_data={
                    "click_trans_id": click_trans_id,
                    "amount": amount_decimal,
                    "error": error,
                    "error_note": error_note,
                    "action": action
                }
            )
            
        except Exception as e:
            self.log_error("process_webhook", str(e), webhook_data)
            return PaymentResult(
                success=False,
                error_message=f"Ошибка обработки webhook Click: {str(e)}"
            )
    
    def _generate_webhook_signature(self, webhook_data: Dict[str, Any]) -> str:
        """Генерация подписи для webhook"""
        
        # Порядок полей для подписи Click
        fields = [
            "click_trans_id",
            "service_id", 
            "merchant_id",
            "amount",
            "action",
            "error",
            "error_note",
            "sign_time"
        ]
        
        # Собираем строку для подписи
        sign_parts = []
        for field in fields:
            value = webhook_data.get(field, "")
            sign_parts.append(str(value))
        
        sign_parts.append(self.secret_key)
        sign_string = "".join(sign_parts)
        
        return hashlib.md5(sign_string.encode()).hexdigest()
    
    def validate_webhook_signature(
        self, 
        webhook_data: Dict[str, Any], 
        signature: str
    ) -> bool:
        """Валидация подписи webhook"""
        expected_signature = self._generate_webhook_signature(webhook_data)
        return signature == expected_signature
