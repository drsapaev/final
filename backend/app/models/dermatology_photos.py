"""
Модели для фото дерматологии
Основа: passport.md стр. 1789-2063
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User


class DermatologyPhoto(Base):
    """Фото для дерматологических пациентов"""

    __tablename__ = "dermatology_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("patients.id", ondelete="RESTRICT"), 
        nullable=False
    )  # ✅ FIX: Medical photos must always belong to a patient (clinical documentation requirement)

    # Категория фото
    category: Mapped[str] = mapped_column(String(20), nullable=False)  # before, after, progress

    # Информация о файле
    filename: Mapped[str] = mapped_column(String(255), nullable=False)  # Уникальное имя файла
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)  # Оригинальное имя
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)  # Путь к файлу
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Путь к миниатюре
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Размер в байтах
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)  # MIME тип

    # Метаданные
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Заметки врача
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Теги (через запятую)

    # Системные поля
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="dermatology_photos")
    uploader: Mapped[Optional["User"]] = relationship("User", foreign_keys=[uploaded_by])
