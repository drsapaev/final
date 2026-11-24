"""Typed configuration for internal Registrar tabs; never queue ownership."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RegistrarTabInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_kind: Literal["profile", "doctor"]
    target_id: int = Field(gt=0, strict=True)
    title: str | None = Field(default=None, max_length=100)
    visible: bool = Field(default=True, strict=True)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if any(ord(char) < 32 for char in value):
            raise ValueError("Tab titles cannot contain control characters")
        return value


class RegistrarTabsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0, strict=True)
    tabs: list[RegistrarTabInput] = Field(max_length=200)
    reason: Literal["configure_registrar_tabs"]

    @model_validator(mode="after")
    def unique_targets(self) -> RegistrarTabsUpdate:
        targets = [(tab.target_kind, tab.target_id) for tab in self.tabs]
        if len(set(targets)) != len(targets):
            raise ValueError("Each profile or doctor can appear only once")
        return self


class StoredRegistrarTabs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(gt=0, strict=True)
    tabs: list[RegistrarTabInput] = Field(max_length=200)

    @model_validator(mode="after")
    def unique_targets(self) -> StoredRegistrarTabs:
        targets = [(tab.target_kind, tab.target_id) for tab in self.tabs]
        if len(set(targets)) != len(targets):
            raise ValueError("Duplicate configured target")
        return self


class ResolvedRegistrarTab(BaseModel):
    target_kind: Literal["profile", "doctor"]
    target_id: int
    custom_title: str | None
    title: str
    title_ru: str | None
    profile_key: str | None
    queue_tags: list[str]
    icon: str | None
    color: str | None
    visible: bool
    available: bool
    reason_code: Literal["missing_target", "inactive_target"] | None


class RegistrarProfileFilter(BaseModel):
    """Historical deep-link filter metadata; does not create a visible tab."""

    key: str
    queue_tags: list[str]
    title: str
    title_ru: str | None


class RegistrarTabsOut(BaseModel):
    mode: Literal["legacy", "configured"]
    version: int
    tabs: list[ResolvedRegistrarTab]
    profile_filters: list[RegistrarProfileFilter]


class AdminRegistrarTabsOut(RegistrarTabsOut):
    options: list[ResolvedRegistrarTab]


class RegistrarTabsErrorDetail(BaseModel):
    code: str


class RegistrarTabsErrorResponse(BaseModel):
    detail: RegistrarTabsErrorDetail


class RegistrarTabsValidationResponse(BaseModel):
    # Business validation uses a safe code object, while FastAPI's request
    # validation uses an array of location/message/type error objects.
    detail: RegistrarTabsErrorDetail | list[dict[str, Any]]
