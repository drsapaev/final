"""
Модели для шаблонов EMR
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class EMRTemplate(Base):
    """Шаблон EMR для разных специализаций"""

    __tablename__ = "emr_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Основная информация
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False)  # cardiology, dermatology, dentistry
    
    # Структура шаблона (JSON)
    template_structure: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Настройки
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # ID пользователя
    
    # Метаданные
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class EMRVersion(Base):
    """Версии EMR для отслеживания изменений"""

    __tablename__ = "emr_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    emr_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # Данные версии (JSON)
    version_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    
    # Метаданные версии
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    change_type: Mapped[str] = mapped_column(String(50), nullable=False)  # created, updated, restored
    change_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # ID пользователя
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
