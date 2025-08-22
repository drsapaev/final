from __future__ import annotations

from typing import Literal, Optional, List
from pydantic import BaseModel, Field


ActivationStatusLiteral = Literal["issued", "trial", "active", "expired", "revoked"]


class ActivationIssueIn(BaseModel):
    days: int = Field(365, ge=1, le=3650)
    status: ActivationStatusLiteral | None = None
    meta: Optional[str] = None


class ActivationIssueOut(BaseModel):
    key: str
    expiry_date: Optional[str] = None  # YYYY-MM-DD
    status: ActivationStatusLiteral


class ActivationActivateIn(BaseModel):
    key: str = Field(..., min_length=8, max_length=64)


class ActivationActivateOut(BaseModel):
    ok: bool
    reason: Optional[str] = None
    token: Optional[str] = None
    key: Optional[str] = None
    machine_hash: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[ActivationStatusLiteral] = None


class ActivationStatusOut(BaseModel):
    ok: bool
    reason: Optional[str] = None
    key: Optional[str] = None
    expiry_date: Optional[str] = None
    status: Optional[ActivationStatusLiteral] = None
    machine_hash: Optional[str] = None


# --- Admin list/revoke/extend ---

class ActivationListRow(BaseModel):
    key: str
    machine_hash: Optional[str] = None
    expiry_date: Optional[str] = None  # YYYY-MM-DD
    status: ActivationStatusLiteral
    created_at: str
    updated_at: str
    meta: Optional[str] = None


class ActivationListOut(BaseModel):
    items: List[ActivationListRow]
    total: int


class ActivationRevokeIn(BaseModel):
    key: str = Field(..., min_length=8, max_length=64)


class ActivationExtendIn(BaseModel):
    key: str = Field(..., min_length=8, max_length=64)
    days: int = Field(..., ge=1, le=3650)