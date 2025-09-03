from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import EmailStr, Field

from app.schemas.base import ORMModel  # <-- новый базовый класс


class UserBase(ORMModel):
    username: str
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserOut(UserBase):
    id: int
    role: str
    is_active: bool = True


# --- Create/Update ---
class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=128)


class UserUpdate(ORMModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: Optional[str] = Field(default=None, max_length=32)
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)
