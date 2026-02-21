"""
Pydantic schemas for Role management
"""
from datetime import datetime

from pydantic import BaseModel, Field


class RoleBase(BaseModel):
    """Base schema for Role"""
    name: str = Field(..., min_length=1, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    level: int = Field(default=0, ge=0, le=100)
    is_active: bool = True
    is_system: bool = False


class RoleCreate(RoleBase):
    """Schema for creating a new role"""
    pass


class RoleUpdate(BaseModel):
    """Schema for updating a role"""
    display_name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    level: int | None = Field(None, ge=0, le=100)
    is_active: bool | None = None


class RoleResponse(BaseModel):
    """Schema for role response"""
    id: int
    name: str
    display_name: str
    description: str | None = None
    level: int = 0
    is_active: bool = True
    is_system: bool = False
    parent_role_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    """Schema for list of roles response"""
    roles: list[RoleResponse]
    total: int


class RoleOptionResponse(BaseModel):
    """Simplified role for dropdowns (value/label pairs)"""
    value: str  # role.name (e.g., "Admin")
    label: str  # role.display_name (e.g., "Администратор")

    class Config:
        from_attributes = True


class RoleOptionsListResponse(BaseModel):
    """List of role options for dropdowns"""
    options: list[RoleOptionResponse]
