"""NURSE-V2 N2-2 — schemas for the nurse workplace assignment admin contract.

Creation/read/deactivation of NurseWorkplaceAssignment rows (owner
design-GO 2026-09-19, scope item 4: "admin/backend contract для
создания/чтения/деактивации assignments"). No serving endpoints here —
those are N2-3.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NurseWorkplaceAssignmentCreateRequest(BaseModel):
    """Admin request to assign a Nurse User to a QueueResource workplace."""

    model_config = ConfigDict(protected_namespaces=())

    user_id: int = Field(..., gt=0, description="Target User id (role must be Nurse)")
    queue_resource_id: int = Field(..., gt=0, description="QueueResource registry id")
    cabinet_override: str | None = Field(
        None,
        max_length=20,
        description=(
            "Station/cabinet for this assignment; NULL falls back to "
            "QueueResource.default_cabinet (D2 FINAL)"
        ),
    )


class NurseWorkplaceAssignmentResponse(BaseModel):
    """Admin read model for a NurseWorkplaceAssignment row.

    Enriched with the referenced user/resource mirror fields so the admin
    surface does not need follow-up requests; ``effective_cabinet`` is the
    resolved cabinet (override ?? QueueResource.default_cabinet).
    """

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    user_id: int
    queue_resource_id: int
    cabinet_override: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # user mirror
    user_username: str | None = None
    user_full_name: str | None = None

    # resource mirror
    resource_code: str | None = None
    resource_display_name: str | None = None
    resource_queue_tag: str | None = None
    resource_default_cabinet: str | None = None

    # resolved cabinet: override ?? default
    effective_cabinet: str | None = None


class NurseWorkplaceAssignmentListResponse(BaseModel):
    """Paged list of assignments with the total count for the filter."""

    items: list[NurseWorkplaceAssignmentResponse]
    total: int
