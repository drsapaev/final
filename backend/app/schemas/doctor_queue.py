"""Explicit response contracts for the doctor-owned queue workflow."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class DoctorQueueResponseModel(BaseModel):
    """Keep existing queue response extensions while documenting known fields."""

    model_config = ConfigDict(extra="allow")


class DoctorQueuePatient(DoctorQueueResponseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    phone: str | None = None
    birth_date: date | None = None


class DoctorQueueDoctor(DoctorQueueResponseModel):
    id: int
    name: str
    specialty: str
    cabinet: str | None = None


class DoctorQueueStats(DoctorQueueResponseModel):
    total: int
    waiting: int
    called: int
    served: int
    online_entries: int | None = None
    desk_entries: int | None = None


class DoctorQueueEntry(DoctorQueueResponseModel):
    id: int
    number: int
    # These identifiers are always emitted. They can be null for an
    # unlinked/anonymous queue entry before a visit has been started.
    patient_id: int | None
    visit_id: int | None
    patient_name: str
    phone: str | None = None
    source: str
    status: str
    created_at: datetime | None = None
    queue_time: datetime | None = None
    updated_at: datetime | None = None
    last_changed_at: datetime | None = None
    display_time_kind: str
    timezone: str
    called_at: datetime | None = None
    patient: DoctorQueuePatient | None = None
    available_actions: list[str]
    can_call: bool
    can_start_visit: bool
    can_no_show: bool
    can_send_to_diagnostics: bool
    can_complete: bool
    can_notify_diagnostics_return: bool
    can_mark_incomplete: bool
    can_restore_next: bool


class DoctorQueueTodayResponse(DoctorQueueResponseModel):
    queue_exists: bool
    queue_id: int | None = None
    queue_ids: list[int] | None = None
    opened_at: datetime | None = None
    doctor: DoctorQueueDoctor
    date: date
    entries: list[DoctorQueueEntry]
    stats: DoctorQueueStats
    can_call_next: bool
    next_call_entry_id: int | None


class DoctorQueueStartVisitResponse(DoctorQueueResponseModel):
    success: bool
    message: str
    entry_id: int
    patient_id: int | None
    visit_id: int
    status: str
