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
