from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SpecimenStatus = Literal[
    "expected", "collected", "received", "accepted", "held", "rejected"
]
SpecimenTransition = Literal["collect", "receive", "accept", "hold", "reject"]
SpecimenAction = Literal[
    "collect",
    "receive",
    "accept",
    "hold",
    "reject",
    "print_label",
    "assign",
    "aliquot",
    "recollect",
]
SpecimenEventAction = Literal[
    "create",
    "collect",
    "receive",
    "accept",
    "hold",
    "reject",
    "print_label",
    "assign",
    "unassign",
    "aliquot",
    "recollect",
]
SpecimenCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, pattern=r"^[a-z][a-z0-9_-]{0,31}$"
    ),
]
PositiveId = Annotated[int, Field(gt=0)]
SpecimenReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
]


class SpecimenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LabSpecimenTargets(SpecimenInput):
    visit_service_ids: list[PositiveId] = Field(default_factory=list, max_length=100)
    report_instance_ids: list[PositiveId] = Field(default_factory=list, max_length=100)


class LabSpecimenCreate(LabSpecimenTargets):
    request_id: UUID
    material_code: SpecimenCode
    container_code: SpecimenCode
    parent_specimen_id: PositiveId | None = None
    replaces_specimen_id: PositiveId | None = None

    @model_validator(mode="after")
    def validate_origin(self) -> LabSpecimenCreate:
        if (
            self.parent_specimen_id is not None
            and self.replaces_specimen_id is not None
        ):
            raise ValueError("A specimen may be an aliquot or recollection")
        return self


class LabSpecimenCommand(SpecimenInput):
    expected_revision: PositiveId
    request_id: UUID


class LabSpecimenTransitionCommand(LabSpecimenCommand):
    action: SpecimenTransition
    reason: SpecimenReason | None = None

    @model_validator(mode="after")
    def validate_reason(self) -> LabSpecimenTransitionCommand:
        if self.action in {"hold", "reject"} and self.reason is None:
            raise ValueError("A reason is required")
        return self


class LabSpecimenAssignmentCommand(LabSpecimenCommand, LabSpecimenTargets):
    operation: Literal["add", "remove"] = "add"
    reason: SpecimenReason | None = None

    @model_validator(mode="after")
    def validate_targets(self) -> LabSpecimenAssignmentCommand:
        if not self.visit_service_ids and not self.report_instance_ids:
            raise ValueError("At least one assignment is required")
        if self.operation == "remove" and self.reason is None:
            raise ValueError("A reason is required to remove an assignment")
        return self


class LabSpecimenScan(SpecimenInput):
    barcode: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
    ]
    order_id: PositiveId | None = None


class LabSpecimenEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    revision: int
    action: SpecimenEventAction
    resulting_status: SpecimenStatus
    actor_user_id: int
    happened_at: datetime
    reason: str | None
    visit_service_ids: list[int]
    report_instance_ids: list[int]


class LabSpecimenOut(BaseModel):
    id: int
    order_id: int
    visit_id: int | None
    barcode: str
    material_code: str
    container_code: str
    status: SpecimenStatus
    revision: int
    created_at: datetime
    collected_at: datetime | None
    received_at: datetime | None
    accepted_at: datetime | None
    latest_reason: str | None
    parent_specimen_id: int | None
    replaces_specimen_id: int | None
    visit_service_ids: list[int]
    report_instance_ids: list[int]
    available_actions: list[SpecimenAction]
    events: list[LabSpecimenEventOut]


class LabSpecimenListOut(BaseModel):
    items: list[LabSpecimenOut]
    data_status: Literal["known", "unknown"]


class LabSpecimenErrorOut(BaseModel):
    detail: str
