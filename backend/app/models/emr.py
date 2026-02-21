from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class EMR(Base):
    """Электронная Медицинская Карта"""

    __tablename__ = "emr"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("appointments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )  # ✅ FIX: EMR must always reference an appointment (medical documentation requirement)

    # Основные поля EMR
    complaints: Mapped[str | None] = mapped_column(Text, nullable=True)  # Жалобы
    anamnesis: Mapped[str | None] = mapped_column(Text, nullable=True)  # Анамнез
    examination: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Объективный осмотр
    diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)  # Диагноз
    icd10: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )  # Код МКБ-10
    recommendations: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Рекомендации

    # Процедуры и услуги (JSON массив)
    procedures: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Прикрепленные файлы (JSON массив)
    attachments: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Расширенные поля для специализаций
    vital_signs: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Жизненные показатели
    lab_results: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Результаты анализов
    imaging_results: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Результаты исследований
    medications: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Назначенные препараты
    allergies: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Аллергии
    family_history: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Семейный анамнез
    social_history: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Социальный анамнез

    # AI данные
    ai_suggestions: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # AI предложения
    ai_confidence: Mapped[float | None] = mapped_column(
        nullable=True
    )  # Уверенность AI

    # Метаданные
    template_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # ID используемого шаблона
    specialty: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Специализация

    # Статус и метаданные
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    saved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Связи
    # appointment = relationship("Appointment", back_populates="emr")


class Prescription(Base):
    """Рецепт - один на визит"""

    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    appointment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True, index=True
    )  # ✅ SECURITY: SET NULL to preserve prescriptions
    emr_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("emr.id", ondelete="SET NULL"), nullable=True, index=True
    )  # ✅ SECURITY: SET NULL to preserve prescriptions

    # Препараты (JSON массив)
    medications: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Общие инструкции и заметки
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    doctor_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Статус и метаданные
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    saved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    printed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Связи
    # appointment = relationship("Appointment", back_populates="prescription")
    # emr = relationship("EMR", back_populates="prescription")
