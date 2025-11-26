from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# Шаблоны уведомлений
class NotificationTemplateBase(BaseModel):
    name: str = Field(..., max_length=100, description="Название шаблона")
    type: str = Field(..., max_length=50, description="Тип уведомления")
    channel: str = Field(..., max_length=20, description="Канал отправки")
    subject: Optional[str] = Field(None, max_length=200, description="Тема (для email)")
    template: str = Field(..., description="Шаблон сообщения")
    is_active: bool = Field(True, description="Активен ли шаблон")


class NotificationTemplateCreate(NotificationTemplateBase):
    pass


class NotificationTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    type: Optional[str] = Field(None, max_length=50)
    channel: Optional[str] = Field(None, max_length=20)
    subject: Optional[str] = Field(None, max_length=200)
    template: Optional[str] = None
    is_active: Optional[bool] = None


class NotificationTemplate(NotificationTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# История уведомлений
class NotificationHistoryBase(BaseModel):
    recipient_type: str = Field(..., max_length=20, description="Тип получателя")
    recipient_id: Optional[int] = Field(None, description="ID получателя")
    recipient_contact: str = Field(
        ..., max_length=255, description="Контакт получателя"
    )
    notification_type: str = Field(..., max_length=50, description="Тип уведомления")
    channel: str = Field(..., max_length=20, description="Канал отправки")
    template_id: Optional[int] = Field(None, description="ID шаблона")
    subject: Optional[str] = Field(None, max_length=200, description="Тема")
    content: str = Field(..., description="Содержание")
    status: str = Field("pending", max_length=20, description="Статус")
    error_message: Optional[str] = Field(None, description="Сообщение об ошибке")
    related_entity_type: Optional[str] = Field(
        None, max_length=50, description="Тип связанной сущности"
    )
    related_entity_id: Optional[int] = Field(None, description="ID связанной сущности")
    notification_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Метаданные"
    )


class NotificationHistoryCreate(NotificationHistoryBase):
    pass


class NotificationHistory(NotificationHistoryBase):
    id: int
    created_at: datetime
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]

    class Config:
        from_attributes = True


# Настройки уведомлений
class NotificationSettingsBase(BaseModel):
    user_id: int = Field(..., description="ID пользователя")
    user_type: str = Field(..., max_length=20, description="Тип пользователя")
    email_enabled: bool = Field(True, description="Email уведомления включены")
    sms_enabled: bool = Field(True, description="SMS уведомления включены")
    telegram_enabled: bool = Field(False, description="Telegram уведомления включены")
    appointment_reminders: bool = Field(True, description="Напоминания о записях")
    payment_notifications: bool = Field(True, description="Уведомления о платежах")
    queue_updates: bool = Field(True, description="Обновления очереди")
    system_alerts: bool = Field(False, description="Системные оповещения")
    reminder_hours_before: int = Field(
        24, ge=1, le=168, description="За сколько часов напоминать"
    )
    notification_email: Optional[EmailStr] = Field(
        None, description="Email для уведомлений"
    )
    notification_phone: Optional[str] = Field(
        None, max_length=20, description="Телефон для SMS"
    )
    telegram_chat_id: Optional[str] = Field(
        None, max_length=50, description="Telegram chat ID"
    )


class NotificationSettingsCreate(NotificationSettingsBase):
    pass


class NotificationSettingsUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    telegram_enabled: Optional[bool] = None
    appointment_reminders: Optional[bool] = None
    payment_notifications: Optional[bool] = None
    queue_updates: Optional[bool] = None
    system_alerts: Optional[bool] = None
    reminder_hours_before: Optional[int] = Field(None, ge=1, le=168)
    notification_email: Optional[EmailStr] = None
    notification_phone: Optional[str] = Field(None, max_length=20)
    telegram_chat_id: Optional[str] = Field(None, max_length=50)


class NotificationSettings(NotificationSettingsBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Запросы для отправки уведомлений
class SendNotificationRequest(BaseModel):
    recipient_type: str = Field(
        ..., description="Тип получателя: patient, doctor, admin"
    )
    recipient_id: Optional[int] = Field(None, description="ID получателя")
    notification_type: str = Field(..., description="Тип уведомления")
    channels: List[str] = Field(["email"], description="Каналы отправки")
    template_data: Dict[str, Any] = Field(
        {}, description="Данные для подстановки в шаблон"
    )
    related_entity_type: Optional[str] = Field(
        None, description="Тип связанной сущности"
    )
    related_entity_id: Optional[int] = Field(None, description="ID связанной сущности")
    priority: str = Field("normal", description="Приоритет: low, normal, high, urgent")
    scheduled_at: Optional[datetime] = Field(
        None, description="Время отправки (для отложенных)"
    )


class BulkNotificationRequest(BaseModel):
    recipient_type: str = Field(..., description="Тип получателей")
    recipient_ids: List[int] = Field(..., description="ID получателей")
    notification_type: str = Field(..., description="Тип уведомления")
    channels: List[str] = Field(["email"], description="Каналы отправки")
    template_data: Dict[str, Any] = Field({}, description="Общие данные для шаблона")
    priority: str = Field("normal", description="Приоритет")


class NotificationStatusResponse(BaseModel):
    id: int
    status: str
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    error_message: Optional[str]


class NotificationStatsResponse(BaseModel):
    total_sent: int
    successful: int
    failed: int
    pending: int
    by_channel: Dict[str, int]
    by_type: Dict[str, int]
    recent_activity: List[NotificationHistory]
