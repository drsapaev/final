"""Admin-only DTOs for editing public website content."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

WEBSITE_SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"


class WebsiteContentOperation(StrEnum):
    SAVE_DRAFT = "save_draft"
    SAVE_PUBLISHED = "save_published"
    PUBLISH = "publish"
    UNPUBLISH = "unpublish"
    REPUBLISH = "republish"


class _WebsiteContentUpdateBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str | None = Field(default=None, max_length=160, pattern=WEBSITE_SLUG_PATTERN)
    operation: WebsiteContentOperation

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class WebsiteServiceContentUpdate(_WebsiteContentUpdateBase):
    name_ru: str | None = Field(default=None, max_length=256)
    name_uz: str | None = Field(default=None, max_length=256)
    description_ru: str | None = None
    description_uz: str | None = None


class WebsiteDoctorContentUpdate(_WebsiteContentUpdateBase):
    bio_ru: str | None = None
    bio_uz: str | None = None


class WebsiteServiceContentOut(BaseModel):
    id: int
    active: bool
    name_ru: str
    name_uz: str | None = None
    description_ru: str | None = None
    description_uz: str | None = None
    slug: str | None = None
    show_on_website: bool
    website_first_published_at: datetime | None = None
    slug_locked: bool
    missing_fields: list[str] = Field(default_factory=list)
    action_result: str | None = None


class WebsiteDoctorContentOut(BaseModel):
    id: int
    active: bool
    owner_active: bool | None = None
    display_name: str | None = None
    bio_ru: str | None = None
    bio_uz: str | None = None
    slug: str | None = None
    show_on_website: bool
    website_first_published_at: datetime | None = None
    slug_locked: bool
    missing_fields: list[str] = Field(default_factory=list)
    action_result: str | None = None
