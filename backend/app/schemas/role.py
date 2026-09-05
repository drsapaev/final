"""
Pydantic schemas for Role management
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    # M-2b (Codex review P2 follow-up on #3049): reject the retired RBAC
    # spellings at the schema boundary — a hand-created catalog row named
    # 'Manager' (or 'Receptionist') would flow into /roles/options and the
    # UserModal dropdown mirror, offering a spelling the user-management
    # write schema then rejects with 422. Case-insensitive (catalog names
    # are free-form; the retired set lives in core/roles.py SSOT).
    @field_validator("name")
    @classmethod
    def validate_name_not_retired(cls, v: str) -> str:
        from app.core.roles import is_retired_role_spelling

        if is_retired_role_spelling(v):
            raise ValueError(
                "Роль выведена из эксплуатации (retired spelling): используйте"
                " канонический словарь ролей"
            )
        return v


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

    model_config = ConfigDict(from_attributes=True)


class RoleListResponse(BaseModel):
    """Schema for list of roles response"""
    roles: list[RoleResponse]
    total: int


class RoleOptionResponse(BaseModel):
    """Simplified role for dropdowns (value/label pairs)"""
    value: str  # role.name (e.g., "Admin")
    label: str  # role.display_name (e.g., "Администратор")

    model_config = ConfigDict(from_attributes=True)


class RoleOptionsListResponse(BaseModel):
    """List of role options for dropdowns"""
    options: list[RoleOptionResponse]
