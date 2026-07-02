"""
Схемы для шаблонов EMR
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.base import ORMModel


class EMRTemplateBase(ORMModel):
    """Базовая схема шаблона EMR"""

    name: str = Field(..., max_length=255)
    description: str | None = Field(None, max_length=5000)
    specialty: str = Field(..., max_length=100)
    template_structure: dict[str, Any] = Field(...)
    is_active: bool = True
    is_public: bool = True
    created_by: int | None = None


class EMRTemplateCreate(EMRTemplateBase):
    """Схема создания шаблона EMR"""

    pass


class EMRTemplateUpdate(ORMModel):
    """Схема обновления шаблона EMR"""

    name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=5000)
    specialty: str | None = Field(None, max_length=100)
    template_structure: dict[str, Any] | None = None
    is_active: bool | None = None
    is_public: bool | None = None


class EMRTemplateOut(EMRTemplateBase):
    """Схема вывода шаблона EMR"""

    id: int
    version: int
    created_at: datetime
    updated_at: datetime | None = None


class EMRVersionBase(ORMModel):
    """Базовая схема версии EMR"""

    emr_id: int
    version_data: dict[str, Any] = Field(...)
    version_number: int
    change_type: str = Field(..., max_length=50)
    change_description: str | None = Field(None, max_length=5000)
    changed_by: int | None = None


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
    field_type: str = Field(
        ..., max_length=50
    )  # text, textarea, select, checkbox, date
    label: str = Field(..., max_length=255)
    placeholder: str | None = Field(None, max_length=255)
    required: bool = False
    options: list[str] | None = None  # для select полей
    validation_rules: dict[str, Any] | None = None
    order: int = 0


class EMRTemplateSection(ORMModel):
    """Схема секции шаблона EMR"""

    section_name: str = Field(..., max_length=255)
    section_title: str = Field(..., max_length=255)
    fields: list[EMRTemplateField] = Field(...)
    order: int = 0
    collapsible: bool = False
    required: bool = False


class EMRTemplateStructure(ORMModel):
    """Схема структуры шаблона EMR"""

    template_name: str = Field(..., max_length=255)
    specialty: str = Field(..., max_length=100)
    sections: list[EMRTemplateSection] = Field(...)
    metadata: dict[str, Any] | None = None
