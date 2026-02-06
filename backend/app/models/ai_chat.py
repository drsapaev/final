"""
AI Chat Models - Модели для хранения истории чата с AI.

Обеспечивает:
- Сессии чата (группировка сообщений)
- История сообщений
- Метаданные (провайдер, токены, время)
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class AIChatSession(Base):
    """
    Сессия чата с AI.
    
    Группирует сообщения одного разговора.
    """
    __tablename__ = "ai_chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Владелец сессии
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Заголовок (автогенерируется из первого сообщения)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    # Контекст чата
    context_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # "emr", "lab", "general", "triage"
    context_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # ID связанной сущности (например, emr_id)
    
    # Специальность (для персонализации ответов)
    specialty: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    messages: Mapped[List["AIChatMessage"]] = relationship(
        "AIChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AIChatMessage.created_at"
    )
    
    user = relationship("User", backref="ai_chat_sessions")
    
    def __repr__(self) -> str:
        return f"<AIChatSession {self.id}: {self.title or 'Untitled'}>"


class AIChatMessage(Base):
    """
    Сообщение в AI чате.
    
    Хранит как пользовательские сообщения, так и ответы AI.
    """
    __tablename__ = "ai_chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Связь с сессией
    session_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("ai_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Роль: "user", "assistant", "system"
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Содержимое сообщения
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Метаданные AI ответа (только для role="assistant")
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Оценка пользователя (для обучения)
    user_rating: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # 1-5 звезд
    user_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Флаги
    is_error: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    was_cached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Relationships
    session: Mapped["AIChatSession"] = relationship(
        "AIChatSession", 
        back_populates="messages"
    )
    
    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<AIChatMessage {self.id} ({self.role}): {preview}>"


class AIChatFeedback(Base):
    """
    Обратная связь по AI ответам.
    
    Используется для улучшения качества AI.
    """
    __tablename__ = "ai_chat_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Связь с сообщением
    message_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Кто оставил feedback
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Тип feedback
    feedback_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "helpful", "not_helpful", "incorrect", "inappropriate"
    
    # Детали
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Что было не так (для incorrect)
    correction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    
    def __repr__(self) -> str:
        return f"<AIChatFeedback {self.id}: {self.feedback_type}>"
