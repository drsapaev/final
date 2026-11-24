from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

WorklistView = Literal[
    "actionable", "today", "overdue", "awaiting_specimen", "in_review", "ready"
]
WorklistSort = Literal["oldest", "newest", "name"]
WorklistStatus = Literal[
    "pending",
    "awaiting_specimen",
    "in_progress",
    "in_review",
    "held",
    "partial",
    "ready",
    "canceled",
]
LabOrderPriority = Literal["routine", "urgent"]


class LabWorklistSearch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    q: str = Field(default="", max_length=120)
    barcode: str | None = Field(default=None, min_length=1, max_length=64)
    view: WorklistView = "actionable"
    sort: WorklistSort = "oldest"
    from_date: date | None = None
    to_date: date | None = None
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=320)

    @model_validator(mode="after")
    def check_date_range(self) -> "LabWorklistSearch":
        if self.from_date and self.to_date and self.from_date > self.to_date:
            raise ValueError("from_date must be on or before to_date")
        return self


class LabWorklistService(BaseModel):
    id: int
    visit_service_id: int | None
    code: str | None
    name: str
    quantity: int
    canceled: bool = False
    can_cancel: bool = False


class LabWorklistProgress(BaseModel):
    total_reports: int
    released_reports: int
    ordered_tests: int | None = None
    released_tests: int | None = None
    canceled_tests: int | None = None


class LabWorklistEntry(BaseModel):
    id: str
    patient_id: int
    patient_fio: str
    patient_birth_year: int | None
    visit_id: int | None
    appointment_id: int | None
    order_id: int | None
    queue_entry_id: int | None
    queue_number: int | None
    queue_status: str | None
    appointment_time: str | None
    work_date: date
    created_at: datetime
    due_at: datetime | None
    priority: LabOrderPriority | None
    status: WorklistStatus
    hold_reason: str | None
    service_details: list[LabWorklistService]
    services: list[str]
    service_codes: list[str]
    report_instance_id: int | None
    report_template_name: str | None
    lab_report_status: str | None
    progress: LabWorklistProgress
    specimen_ids: list[int]
    specimen_barcodes: list[str]


class LabWorklistCounts(BaseModel):
    actionable: int
    today: int
    overdue: int
    awaiting_specimen: int
    in_review: int
    ready: int


class LabWorklistPage(BaseModel):
    entries: list[LabWorklistEntry]
    total: int
    counts: LabWorklistCounts
    next_cursor: str | None
    date: date
    timezone: str


class LabOrderedTestCancellation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    order_id: int | None = Field(default=None, gt=0)
    reason: str = Field(min_length=1, max_length=300)


class LabCanceledOrderedTest(BaseModel):
    order_id: int
    visit_service_id: int
    canceled_at: datetime
    canceled_by_user_id: int
