from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# --- Shared ---
class UserBase(BaseModel):
    username: str = Field(max_length=64)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: str = Field(default="User", max_length=32)  # Admin|Registrar|Doctor|Lab|Cashier|User
    is_active: bool = True


# --- Create/Update ---
class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=128)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: Optional[str] = Field(default=None, max_length=32)
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=128)


# --- Outputs ---
class UserOut(UserBase):
    id: int
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    password_changed_at: Optional[datetime] = None
    email_verified: bool = False