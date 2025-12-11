"""
Модели для управления фича-флагами
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class FeatureFlag(Base):
    """
    Модель фича-флага для управления функциональностью системы
    """

    __tablename__ = "feature_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Основная информация
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Состояние флага
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Конфигурация
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)  # Дополнительные настройки флага

    # Метаданные
    category: Mapped[str] = mapped_column(String(50), default="general")  # Категория флага
    environment: Mapped[str] = mapped_column(
        String(20), default="all"
    )  # production, staging, development, all

    # Временные метки
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Аудит
    created_by: Mapped[Optional[str]] = mapped_column(String(100))
    updated_by: Mapped[Optional[str]] = mapped_column(String(100))

    def __repr__(self) -> str:
        return f"<FeatureFlag(key='{self.key}', enabled={self.enabled})>"


class FeatureFlagHistory(Base):
    """
    История изменений фича-флагов для аудита
    """

    __tablename__ = "feature_flag_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Связь с флагом
    flag_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Изменения
    action: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # created, enabled, disabled, updated, deleted
    old_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    new_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    # Метаданные изменения
    changed_by: Mapped[Optional[str]] = mapped_column(String(100))
    changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))  # IPv4/IPv6
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    reason: Mapped[Optional[str]] = mapped_column(Text)  # Причина изменения

    def __repr__(self) -> str:
        return (
            f"<FeatureFlagHistory(flag_key='{self.flag_key}', action='{self.action}')>"
        )
