"""
Doctor Treatment Templates - персональная клиническая память врача

Модель для хранения шаблонов лечения, основанных на реальной практике врача.
Учится при подписании EMR, рекомендует по ICD-10 коду.
"""

import hashlib
import re
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class DoctorTreatmentTemplate(Base):
    """
    SQLAlchemy модель для хранения шаблонов лечения врача.

    Принцип: AI = индекс + сортировка, НЕ генерация
    Источник истины — реальная EMR история врача
    """
    __tablename__ = "doctor_treatment_templates"

    id = Column(String(36), primary_key=True)
    doctor_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    icd10_code = Column(String(10), nullable=False, index=True, comment="Код МКБ-10")
    treatment_text = Column(Text, nullable=False, comment="Текст назначения")
    treatment_hash = Column(String(64), nullable=False, comment="SHA256 для дедупликации")
    usage_count = Column(Integer, default=1, nullable=False, comment="Количество использований")
    last_used_at = Column(DateTime, default=func.now(), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Soft delete - врач может "передумать"
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    # Pin support - "Часто использую" (max 3-5 per doctor+diagnosis)
    is_pinned = Column(Boolean, default=False, nullable=False)
    pinned_at = Column(DateTime, nullable=True)

    # Relationship
    doctor = relationship("User", back_populates="treatment_templates", lazy="joined")

    @staticmethod
    def normalize_treatment(text: str) -> str:
        """
        Нормализация текста лечения для дедупликации.

        ВАЖНО: НЕ меняет смысл!
        - Только убираем лишние пробелы
        - НЕ делаем AI-нормализацию
        - НЕ удаляем дозы
        """
        if not text:
            return ""
        text = text.strip()
        # Заменяем множественные пробелы/табы на один пробел
        text = re.sub(r'[ \t]+', ' ', text)
        # Убираем пустые строки и лишние переносы
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)

    @staticmethod
    def compute_hash(normalized_text: str) -> str:
        """Вычислить SHA256 хеш для дедупликации"""
        return hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()


# ============ Pydantic Schemas ============

class DoctorTreatmentTemplateBase(BaseModel):
    """Базовая схема шаблона"""
    icd10_code: str = Field(..., description="Код МКБ-10")
    treatment_text: str = Field(..., description="Текст назначения")


class DoctorTreatmentTemplateResponse(BaseModel):
    """Ответ API - шаблон лечения"""
    id: str
    icd10_code: str
    treatment_text: str
    usage_count: int
    last_used_at: datetime
    is_pinned: bool = False
    frequency_label: str | None = None  # "часто" / "редко" / None
    is_stale: bool = False  # last_used_at > 12 months → 🕒 "Давно не использовал"

    class Config:
        from_attributes = True


class DoctorTreatmentTemplatesListResponse(BaseModel):
    """Список шаблонов для диагноза"""
    source: str = "doctor_history"  # Явно указываем источник
    icd10_code: str
    templates: list[DoctorTreatmentTemplateResponse]
    total: int
