from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.base import ORMModel


class EMRBase(ORMModel):
    """Базовая схема EMR"""

    appointment_id: int
    complaints: str | None = Field(None, max_length=5000)
    anamnesis: str | None = Field(None, max_length=5000)
    examination: str | None = Field(None, max_length=5000)
    diagnosis: str | None = Field(None, max_length=1000)
    icd10: str | None = Field(None, max_length=16)
    recommendations: str | None = Field(None, max_length=5000)
    procedures: list[dict[str, Any]] | None = None
    attachments: list[dict[str, Any]] | None = None

    # Расширенные поля для специализаций
    vital_signs: dict[str, Any] | None = None  # Жизненные показатели
    lab_results: dict[str, Any] | None = None  # Результаты анализов
    imaging_results: dict[str, Any] | None = None  # Результаты исследований
    medications: dict[str, Any] | None = None  # Назначенные препараты
    allergies: dict[str, Any] | None = None  # Аллергии
    family_history: dict[str, Any] | None = None  # Семейный анамнез
    social_history: dict[str, Any] | None = None  # Социальный анамнез

    # AI поля
    ai_suggestions: dict[str, Any] | None = None  # AI предложения
    ai_confidence: float | None = Field(None, ge=0.0, le=1.0)  # Уверенность AI

    # Шаблоны и специализация
    template_id: int | None = None  # ID шаблона
    specialty: str | None = Field(None, max_length=100)  # Специализация

    is_draft: bool = True


class EMRCreate(EMRBase):
    """Схема создания EMR"""

    pass


class EMRUpdate(ORMModel):
    """Схема обновления EMR"""

    complaints: str | None = Field(None, max_length=5000)
    anamnesis: str | None = Field(None, max_length=5000)
    examination: str | None = Field(None, max_length=5000)
    diagnosis: str | None = Field(None, max_length=1000)
    icd10: str | None = Field(None, max_length=16)
    recommendations: str | None = Field(None, max_length=5000)
    procedures: list[dict[str, Any]] | None = None
    attachments: list[dict[str, Any]] | None = None

    # Расширенные поля для специализаций
    vital_signs: dict[str, Any] | None = None
    lab_results: dict[str, Any] | None = None
    imaging_results: dict[str, Any] | None = None
    medications: dict[str, Any] | None = None
    allergies: dict[str, Any] | None = None
    family_history: dict[str, Any] | None = None
    social_history: dict[str, Any] | None = None

    # AI поля
    ai_suggestions: dict[str, Any] | None = None
    ai_confidence: float | None = Field(None, ge=0.0, le=1.0)

    # Шаблоны и специализация
    template_id: int | None = None
    specialty: str | None = Field(None, max_length=100)

    is_draft: bool | None = None


class EMR(EMRBase):
    """Полная схема EMR"""

    id: int
    created_at: datetime
    updated_at: datetime | None = None
    saved_at: datetime | None = None


class MedicationItem(ORMModel):
    """Элемент препарата в рецепте"""

    name: str = Field(..., max_length=200)
    dosage: str = Field(..., max_length=100)
    frequency: str = Field(..., max_length=100)
    duration: str = Field(..., max_length=100)
    instructions: str | None = Field(None, max_length=500)
    quantity: int = Field(default=1, ge=1)


class PrescriptionBase(ORMModel):
    """Базовая схема рецепта"""

    appointment_id: int
    emr_id: int
    medications: list[MedicationItem] | None = None
    instructions: str | None = Field(None, max_length=2000)
    doctor_notes: str | None = Field(None, max_length=1000)
    is_draft: bool = True


class PrescriptionCreate(PrescriptionBase):
    """Схема создания рецепта"""

    pass


class PrescriptionUpdate(ORMModel):
    """Схема обновления рецепта"""

    medications: list[MedicationItem] | None = None
    instructions: str | None = Field(None, max_length=2000)
    doctor_notes: str | None = Field(None, max_length=1000)
    is_draft: bool | None = None


class Prescription(PrescriptionBase):
    """Полная схема рецепта"""

    id: int
    created_at: datetime
    updated_at: datetime | None = None
    saved_at: datetime | None = None
    printed_at: datetime | None = None
