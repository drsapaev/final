"""
DoctorSectionTemplate Model - Universal section templates

Персональная клиническая память врача по секциям EMR:
- complaints (жалобы)
- anamnesis (анамнез)
- examination (осмотр)
- treatment (лечение)
- recommendations (рекомендации)

Каждый шаблон:
- Привязан к doctor_id
- Имеет section_type
- Может быть привязан к icd10_code (или NULL для общих)
- Учится автоматически при подписании EMR
- Редактируемый врачом
"""

import hashlib
import re
import uuid
from datetime import datetime
from typing import Optional, List, Literal
from enum import Enum

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

from app.db.base_class import Base


class SectionType(str, Enum):
    """EMR Section types"""
    COMPLAINTS = "complaints"
    ANAMNESIS = "anamnesis"
    EXAMINATION = "examination"
    TREATMENT = "treatment"
    RECOMMENDATIONS = "recommendations"


class DoctorSectionTemplate(Base):
    """
    Универсальный шаблон секции EMR врача.
    
    Attributes:
        id: UUID шаблона
        doctor_id: ID врача-владельца
        section_type: Тип секции EMR
        icd10_code: Код МКБ-10 (NULL для общих шаблонов)
        template_text: Текст шаблона
        template_hash: SHA256 хеш нормализованного текста
        usage_count: Счётчик использований
        is_pinned: Закреплён ли шаблон
        pinned_at: Когда закреплён
        last_used_at: Последнее использование
        created_at: Дата создания
    """
    __tablename__ = "doctor_section_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    section_type = Column(String(20), nullable=False, index=True)
    icd10_code = Column(String(10), nullable=True, index=True)  # NULL = general template
    template_text = Column(Text, nullable=False)
    template_hash = Column(String(64), nullable=False)
    usage_count = Column(Integer, default=1, nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    pinned_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    doctor = relationship("User", backref="section_templates")

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize text for comparison.
        Removes extra whitespace, trims, lowercases.
        """
        if not text:
            return ""
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', text.strip())
        # Lowercase for comparison
        return normalized.lower()

    @staticmethod
    def compute_hash(text: str) -> str:
        """
        Compute SHA256 hash of normalized text.
        Used for deduplication.
        """
        normalized = DoctorSectionTemplate.normalize_text(text)
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


# ============== Pydantic Schemas ==============

class DoctorSectionTemplateBase(BaseModel):
    """Base schema for template"""
    section_type: SectionType
    icd10_code: Optional[str] = None
    template_text: str


class DoctorSectionTemplateCreate(DoctorSectionTemplateBase):
    """Schema for creating template"""
    pass


class DoctorSectionTemplateUpdate(BaseModel):
    """Schema for updating template"""
    new_text: str
    mode: Literal["replace", "save_as_new"] = "replace"


class DoctorSectionTemplateResponse(BaseModel):
    """Response schema with all fields"""
    id: str
    section_type: str
    icd10_code: Optional[str] = None
    template_text: str
    usage_count: int = 1
    is_pinned: bool = False
    frequency_label: Optional[str] = None  # "часто" | "редко" | None
    is_stale: bool = False  # True if not used > 12 months
    last_used_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DoctorSectionTemplatesListResponse(BaseModel):
    """Response for list of templates"""
    section_type: str
    icd10_code: Optional[str] = None
    templates: List[DoctorSectionTemplateResponse] = []
    total: int = 0
