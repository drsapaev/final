"""
Pydantic схемы для сообщений
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class MessageType(str, Enum):
    """Типы сообщений"""
    TEXT = "text"
    VOICE = "voice"


class MessageCreate(BaseModel):
    """Создание нового текстового сообщения"""
    recipient_id: int = Field(..., description="ID получателя")
    content: str = Field(..., min_length=1, max_length=5000, description="Текст сообщения")
    
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


class MessageOut(BaseModel):
    """Вывод сообщения"""
    id: int
    sender_id: int
    recipient_id: int
    message_type: str = "text"  # "text" или "voice"
    content: Optional[str] = None
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None
    
    # Для голосовых сообщений
    file_id: Optional[int] = None
    voice_duration: Optional[int] = None  # секунды
    file_url: Optional[str] = None  # URL для скачивания/стриминга
    
    # Дополнительные поля для UI
    sender_name: Optional[str] = None
    sender_role: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_role: Optional[str] = None
    
    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    """Информация о беседе для списка"""
    user_id: int
    user_name: str
    user_role: str
    last_message: str
    last_message_time: datetime
    unread_count: int
    is_online: bool = False
    
    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """Ответ со списком сообщений"""
    messages: List[MessageOut]
    total: int
    has_more: bool


class ConversationListResponse(BaseModel):
    """Ответ со списком бесед"""
    conversations: List[ConversationOut]
    total_unread: int


class UnreadCountResponse(BaseModel):
    """Ответ с количеством непрочитанных"""
    unread_count: int


class TypingEvent(BaseModel):
    """Событие набора текста"""
    recipient_id: int
    is_typing: bool
