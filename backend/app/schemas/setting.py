from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SettingRowOut(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=128)
    value: Optional[str] = None


class SettingUpsertIn(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=128)
    value: Optional[str] = None