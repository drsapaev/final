"""Contracts for the public-site media management API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

PublicSiteMediaKind = Literal["clinic_logo", "doctor_portrait"]


class PublicSiteMediaAdminOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    asset_kind: PublicSiteMediaKind
    doctor_id: int | None
    mime_type: str
    byte_size: int
    is_published: bool
    published_at: datetime | None
    created_at: datetime
    media_url: str


class PublicSiteMediaErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str


class PublicSiteMediaErrorOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: PublicSiteMediaErrorDetail


class PublicSiteMediaStorageReadyOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ready: Literal[True]
