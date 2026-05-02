from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.base import ORMModel


class ServiceCreate(ORMModel):
    code: str | None = Field(default=None, max_length=32)
    name: str = Field(max_length=255)
    department: str | None = Field(default=None, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    price: float = 0.0
    active: bool = True
    department_key: str | None = Field(default=None, max_length=50)


class ServiceUpdate(ORMModel):
    code: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    price: float | None = None
    active: bool | None = None
    department_key: str | None = Field(default=None, max_length=50)


class Service(ORMModel):
    id: int
    code: str | None = Field(default=None, max_length=32)
    name: str = Field(max_length=255)
    department: str | None = Field(default=None, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    price: float
    active: bool
    department_key: str | None = Field(default=None, max_length=50)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ServiceItem(ORMModel):
    id: int
    code: str | None = Field(default=None, max_length=32)
    name: str = Field(max_length=255)
    department: str | None = Field(default=None, max_length=64)
    unit: str | None = Field(default=None, max_length=32)
    price: float
    active: bool
    department_key: str | None = Field(default=None, max_length=50)
    created_at: datetime | None = None
    updated_at: datetime | None = None
