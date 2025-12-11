"""
Модели для конфигурации AI в админ панели
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User


class AIProvider(Base):
    """Провайдеры AI (OpenAI, Gemini, DeepSeek и т.д.)"""

    __tablename__ = "ai_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)  # openai, gemini, deepseek
    display_name = Column(String(100), nullable=False)  # OpenAI GPT-4
    api_key = Column(String(200), nullable=True)  # Зашифрованный ключ
    api_url = Column(String(200), nullable=True)  # Базовый URL API
    model = Column(String(100), nullable=True)  # gpt-4, gemini-pro
    temperature = Column(Float, default=0.2, nullable=False)
    max_tokens = Column(Integer, default=1000, nullable=False)
    active = Column(Boolean, default=False, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    capabilities = Column(JSON, nullable=True)  # ["text", "vision", "ocr"]
    limits = Column(
        JSON, nullable=True
    )  # {"requests_per_minute": 60, "tokens_per_day": 10000}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    prompt_templates = relationship("AIPromptTemplate", back_populates="provider")


class AIPromptTemplate(Base):
    """Шаблоны промптов для AI"""

    __tablename__ = "ai_prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("ai_providers.id", ondelete="CASCADE"), nullable=False)
    task_type = Column(
        String(50), nullable=False, index=True
    )  # complaints2plan, icd10, lab_interpret
    specialty = Column(
        String(50), nullable=True, index=True
    )  # cardiology, dermatology, stomatology
    language = Column(String(5), default="ru", nullable=False)  # ru, uz, en
    version = Column(String(20), default="1.0", nullable=False)

    # Промпт компоненты
    system_prompt = Column(Text, nullable=False)
    context_template = Column(Text, nullable=True)
    task_template = Column(Text, nullable=False)
    examples = Column(JSON, nullable=True)  # Примеры для few-shot learning

    # Настройки
    temperature = Column(Float, nullable=True)  # Переопределяет настройки провайдера
    max_tokens = Column(Integer, nullable=True)
    response_schema = Column(JSON, nullable=True)  # JSON Schema для валидации ответа

    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    provider = relationship("AIProvider", back_populates="prompt_templates")


class AIUsageLog(Base):
    """Логи использования AI"""

    __tablename__ = "ai_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # AUDIT INTEGRITY: provider_id должен быть NOT NULL с RESTRICT для сохранения audit trail
    # Провайдер не может быть удален, если существуют логи (пометить как inactive вместо удаления)
    provider_id = Column(Integer, ForeignKey("ai_providers.id", ondelete="RESTRICT"), nullable=False)
    provider_name = Column(String(100), nullable=False)  # Копия имени провайдера для дополнительной защиты
    task_type = Column(String(50), nullable=False, index=True)
    specialty = Column(String(50), nullable=True)

    # Метрики
    tokens_used = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)

    # Контекст
    request_hash = Column(
        String(64), nullable=True, index=True
    )  # Хеш запроса для кэширования
    cached_response = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    provider = relationship("AIProvider", foreign_keys=[provider_id])
