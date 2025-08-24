from __future__ import annotations
from app.schemas.base import ORMModel
from datetime import datetime
from typing import Optional

from pydantic import Field


class ServiceCreate(ORMModel):
    code: Optional[str] = Field(default=None, max_length=32)
    name: str = Field(max_length=255)
    department: Optional[str] = Field(default=None, max_length=64)
    unit: Optional[str] = Field(default=None, max_length=32)
    price: float = 0.0
    active: bool = True


class ServiceUpdate(ORMModel):
    code: Optional[str] = Field(default=None, max_length=32)
    name: Optional[str] = Field(default=None, max_length=255)
    department: Optional[str] = Field(default=None, max_length=64)
    unit: Optional[str] = Field(default=None, max_length=32)
    price: Optional[float] = None
    active: Optional[bool] = None


class ServiceItem(ORMModel):
    id: int
    code: Optional[str] = Field(default=None, max_length=32)
    name: str = Field(max_length=255)
    department: Optional[str] = Field(default=None, max_length=64)
    unit: Optional[str] = Field(default=None, max_length=32)
    price: float
    active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
