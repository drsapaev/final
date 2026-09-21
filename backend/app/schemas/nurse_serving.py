"""NURSE-V2 N2-3 — schemas for the assignment-scoped nurse serving API.

The serving plane of the track (owner GO 2026-09-20, slice table row
N2-3): a Nurse User sees and serves ONLY the queue of a QueueResource
she holds an ACTIVE NurseWorkplaceAssignment for. Every operation is
attributed to the real User (called_by/served_by on the entry,
started_by/performed_by on the execution, actor UserAuditLog rows).

No migration: the N2-2 foundation (0071/0072) already carries the whole
schema this API writes (assignment rows, service_executions with the
mandatory-for-this-API queue_entry_id, the QF-1 attribution columns on
online_queue_entries).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NurseServingErrorDetail(BaseModel):
    """The typed {"detail": ...} body every domain/auth error returns."""

    detail: str


class NurseServingWorkplaceResponse(BaseModel):
    """One ACTIVE workplace of the calling Nurse (self-scope read)."""

    model_config = ConfigDict(protected_namespaces=())

    assignment_id: int
    queue_resource_id: int
    resource_code: str | None = None
    resource_display_name: str | None = None
    resource_queue_tag: str | None = None
    resource_default_cabinet: str | None = None
    cabinet_override: str | None = None
    # D2 FINAL resolution (override ?? default) — the station cabinet the
    # nurse actually works at; call announcements use it.
    effective_cabinet: str | None = None


class NurseServingWorkplaceListResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    items: list[NurseServingWorkplaceResponse]
    total: int


class NurseServingStationServiceState(BaseModel):
    """One VisitService of the held entry's visit, routed to this station.

    ``pending`` is the D3/last-completer predicate: a station-routed
    service is pending until some attempt completed it or its LATEST
    attempt was explicitly cancelled (an incomplete latest attempt still
    needs a retry or an explicit entry-level terminal decision).
    """

    model_config = ConfigDict(protected_namespaces=())

    visit_service_id: int
    service_id: int | None = None
    code: str | None = None
    name: str | None = None
    qty: int = 1
    latest_attempt_no: int | None = None
    latest_attempt_status: str | None = None
    in_progress_execution_id: int | None = None
    pending: bool = True


class NurseServingEntryResponse(BaseModel):
    """A queue entry as the serving station sees it."""

    model_config = ConfigDict(protected_namespaces=())

    id: int
    number: int
    status: str
    priority: int = 0
    source: str | None = None
    patient_id: int | None = None
    patient_name: str | None = None
    phone: str | None = None
    queue_time: datetime | None = None
    called_at: datetime | None = None
    called_by_user_id: int | None = None
    served_by_user_id: int | None = None
    served_at: datetime | None = None
    visit_id: int | None = None
    is_my_claim: bool = False
    # Populated for the active (called/in_progress) entries: the
    # station-routed services of the entry's visit with their execution
    # state — the tablet's "what is left to perform" list.
    services: list[NurseServingStationServiceState] = Field(default_factory=list)


class NurseServingStationResponse(BaseModel):
    """The station state: queue metadata + waiting + active entries.

    ``late_pending`` (codex round-2 P1): TERMINAL entries of today's
    station queue whose visit still has PENDING station-routed services
    — e.g. a procedure prescribed after the last-completer flip. The
    serving plane deliberately does not reopen terminal entries; the
    servable path is the existing rejoin flow (a new ticket for the same
    visit — the next entry's serving sees ALL pending station services).
    The board surfaces the state so nothing prescribed is silently
    stranded and the desk can re-ticket.
    """

    model_config = ConfigDict(protected_namespaces=())

    queue_resource_id: int
    resource_queue_tag: str | None = None
    resource_display_name: str | None = None
    effective_cabinet: str | None = None
    queue_id: int
    queue_day: datetime | None = None
    waiting: list[NurseServingEntryResponse]
    active: list[NurseServingEntryResponse]
    my_entry: NurseServingEntryResponse | None = None
    late_pending: list[NurseServingEntryResponse] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


class NurseServingCallNextResponse(BaseModel):
    """The atomic claim result.

    ``idempotent`` is True when the Nurse already held a called /
    in_progress entry at this station and the SAME entry was returned
    (the §6 "повтор запроса идемпотентен" / reconnect contract).
    """

    model_config = ConfigDict(protected_namespaces=())

    entry: NurseServingEntryResponse
    idempotent: bool
    waiting_count: int


class NurseServingStartResponse(BaseModel):
    """Entry-level serving start (called -> in_progress)."""

    model_config = ConfigDict(protected_namespaces=())

    entry_id: int
    status: str
    visit_id: int | None = None
    visit_status: str | None = None
    idempotent: bool


class NurseServingExecutionCreateRequest(BaseModel):
    """Start (or idempotently re-claim) a service execution attempt."""

    model_config = ConfigDict(protected_namespaces=())

    queue_entry_id: int = Field(..., gt=0, description="The served queue entry")
    visit_service_id: int = Field(..., gt=0, description="The VisitService to perform")


class NurseServingExecutionResponse(BaseModel):
    """One ServiceExecution attempt, with the entry-flip outcome."""

    model_config = ConfigDict(protected_namespaces=())

    id: int
    visit_service_id: int
    queue_entry_id: int | None = None
    attempt_no: int
    status: str
    started_by_user_id: int
    started_at: datetime | None = None
    performed_by_user_id: int | None = None
    completed_at: datetime | None = None
    incomplete_reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Set on terminal transitions: whether THIS completion flipped the
    # queue entry to served (the last-completer contract). On an
    # idempotent replay the field reflects the entry's CURRENT served
    # state (the durable attribution lives on the entry row:
    # status/served_by/served_at).
    entry_served: bool = False
    entry_served_by_user_id: int | None = None


def _normalize_mandatory_reason(value: str) -> str:
    """Codex round-3 P2: a mandatory reason must carry CONTENT.

    ``min_length=1`` counts whitespace codepoints, so a spaces-only
    payload passed validation and was stored verbatim. Normalize:
    strip, then fail closed on blank — and a VALID reason is stored
    trimmed, so the clinical record never carries padding.
    """
    normalized = value.strip()
    if not normalized:
        raise ValueError("reason must not be blank")
    return normalized


class NurseServingExecutionIncompleteRequest(BaseModel):
    """Abort an in_progress attempt with a mandatory reason."""

    reason: str = Field(..., min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        return _normalize_mandatory_reason(value)


class NurseServingEntryIncompleteRequest(BaseModel):
    """Terminate the entry-level serving with a mandatory reason."""

    reason: str = Field(..., min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        return _normalize_mandatory_reason(value)


class NurseServingEntryActionResponse(BaseModel):
    """Entry-level no-show / incomplete result."""

    model_config = ConfigDict(protected_namespaces=())

    entry_id: int
    new_status: str
    reason: str | None = None


# N2-3 follow-up (N2-5 §8): the drain-recovery discovery read path. A
# mid-flight assignment deactivation empties the workplaces list and 403s
# the station board, so a RELOADED tablet had no way to rediscover the
# in_progress execution the graceful drain still lets the starter finish.
class NurseServingDrainingStationRef(BaseModel):
    """The station a draining execution belongs to (display context)."""

    model_config = ConfigDict(protected_namespaces=())

    queue_resource_id: int
    resource_code: str | None = None
    resource_display_name: str | None = None
    # Historical D2 resolution (the now-inactive assignment override ??
    # resource default) — display-only context, never an authorization.
    effective_cabinet: str | None = None


class NurseServingDrainingEntryRef(BaseModel):
    """The queue entry context of a draining execution."""

    model_config = ConfigDict(protected_namespaces=())

    entry_id: int
    number: int
    patient_name: str | None = None


class NurseServingDrainingServiceRef(BaseModel):
    """The VisitService a draining execution performs."""

    model_config = ConfigDict(protected_namespaces=())

    visit_service_id: int
    code: str | None = None
    name: str | None = None
    qty: int = 1


class NurseServingDrainingExecutionItem(BaseModel):
    """One discoverable drain candidate: the caller's own unfinished work."""

    model_config = ConfigDict(protected_namespaces=())

    execution: NurseServingExecutionResponse
    station: NurseServingDrainingStationRef
    entry: NurseServingDrainingEntryRef
    service: NurseServingDrainingServiceRef


class NurseServingDrainingExecutionListResponse(BaseModel):
    """The drain-recovery discovery payload (self-scope, read-only)."""

    model_config = ConfigDict(protected_namespaces=())

    items: list[NurseServingDrainingExecutionItem] = Field(default_factory=list)
    total: int = 0
