"""
Pydantic схемы для сообщений
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict


class MessageType(str, Enum):
    """Типы сообщений"""
    TEXT = "text"
    VOICE = "voice"


class MessageCreate(BaseModel):
    """Создание нового текстового сообщения"""
    recipient_id: int = Field(..., description="ID получателя")
    content: str = Field(..., min_length=1, max_length=5000, description="Текст сообщения")
    patient_id: int | None = Field(None, description="ID пациента для связи с EMR")

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Сообщение не может быть пустым')
        return v


class VoiceMessageCreate(BaseModel):
    """Создание голосового сообщения"""
    recipient_id: int = Field(..., description="ID получателя")
    patient_id: int | None = Field(None, description="ID пациента для связи с EMR")


class MessageReactionBase(BaseModel):
    """Базовая схема реакции"""
    reaction: str = Field(..., max_length=10, description="Emoji реакции")

class MessageReactionCreate(MessageReactionBase):
    """Создание реакции"""
    pass

class MessageReactionOut(MessageReactionBase):
    """Вывод реакции"""
    id: int
    user_id: int
    user_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageOut(BaseModel):
    """Вывод сообщения"""
    id: int
    sender_id: int
    recipient_id: int
    message_type: str = "text"  # "text" или "voice"
    content: str | None = None
    is_read: bool
    created_at: datetime
    read_at: datetime | None = None

    # Для голосовых сообщений
    file_id: int | None = None
    voice_duration: int | None = None  # секунды
    file_url: str | None = None  # URL для скачивания/стриминга

    # Дополнительные поля для UI
    sender_name: str | None = None
    sender_role: str | None = None
    recipient_name: str | None = None
    recipient_role: str | None = None

    # EMR Integration
    patient_id: int | None = None

    # Реакции
    reactions: list[MessageReactionOut] = []

    model_config = ConfigDict(from_attributes=True)


class ConversationOut(BaseModel):
    """Информация о беседе для списка"""
    user_id: int
    user_name: str
    user_role: str
    last_message: str
    last_message_time: datetime
    unread_count: int
    is_online: bool = False

    model_config = ConfigDict(from_attributes=True)


class MessageListResponse(BaseModel):
    """Ответ со списком сообщений"""
    messages: list[MessageOut]
    total: int
    has_more: bool


class ConversationListResponse(BaseModel):
    """Ответ со списком бесед"""
    conversations: list[ConversationOut]
    total_unread: int


class UnreadCountResponse(BaseModel):
    """Ответ с количеством непрочитанных"""
    unread_count: int


class TypingEvent(BaseModel):
    """Событие набора текста"""
    recipient_id: int
    is_typing: bool
