"""
Схемы для шаблонов EMR
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.schemas.base import ORMModel


class EMRTemplateBase(ORMModel):
    """Базовая схема шаблона EMR"""
    
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    specialty: str = Field(..., max_length=100)
    template_structure: Dict[str, Any] = Field(...)
    is_active: bool = True
    is_public: bool = True
    created_by: Optional[int] = None


class EMRTemplateCreate(EMRTemplateBase):
    """Схема создания шаблона EMR"""
    pass


class EMRTemplateUpdate(ORMModel):
    """Схема обновления шаблона EMR"""
    
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    specialty: Optional[str] = Field(None, max_length=100)
    template_structure: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None


class EMRTemplateOut(EMRTemplateBase):
    """Схема вывода шаблона EMR"""
    
    id: int
    version: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class EMRVersionBase(ORMModel):
    """Базовая схема версии EMR"""
    
    emr_id: int
    version_data: Dict[str, Any] = Field(...)
    version_number: int
    change_type: str = Field(..., max_length=50)
    change_description: Optional[str] = Field(None, max_length=5000)
    changed_by: Optional[int] = None


class EMRVersionCreate(EMRVersionBase):
    """Схема создания версии EMR"""
    pass


class EMRVersionOut(EMRVersionBase):
    """Схема вывода версии EMR"""
    
    id: int
    created_at: datetime


class EMRTemplateField(ORMModel):
    """Схема поля шаблона EMR"""
    
    field_name: str = Field(..., max_length=100)
    field_type: str = Field(..., max_length=50)  # text, textarea, select, checkbox, date
    label: str = Field(..., max_length=255)
    placeholder: Optional[str] = Field(None, max_length=255)
    required: bool = False
    options: Optional[List[str]] = None  # для select полей
    validation_rules: Optional[Dict[str, Any]] = None
    order: int = 0


class EMRTemplateSection(ORMModel):
    """Схема секции шаблона EMR"""
    
    section_name: str = Field(..., max_length=255)
    section_title: str = Field(..., max_length=255)
    fields: List[EMRTemplateField] = Field(...)
    order: int = 0
    collapsible: bool = False
    required: bool = False


class EMRTemplateStructure(ORMModel):
    """Схема структуры шаблона EMR"""
    
    template_name: str = Field(..., max_length=255)
    specialty: str = Field(..., max_length=100)
    sections: List[EMRTemplateSection] = Field(...)
    metadata: Optional[Dict[str, Any]] = None
