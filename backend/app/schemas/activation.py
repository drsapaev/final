from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.base import ORMModel

ActivationStatusLiteral = Literal["issued", "trial", "active", "expired", "revoked"]


class ActivationIssueIn(ORMModel):
    days: int = Field(365, ge=1, le=3650)
    status: ActivationStatusLiteral | None = None
    meta: str | None = None


class ActivationIssueOut(ORMModel):
    key: str
    expiry_date: str | None = None  # YYYY-MM-DD
    status: ActivationStatusLiteral


class ActivationActivateIn(ORMModel):
    key: str = Field(..., min_length=8, max_length=64)


class ActivationActivateOut(ORMModel):
    ok: bool
    reason: str | None = None
    token: str | None = None
    key: str | None = None
    machine_hash: str | None = None
    expiry_date: str | None = None
    status: ActivationStatusLiteral | None = None


class ActivationStatusOut(ORMModel):
    ok: bool
    reason: str | None = None
    key: str | None = None
    expiry_date: str | None = None
    status: ActivationStatusLiteral | None = None
    machine_hash: str | None = None


# --- Admin list/revoke/extend ---


class ActivationListRow(ORMModel):
    key: str
    machine_hash: str | None = None
    expiry_date: str | None = None  # YYYY-MM-DD
    status: ActivationStatusLiteral
    created_at: str
    updated_at: str
    meta: str | None = None


class ActivationListOut(ORMModel):
    items: list[ActivationListRow]
    total: int


class ActivationRevokeIn(ORMModel):
    key: str = Field(..., min_length=8, max_length=64)


class ActivationExtendIn(ORMModel):
    key: str = Field(..., min_length=8, max_length=64)
    days: int = Field(..., ge=1, le=3650)
