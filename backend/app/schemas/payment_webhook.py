# app/schemas/payment_webhook.py
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class PaymentWebhookBase(BaseModel):
    provider: str = Field(..., description="Провайдер платежей (payme, click, etc.)")
    webhook_id: str = Field(..., description="Уникальный ID вебхука")
    transaction_id: str = Field(..., description="ID транзакции")
    amount: int = Field(..., description="Сумма в тийинах")
    currency: str = Field(default="UZS", description="Валюта")
    visit_id: Optional[int] = Field(None, description="ID визита")
    patient_id: Optional[int] = Field(None, description="ID пациента")


class PaymentWebhookCreate(PaymentWebhookBase):
    raw_data: Dict[str, Any] = Field(..., description="Сырые данные от провайдера")
    signature: Optional[str] = Field(None, description="Подпись для верификации")
    status: str = Field(default="pending", description="Статус обработки")


class PaymentWebhookUpdate(BaseModel):
    status: Optional[str] = Field(None, description="Статус обработки")
    processed_at: Optional[datetime] = Field(None, description="Время обработки")
    error_message: Optional[str] = Field(None, description="Сообщение об ошибке")


class PaymentWebhookOut(PaymentWebhookBase, ORMModel):
    id: int
    status: str
    raw_data: Dict[str, Any]
    signature: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]
    error_message: Optional[str]


class PaymentTransactionBase(BaseModel):
    transaction_id: str = Field(..., description="ID транзакции")
    provider: str = Field(..., description="Провайдер платежей")
    amount: int = Field(..., description="Сумма в тийинах")
    currency: str = Field(default="UZS", description="Валюта")
    commission: int = Field(default=0, description="Комиссия провайдера")
    status: str = Field(default="pending", description="Статус транзакции")
    visit_id: Optional[int] = Field(None, description="ID визита")


class PaymentTransactionCreate(PaymentTransactionBase):
    webhook_id: Optional[int] = Field(None, description="ID вебхука")


class PaymentTransactionUpdate(BaseModel):
    status: Optional[str] = Field(None, description="Статус транзакции")
    commission: Optional[int] = Field(None, description="Комиссия провайдера")


class PaymentTransactionOut(PaymentTransactionBase, ORMModel):
    id: int
    webhook_id: Optional[int]
    created_at: datetime
    updated_at: datetime


class PaymentProviderBase(BaseModel):
    name: str = Field(..., description="Название провайдера")
    code: str = Field(..., description="Код провайдера")
    is_active: bool = Field(default=True, description="Активен ли провайдер")
    webhook_url: Optional[str] = Field(None, description="URL для вебхуков")
    commission_percent: int = Field(default=0, description="Комиссия в процентах")
    min_amount: int = Field(default=0, description="Минимальная сумма")
    max_amount: int = Field(default=100000000, description="Максимальная сумма")


class PaymentProviderCreate(PaymentProviderBase):
    api_key: Optional[str] = Field(None, description="API ключ")
    secret_key: Optional[str] = Field(None, description="Секретный ключ")
    created_at: Optional[datetime] = Field(None, description="Время создания")
    updated_at: Optional[datetime] = Field(None, description="Время обновления")


class PaymentProviderUpdate(BaseModel):
    is_active: Optional[bool] = Field(None, description="Активен ли провайдер")
    webhook_url: Optional[str] = Field(None, description="URL для вебхуков")
    api_key: Optional[str] = Field(None, description="API ключ")
    secret_key: Optional[str] = Field(None, description="Секретный ключ")
    commission_percent: Optional[int] = Field(None, description="Комиссия в процентах")
    min_amount: Optional[int] = Field(None, description="Минимальная сумма")
    max_amount: Optional[int] = Field(None, description="Максимальная сумма")


class PaymentProviderOut(PaymentProviderBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


# Специальные схемы для вебхуков
class PaymeWebhookData(BaseModel):
    """Данные вебхука от Payme"""

    id: str
    state: int = Field(
        ..., description="1 - pending, 2 - paid, -1 - cancelled, -2 - failed"
    )
    amount: int = Field(..., description="Сумма в тийинах")
    time: Optional[int] = Field(None, description="Время транзакции")
    account: Optional[Dict[str, Any]] = Field(None, description="Данные аккаунта")
    create_time: Optional[int] = Field(None, description="Время создания")
    perform_time: Optional[int] = Field(None, description="Время выполнения")
    cancel_time: Optional[int] = Field(None, description="Время отмены")
    reason: Optional[int] = Field(None, description="Причина")
    receivers: Optional[list] = Field(None, description="Получатели")


class ClickWebhookData(BaseModel):
    """Данные вебхука от Click"""

    click_trans_id: str = Field(..., description="ID транзакции Click")
    merchant_trans_id: str = Field(..., description="ID транзакции мерчанта")
    amount: str = Field(..., description="Сумма")
    action: str = Field(..., description="Действие")
    sign_time: str = Field(..., description="Время подписи")
    sign_string: str = Field(..., description="Подпись")
    service_id: Optional[str] = Field(None, description="ID сервиса")
    click_paydoc_id: Optional[str] = Field(None, description="ID документа Click")
    error: Optional[str] = Field(None, description="Ошибка")
    error_note: Optional[str] = Field(None, description="Примечание об ошибке")
