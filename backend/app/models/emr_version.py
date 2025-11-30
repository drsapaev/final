"""
Модель для версий EMR
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class EMRVersion(Base):
    """Версия EMR для отслеживания изменений"""

    __tablename__ = "emr_version_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    emr_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("emr.id", ondelete="CASCADE"), nullable=False, index=True
    )

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)  # Снимок данных EMR

    # Метаданные изменения
    change_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # created, updated, deleted
    change_description: Mapped[Optional[str]] = mapped_column(
        String(1000), nullable=True
    )
    changed_by: Mapped[int] = mapped_column(Integer, nullable=False)  # ID пользователя
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
