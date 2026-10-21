"""Public website read contracts.

Only patient-facing content is exposed here. These DTOs intentionally do not
inherit from the broader operational service or doctor schemas.
"""

from __future__ import annotations

from datetime import time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PublicSiteLocale = Literal["uz-Latn", "ru"]


class PublicSiteClinicOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    logo_url: str | None = None
    working_hours_start: time | None = None
    working_hours_end: time | None = None


class PublicSiteNotFoundDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["public_content_not_found"]


class PublicSiteNotFoundOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: PublicSiteNotFoundDetail


class PublicSiteCategoryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class PublicSiteServiceOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    description: str
    price: Decimal | None = Field(
        description="Null means the localized site should display 'price on request'."
    )
    currency: str | None = None
    category: str | None = None


class PublicSiteDoctorOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    bio: str
    specialty: str | None = None
    experience_years: int | None = Field(None, ge=0)
    portrait_url: str | None = None
