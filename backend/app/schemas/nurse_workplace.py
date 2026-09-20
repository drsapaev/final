"""NURSE-V2 N2-2 — schemas for the nurse workplace assignment admin contract.

Creation/read/deactivation of NurseWorkplaceAssignment rows (owner
design-GO 2026-09-19, scope item 4: "admin/backend contract для
создания/чтения/деактивации assignments"). No serving endpoints here —
those are N2-3.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @field_validator("cabinet_override")
    @classmethod
    def _blank_override_is_no_override(cls, v: str | None) -> str | None:
        # Review P2 round 3 (PR #3333): D2 FINAL defines the cabinet axis as
        # NULL-coalesced (NULL -> QueueResource.default_cabinet). An empty
        # or whitespace-only string carries the same "no override" intent
        # as an omitted field (an empty admin form input serializes to ""),
        # so it is normalized to NULL at the write boundary. Without this
        # the API could store cabinet_override="" — a non-NULL override the
        # enrichment would contradict ("" override, default effective) and
        # an N2-3 implementation that is D2-literal (override ?? default)
        # would read as a real cabinet, diverging from this admin surface.
        if v is None or not v.strip():
            return None
        return v


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


class NurseWorkplaceErrorDetail(BaseModel):
    """Body of the documented errors on the assignment control plane:
    the domain errors (400/404/409) AND the auth errors (401/403, review
    P2 round 2 — PR #3333).

    Review P2 (PR #3333): the PR body declares 400/404/409 part of the
    canonical admin contract; this model gives the generated clients the
    typed ``{"detail": ...}`` shape FastAPI's HTTPException actually
    returns — the same pattern as ServiceUnavailableDetail (admin-doctors
    503) and UserPhoneScopeConflictDetail (user-management 409). The
    401/403 publications reuse the same model because the auth failures
    (get_current_user / require_active_roles) also surface as
    HTTPException ``{"detail": ...}`` bodies — proven at runtime by
    test_nurse_workplace_endpoints.py."""

    model_config = ConfigDict(protected_namespaces=())

    detail: str


class NurseWorkplaceAssignmentListResponse(BaseModel):
    """Paged list of assignments with the total count for the filter."""

    items: list[NurseWorkplaceAssignmentResponse]
    total: int
