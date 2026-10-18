"""Typed, read-only contract for the queue setup directions screen."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AdminDirectionReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal["info", "warning", "error"]
    subject_type: Literal["queue_profile", "department", "queue_tag"] | None = None
    subject_key: str | None = None


class AdminDirectionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    key: str
    title: str
    title_ru: str | None = None
    queue_tags: list[str]
    department_key: str | None = None
    is_active: bool
    show_on_qr_page: bool
    display_order: int
    icon: str | None = None
    color: str | None = None


class AdminDirectionBookingTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_type: Literal["doctor", "resource"]
    owner_id: int
    queue_tag: str
    label: str
    is_active: bool
    eligible_for_new_booking: bool
    existing_daily_queue_ids: list[int] = Field(default_factory=list)


class AdminDirectionDailyQueueReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daily_queue_id: int
    queue_tag: str
    owner_type: Literal["doctor", "resource", "unresolved"]
    owner_id: int | None = None


class AdminDirectionPrecreateTag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_tag: str
    state: Literal["eligible", "already_exists", "blocked"]
    can_precreate: bool
    active_service_count: int = Field(ge=0)
    owner_type: Literal["doctor", "resource"] | None = None
    owner_id: int | None = None
    existing_daily_queue_ids: list[int] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)


class AdminDirectionAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "restore_profile",
        "configure_ownership",
        "review_configuration",
        "publish_profile",
        "provision_permanent_address",
    ]
    entity_type: Literal["queue_profile", "queue_tag", "department"]
    entity_id: int | None = None
    entity_key: str | None = None


class AdminQueueDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: AdminDirectionProfile
    resolved_mode: Literal["booking", "overview", "unresolved"]
    configuration_state: Literal["ready", "incomplete", "conflict", "unavailable"]
    configuration_reasons: list[AdminDirectionReason] = Field(default_factory=list)
    effective_availability: Literal["available", "unavailable", "conflict"]
    effective_availability_reasons: list[str] = Field(default_factory=list)
    booking_targets: list[AdminDirectionBookingTarget] = Field(default_factory=list)
    current_day_queues: list[AdminDirectionDailyQueueReference] = Field(
        default_factory=list
    )
    public_availability: bool
    permanent_address_exists: bool
    precreate_by_tag: list[AdminDirectionPrecreateTag] = Field(default_factory=list)
    allowed_next_actions: list[AdminDirectionAction] = Field(default_factory=list)


class AdminUnattachedService(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_id: int
    name: str
    code: str | None = None
    queue_tag: str | None = None
    active: bool


class AdminUnattachedResource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: int
    queue_tag: str
    display_name: str
    active: bool


class AdminUnattachedCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue_tags: list[str] = Field(default_factory=list)
    services: list[AdminUnattachedService] = Field(default_factory=list)
    resources: list[AdminUnattachedResource] = Field(default_factory=list)


class AdminQueueDirectionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_day: date
    directions: list[AdminQueueDirection] = Field(default_factory=list)
    unattached: AdminUnattachedCatalog
