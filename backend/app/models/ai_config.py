"""
Модели для конфигурации AI в админ панели
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User


class AIProvider(Base):
    """Провайдеры AI (OpenAI, Gemini, DeepSeek и т.д.)"""

    __tablename__ = "ai_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # openai, gemini, deepseek
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)  # OpenAI GPT-4
    api_key: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Зашифрованный ключ
    api_url: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Базовый URL API
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # gpt-4, gemini-pro
    temperature: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    capabilities: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)  # ["text", "vision", "ocr"]
    limits: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )  # {"requests_per_minute": 60, "tokens_per_day": 10000}
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    prompt_templates: Mapped[List["AIPromptTemplate"]] = relationship(
        "AIPromptTemplate", back_populates="provider"
    )


class AIPromptTemplate(Base):
    """Шаблоны промптов для AI"""

    __tablename__ = "ai_prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_providers.id", ondelete="CASCADE"), nullable=False
    )
    task_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # complaints2plan, icd10, lab_interpret
    specialty: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )  # cardiology, dermatology, stomatology
    language: Mapped[str] = mapped_column(String(5), default="ru", nullable=False)  # ru, uz, en
    version: Mapped[str] = mapped_column(String(20), default="1.0", nullable=False)

    # Промпт компоненты
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    context_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    task_template: Mapped[str] = mapped_column(Text, nullable=False)
    examples: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)  # Примеры для few-shot learning

    # Настройки
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Переопределяет настройки провайдера
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_schema: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # JSON Schema для валидации ответа

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    provider: Mapped["AIProvider"] = relationship("AIProvider", back_populates="prompt_templates")


class AIUsageLog(Base):
    """Логи использования AI"""

    __tablename__ = "ai_usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # AUDIT INTEGRITY: provider_id должен быть NOT NULL с RESTRICT для сохранения audit trail
    # Провайдер не может быть удален, если существуют логи (пометить как inactive вместо удаления)
    provider_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_providers.id", ondelete="RESTRICT"), nullable=False
    )
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)  # Копия имени провайдера для дополнительной защиты
    task_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    specialty: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Метрики
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Контекст
    request_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )  # Хеш запроса для кэширования
    cached_response: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    provider: Mapped["AIProvider"] = relationship("AIProvider", foreign_keys=[provider_id])
