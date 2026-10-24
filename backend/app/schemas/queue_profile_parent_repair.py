"""Explicit Admin contract for the narrow QueueProfile parent repair."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class QueueProfileParentReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["profile_key", "department_key"]
    department_key: str
    department_name_ru: str | None
    exists: bool
    active: bool | None


class QueueProfileParentRepairTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department_key: str
    department_name_ru: str
    active: bool


class QueueProfileParentRepairLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    services: int = Field(ge=0)
    department_services: int = Field(ge=0)
    active_doctors: int = Field(ge=0)
    active_queue_resources: int = Field(ge=0)
    daily_queues: int = Field(ge=0)
    entries_waiting: int = Field(ge=0)
    entries_total: int = Field(ge=0)
    active_public_addresses: int = Field(ge=0)


class QueueProfileParentRepairPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    profile_id: int
    profile_key: str
    current_department_key: str | None
    current_availability_state: Literal["available", "unavailable", "conflict"]
    current_reason_codes: list[str]
    parent_references: list[QueueProfileParentReference]
    target: QueueProfileParentRepairTarget | None
    proposed_availability_state: Literal["available", "unavailable", "conflict"] | None
    proposed_reason_codes: list[str]
    links: QueueProfileParentRepairLinks
    services_removed_from_parent_scope: int = Field(ge=0)
    services_added_to_parent_scope: int = Field(ge=0)
    service_scope_confirmation_required: bool
    qr_catalog_would_be_bookable: bool
    permanent_address_would_be_bookable: bool
    public_access_confirmation_required: bool
    can_apply: bool
    blocker_code: (
        Literal[
            "parent_conflict_absent",
            "own_key_department_missing",
        ]
        | None
    )
    preview_token: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class QueueProfileParentRepairApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_department_key: str = Field(min_length=1, max_length=50)
    preview_token: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm_target: Literal[True]
    confirm_service_scope_change: bool = False
    confirm_public_access: bool = False
    reason_code: Literal["resolve_parent_conflict_to_own_key"]


class QueueProfileParentRepairResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["applied", "already_applied"]
    profile_id: int
    profile_key: str
    department_key: None
    audit_event_id: int | None


class QueueProfileParentRepairErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal[
        "profile_not_found",
        "parent_repair_stale",
        "parent_repair_not_applicable",
        "parent_repair_confirmation_required",
    ]
    message: str


class QueueProfileParentRepairErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: QueueProfileParentRepairErrorDetail
