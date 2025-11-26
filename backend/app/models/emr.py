from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class EMR(Base):
    """Электронная Медицинская Карта"""

    __tablename__ = "emr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("appointments.id"), nullable=False, index=True
    )

    # Основные поля EMR
    complaints: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Жалобы
    anamnesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Анамнез
    examination: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Объективный осмотр
    diagnosis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Диагноз
    icd10: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True
    )  # Код МКБ-10
    recommendations: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Рекомендации

    # Процедуры и услуги (JSON массив)
    procedures: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Прикрепленные файлы (JSON массив)
    attachments: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Расширенные поля для специализаций
    vital_signs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Жизненные показатели
    lab_results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Результаты анализов
    imaging_results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Результаты исследований
    medications: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Назначенные препараты
    allergies: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Аллергии
    family_history: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Семейный анамнез
    social_history: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Социальный анамнез
    
    # AI данные
    ai_suggestions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # AI предложения
    ai_confidence: Mapped[Optional[float]] = mapped_column(nullable=True)  # Уверенность AI
    
    # Метаданные
    template_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # ID используемого шаблона
    specialty: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Специализация

    # Статус и метаданные
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    saved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Связи
    # appointment = relationship("Appointment", back_populates="emr")


class Prescription(Base):
    """Рецепт - один на визит"""

    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("appointments.id"), nullable=False, index=True
    )
    emr_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("emr.id"), nullable=False, index=True
    )

    # Препараты (JSON массив)
    medications: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Общие инструкции и заметки
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doctor_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Статус и метаданные
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    saved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    printed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Связи
    # appointment = relationship("Appointment", back_populates="prescription")
    # emr = relationship("EMR", back_populates="prescription")
