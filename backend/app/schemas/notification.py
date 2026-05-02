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


class NotificationInboxItem(BaseModel):
    id: str = Field(..., description="Delivery ID used by the frontend")
    delivery_id: str = Field(..., description="Canonical delivery UUID")
    event_id: str = Field(..., description="Canonical event UUID")
    sequence_id: int = Field(..., description="Monotonic inbox cursor")
    notification_type: str = Field(..., description="Canonical notification type")
    event_type: str = Field(..., description="Canonical event type")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification body")
    severity: str = Field(..., description="Severity: info, warning, critical, error")
    priority: str = Field(..., description="Priority: low, normal, high, urgent")
    recipient_type: str = Field(..., description="Recipient scope type")
    recipient_id: int = Field(..., description="Recipient user ID")
    role: str | None = Field(None, description="Derived panel role")
    department_key: str | None = Field(None, description="Derived department key")
    channel: str = Field(..., description="Delivery channel")
    status: str = Field(..., description="Legacy-compatible delivery status")
    delivery_status: str = Field(..., description="Canonical delivery status")
    is_read: bool = Field(False, description="Read flag")
    is_seen: bool = Field(False, description="Seen flag")
    is_archived: bool = Field(False, description="Archived flag")
    correlation_id: str | None = Field(None, description="Correlation ID")
    dedup_key: str = Field(..., description="Deduplication key")
    deep_link: str | None = Field(None, description="Deep link")
    payload_snapshot: dict[str, Any] | None = Field(None, description="Snapshot")
    created_at: datetime
    dispatched_at: datetime | None = None
    first_delivered_at: datetime | None = None
    seen_at: datetime | None = None
    read_at: datetime | None = None
    archived_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class NotificationInboxResponse(BaseModel):
    items: list[NotificationInboxItem]
    total: int
    unread_count: int
    next_cursor: str | None = None
    has_more: bool = False
    cursor: str | None = None
    role: str | None = None
    status: str = "all"


class NotificationUnreadCountResponse(BaseModel):
    total: int
    by_role: dict[str, int]
    by_channel: dict[str, int]
    by_severity: dict[str, int]


class NotificationMutationResponse(BaseModel):
    success: bool = True
    id: str
    delivery_status: str
    unread_count: int
    message: str | None = None


class NotificationStatsItem(BaseModel):
    id: str
    notification_type: str
    status: str
    message: str
    created_at: datetime
    role: str | None = None
    channel: str | None = None
    severity: str | None = None

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
    recent_activity: list[NotificationStatsItem]
