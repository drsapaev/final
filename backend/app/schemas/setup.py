from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SetupStatusOut(BaseModel):
    initialized: bool


class SetupClinicIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    address: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=20)
    email: EmailStr | None = None
    timezone: str = Field("Asia/Tashkent", max_length=50)
    logo_url: str | None = Field(None, max_length=500)


class SetupBranchIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str | None = Field(None, min_length=1, max_length=20)
    address: str | None = Field(None, max_length=1000)
    phone: str | None = Field(None, max_length=20)
    email: EmailStr | None = None
    timezone: str = Field("Asia/Tashkent", max_length=50)
    capacity: int = Field(50, ge=1, le=1000)


class SetupAdminIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr


class SetupInitializeIn(BaseModel):
    clinic: SetupClinicIn
    branch: SetupBranchIn
    admin: SetupAdminIn
    activation_key: str | None = Field(None, min_length=8, max_length=64)


class SetupInitializeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    initialized: bool
    branch_id: int
    admin_user_id: int
    activation_applied: bool
