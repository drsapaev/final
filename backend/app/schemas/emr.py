from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.schemas.base import ORMModel


class EMRBase(ORMModel):
    """Базовая схема EMR"""

    appointment_id: int
    complaints: Optional[str] = Field(None, max_length=5000)
    anamnesis: Optional[str] = Field(None, max_length=5000)
    examination: Optional[str] = Field(None, max_length=5000)
    diagnosis: Optional[str] = Field(None, max_length=1000)
    icd10: Optional[str] = Field(None, max_length=16)
    recommendations: Optional[str] = Field(None, max_length=5000)
    procedures: Optional[List[Dict[str, Any]]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    
    # Расширенные поля для специализаций
    vital_signs: Optional[Dict[str, Any]] = None  # Жизненные показатели
    lab_results: Optional[Dict[str, Any]] = None  # Результаты анализов
    imaging_results: Optional[Dict[str, Any]] = None  # Результаты исследований
    medications: Optional[Dict[str, Any]] = None  # Назначенные препараты
    allergies: Optional[Dict[str, Any]] = None  # Аллергии
    family_history: Optional[Dict[str, Any]] = None  # Семейный анамнез
    social_history: Optional[Dict[str, Any]] = None  # Социальный анамнез
    
    # AI поля
    ai_suggestions: Optional[Dict[str, Any]] = None  # AI предложения
    ai_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)  # Уверенность AI
    
    # Шаблоны и специализация
    template_id: Optional[int] = None  # ID шаблона
    specialty: Optional[str] = Field(None, max_length=100)  # Специализация
    
    is_draft: bool = True


class EMRCreate(EMRBase):
    """Схема создания EMR"""

    pass


class EMRUpdate(ORMModel):
    """Схема обновления EMR"""

    complaints: Optional[str] = Field(None, max_length=5000)
    anamnesis: Optional[str] = Field(None, max_length=5000)
    examination: Optional[str] = Field(None, max_length=5000)
    diagnosis: Optional[str] = Field(None, max_length=1000)
    icd10: Optional[str] = Field(None, max_length=16)
    recommendations: Optional[str] = Field(None, max_length=5000)
    procedures: Optional[List[Dict[str, Any]]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    
    # Расширенные поля для специализаций
    vital_signs: Optional[Dict[str, Any]] = None
    lab_results: Optional[Dict[str, Any]] = None
    imaging_results: Optional[Dict[str, Any]] = None
    medications: Optional[Dict[str, Any]] = None
    allergies: Optional[Dict[str, Any]] = None
    family_history: Optional[Dict[str, Any]] = None
    social_history: Optional[Dict[str, Any]] = None
    
    # AI поля
    ai_suggestions: Optional[Dict[str, Any]] = None
    ai_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    # Шаблоны и специализация
    template_id: Optional[int] = None
    specialty: Optional[str] = Field(None, max_length=100)
    
    is_draft: Optional[bool] = None


class EMR(EMRBase):
    """Полная схема EMR"""

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    saved_at: Optional[datetime] = None


class MedicationItem(ORMModel):
    """Элемент препарата в рецепте"""

    name: str = Field(..., max_length=200)
    dosage: str = Field(..., max_length=100)
    frequency: str = Field(..., max_length=100)
    duration: str = Field(..., max_length=100)
    instructions: Optional[str] = Field(None, max_length=500)
    quantity: int = Field(default=1, ge=1)


class PrescriptionBase(ORMModel):
    """Базовая схема рецепта"""

    appointment_id: int
    emr_id: int
    medications: Optional[List[MedicationItem]] = None
    instructions: Optional[str] = Field(None, max_length=2000)
    doctor_notes: Optional[str] = Field(None, max_length=1000)
    is_draft: bool = True


class PrescriptionCreate(PrescriptionBase):
    """Схема создания рецепта"""

    pass


class PrescriptionUpdate(ORMModel):
    """Схема обновления рецепта"""

    medications: Optional[List[MedicationItem]] = None
    instructions: Optional[str] = Field(None, max_length=2000)
    doctor_notes: Optional[str] = Field(None, max_length=1000)
    is_draft: Optional[bool] = None


class Prescription(PrescriptionBase):
    """Полная схема рецепта"""

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    saved_at: Optional[datetime] = None
    printed_at: Optional[datetime] = None
