from __future__ import annotations

from pydantic import EmailStr, Field

from app.schemas.base import ORMModel  # <-- новый базовый класс


class UserBase(ORMModel):
    username: str
    full_name: str | None = None
    email: EmailStr | None = None


class UserOut(UserBase):
    id: int
    role: str
    is_active: bool = True


# --- Create/Update ---
class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=128)


class UserUpdate(ORMModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
