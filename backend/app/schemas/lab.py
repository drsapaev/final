"""
Схемы для лабораторных данных
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class LabResultBase(BaseModel):
    """Базовая схема лабораторного результата"""
    test_code: Optional[str] = Field(None, max_length=64)
    test_name: str = Field(..., max_length=255)
    value: Optional[str] = Field(None, max_length=128)
    unit: Optional[str] = Field(None, max_length=32)
    ref_range: Optional[str] = Field(None, max_length=64)
    abnormal: bool = Field(False)
    notes: Optional[str] = Field(None, max_length=1000)


class LabResultCreate(LabResultBase):
    """Схема для создания лабораторного результата"""
    order_id: int


class LabResultUpdate(BaseModel):
    """Схема для обновления лабораторного результата"""
    test_code: Optional[str] = Field(None, max_length=64)
    test_name: Optional[str] = Field(None, max_length=255)
    value: Optional[str] = Field(None, max_length=128)
    unit: Optional[str] = Field(None, max_length=32)
    ref_range: Optional[str] = Field(None, max_length=64)
    abnormal: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)


class LabResultOut(LabResultBase):
    """Схема для вывода лабораторного результата"""
    id: int
    order_id: int
    created_at: datetime

    class Config:
        from_orm = True


class LabOrderBase(BaseModel):
    """Базовая схема лабораторного заказа"""
    patient_id: Optional[int] = None
    status: str = Field("ordered", max_length=16)
    notes: Optional[str] = Field(None, max_length=1000)


class LabOrderCreate(LabOrderBase):
    """Схема для создания лабораторного заказа"""
    pass


class LabOrderUpdate(BaseModel):
    """Схема для обновления лабораторного заказа"""
    status: Optional[str] = Field(None, max_length=16)
    notes: Optional[str] = Field(None, max_length=1000)


class LabOrderOut(LabOrderBase):
    """Схема для вывода лабораторного заказа"""
    id: int
    visit_id: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_orm = True