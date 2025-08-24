from __future__ import annotations
from app.schemas.base import ORMModel
from typing import Optional

from pydantic import Field


class SettingRowOut(ORMModel):
    category: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=128)
    value: Optional[str] = None


class SettingUpsertIn(ORMModel):
    category: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=128)
    value: Optional[str] = None
