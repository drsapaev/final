from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# Шаблоны уведомлений
class NotificationTemplateBase(BaseModel):
    name: str = Field(..., max_length=100, description="Название шаблона")
    type: str = Field(..., max_length=50, description="Тип уведомления")
    channel: str = Field(..., max_length=20, description="Канал отправки")
    subject: str | None = Field(None, max_length=200, description="Тема (для email)")
    template: str = Field(..., description="Шаблон сообщения")
    is_active: bool = Field(True, description="Активен ли шаблон")


class NotificationTemplateCreate(NotificationTemplateBase):
    pass


class NotificationTemplateUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    type: str | None = Field(None, max_length=50)
    channel: str | None = Field(None, max_length=20)
    subject: str | None = Field(None, max_length=200)
    template: str | None = None
    is_active: bool | None = None


class NotificationTemplate(NotificationTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# История уведомлений
class NotificationHistoryBase(BaseModel):
    recipient_type: str = Field(..., max_length=20, description="Тип получателя")
    recipient_id: int | None = Field(None, description="ID получателя")
    recipient_contact: str = Field(
        ..., max_length=255, description="Контакт получателя"
    )
    notification_type: str = Field(..., max_length=50, description="Тип уведомления")
    channel: str = Field(..., max_length=20, description="Канал отправки")
    template_id: int | None = Field(None, description="ID шаблона")
    subject: str | None = Field(None, max_length=200, description="Тема")
    content: str = Field(..., description="Содержание")
    status: str = Field("pending", max_length=20, description="Статус")
    error_message: str | None = Field(None, description="Сообщение об ошибке")
    related_entity_type: str | None = Field(
        None, max_length=50, description="Тип связанной сущности"
    )
    related_entity_id: int | None = Field(None, description="ID связанной сущности")
    notification_metadata: dict[str, Any] | None = Field(
        None, description="Метаданные"
    )


class NotificationHistoryCreate(NotificationHistoryBase):
    pass


class NotificationHistory(NotificationHistoryBase):
    id: int
    created_at: datetime
    sent_at: datetime | None
    delivered_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# Настройки уведомлений пользователя
class NotificationSettingsBase(BaseModel):
    user_id: int = Field(..., description="ID пользователя")
    user_type: str = Field(..., max_length=20, description="Тип пользователя")
    email_enabled: bool = Field(True, description="Email уведомления")
    sms_enabled: bool = Field(True, description="SMS уведомления")
    telegram_enabled: bool = Field(False, description="Telegram уведомления")
    push_enabled: bool = Field(True, description="Push уведомления")
    appointment_reminders: bool = Field(True, description="Напоминания о записях")
    payment_notifications: bool = Field(True, description="Уведомления об оплате")
    queue_updates: bool = Field(True, description="Обновления очереди")
    system_alerts: bool = Field(True, description="Системные оповещения")


class NotificationSettingsCreate(NotificationSettingsBase):
    pass


class NotificationSettingsUpdate(BaseModel):
    email_enabled: bool | None = None
    sms_enabled: bool | None = None
    telegram_enabled: bool | None = None
    push_enabled: bool | None = None
    appointment_reminders: bool | None = None
    payment_notifications: bool | None = None
    queue_updates: bool | None = None
    system_alerts: bool | None = None


class NotificationSettings(NotificationSettingsBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Запросы для отправки уведомлений
class SendNotificationRequest(BaseModel):
    recipient_type: str = Field(
        ..., description="Тип получателя: patient, doctor, admin"
    )
    recipient_id: int | None = Field(None, description="ID получателя")
    notification_type: str = Field(..., description="Тип уведомления")
    channels: list[str] = Field(["email"], description="Каналы отправки")
    template_data: dict[str, Any] = Field(
        {}, description="Данные для подстановки в шаблон"
    )
    related_entity_type: str | None = Field(
        None, description="Тип связанной сущности"
    )
    related_entity_id: int | None = Field(None, description="ID связанной сущности")
    priority: str = Field("normal", description="Приоритет: low, normal, high, urgent")
    scheduled_at: datetime | None = Field(
        None, description="Время отправки (для отложенных)"
    )


class BulkNotificationRequest(BaseModel):
    recipient_type: str = Field(..., description="Тип получателей")
    recipient_ids: list[int] = Field(..., description="ID получателей")
    notification_type: str = Field(..., description="Тип уведомления")
    channels: list[str] = Field(["email"], description="Каналы отправки")
    template_data: dict[str, Any] = Field({}, description="Общие данные для шаблона")
    priority: str = Field("normal", description="Приоритет")


class NotificationStatusResponse(BaseModel):
    id: int
    status: str
    sent_at: datetime | None
    delivered_at: datetime | None
    error_message: str | None


class NotificationStatsResponse(BaseModel):
    total_sent: int
    successful: int
    failed: int
    pending: int
    by_channel: dict[str, int]
    by_type: dict[str, int]
    recent_activity: list[NotificationHistory]
