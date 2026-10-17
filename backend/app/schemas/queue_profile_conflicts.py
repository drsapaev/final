"""Typed conflict responses shared by queue-profile write surfaces."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class QueueProfileBindingChangedDetail(BaseModel):
    """A stale binding snapshot that must be reloaded before retrying."""

    reason: Literal["profile_binding_changed"]
    stale_fields: list[str] | None = None
    message: str


class QueueProfileBindingChangedResponse(BaseModel):
    detail: QueueProfileBindingChangedDetail


class QueueProfilePublicationConflictDetail(BaseModel):
    """A profile cannot be published as one bookable QR direction yet."""

    reason: Literal["profile_publication_blocked"]
    code: Literal[
        "profile_inactive",
        "profile_unpublished",
        "profile_unavailable",
        "mixed_direction_targets",
        "ambiguous_profile_target",
        "no_bookable_owner",
    ]
    message: str


class QueueProfilePublicationConflictResponse(BaseModel):
    detail: QueueProfilePublicationConflictDetail
