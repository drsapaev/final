"""NURSE-V2 N2-3 — the assignment-scoped nurse serving endpoints.

Owner GO 2026-09-20 («Начинай N2-3 (serving API) отдельным PR»).
Every operation authenticates the JWT, enforces the canonical role via
``require_active_roles("Nurse")`` (a deactivated Nurse with an
unexpired JWT fails closed — the N2-2 factory, PR #3333), and then
delegates the DATA-level authorization to the service: an ACTIVE
NurseWorkplaceAssignment row for (caller, queue_resource). Deny by
default: even a superuser needs the assignment row on this plane (the
superuser bypass covers the ROLE check only); Admin keeps its own
existing resource-queue surfaces, which this API neither touches nor
widens.

The domain-error contract (400/404/409) and the auth contract (401/403)
are published on the decorators via NurseServingErrorDetail — the
N2-2 review-round-2/3 discipline — so backend/openapi.json and the
generated frontend api.ts describe the responses the runtime actually
returns.

call-next mirrors the REST call-next notification contract
(best-effort, AFTER the committed transition — an audit/notification
failure must never 5xx a successful claim, a client retry would call a
SECOND patient): the patient notification, the display-board broadcast
(resource-axis naming — the QD-2C round-12/13 pattern) and the queue-WS
routing rooms. The announced cabinet is THE NURSE'S station (D2
resolution: assignment override ?? resource default), and idempotent
replays (the §6 reconnect contract) re-announce nothing.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_roles
from app.core.audit import audit_log_dependency
from app.models.user import User
from app.schemas.nurse_serving import (
    NurseServingCallNextResponse,
    NurseServingEntryActionResponse,
    NurseServingEntryIncompleteRequest,
    NurseServingErrorDetail,
    NurseServingExecutionCreateRequest,
    NurseServingExecutionIncompleteRequest,
    NurseServingExecutionResponse,
    NurseServingStartResponse,
    NurseServingStationResponse,
    NurseServingWorkplaceListResponse,
)
from app.services.nurse_serving_api_service import (
    NurseServingApiDomainError,
    NurseServingApiService,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_BASE = "/nurse/serving"

_AUTH_ERROR_RESPONSES = {
    401: {
        "model": NurseServingErrorDetail,
        "description": "Требуется аутентификация (JWT отсутствует или недействителен)",
    },
    403: {
        "model": NurseServingErrorDetail,
        "description": (
            "Только активная роль Nurse: не Nurse, деактивированный аккаунт "
            "с действующим JWT, либо нет АКТИВНОГО назначения на это рабочее "
            "место (data-level авторизация)"
        ),
    },
}


def _service(db: Session) -> NurseServingApiService:
    return NurseServingApiService(db)


def _run(handler) -> Any:
    """Map domain errors to HTTPExceptions (the N2-2 endpoint pattern)."""
    try:
        return handler()
    except NurseServingApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get(
    f"{_BASE}/workplaces",
    response_model=NurseServingWorkplaceListResponse,
    responses={**_AUTH_ERROR_RESPONSES},
)
def list_my_workplaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Nurse")),
):
    """The caller's ACTIVE workplaces (self-scope; no admin surface).

    One row per active NurseWorkplaceAssignment, enriched with the
    resource mirror fields and the D2-resolved effective cabinet
    (assignment override ?? resource default) — the station list the
    tablet (N2-5) will offer as the shift context.
    """
    from app.schemas.nurse_serving import NurseServingWorkplaceResponse

    items, total = _service(db).list_workplaces(current_user.id)
    return NurseServingWorkplaceListResponse(
        items=[NurseServingWorkplaceResponse(**item) for item in items],
        total=total,
    )


@router.get(
    f"{_BASE}/queue-resources/{{queue_resource_id}}/entries",
    response_model=NurseServingStationResponse,
    responses={
        404: {
            "model": NurseServingErrorDetail,
            "description": "QueueResource не найден или очередь станции сегодня не активна",
        },
        **_AUTH_ERROR_RESPONSES,
    },
)
def get_station_entries(
    queue_resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Nurse")),
):
    """The station board: waiting + active entries + the caller's claim.

    ``waiting`` is the canonical call order (priority DESC, arrival
    ASC, id ASC); ``active`` are the called/in_progress entries with
    their station-routed services and execution state (the tablet's
    "what is left to perform" list); ``my_entry`` is the caller's own
    held claim — the §6 reconnect/reload contract (the active serving
    is re-fetchable, never lost).
    """
    return _run(
        lambda: _service(db).get_station_state(current_user.id, queue_resource_id)
    )


@router.post(
    f"{_BASE}/queue-resources/{{queue_resource_id}}/call-next",
    response_model=NurseServingCallNextResponse,
    responses={
        404: {
            "model": NurseServingErrorDetail,
            "description": "Нет ожидающих пациентов, либо очередь станции не активна",
        },
        **_AUTH_ERROR_RESPONSES,
    },
)
async def call_next_patient(
    queue_resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Nurse")),
    audit_context: dict[str, Any] = Depends(audit_log_dependency),
):
    """Atomically claim the next waiting patient (§6, idempotent per Nurse).

    The claim serializes on the station's queue row; a Nurse already
    holding a called/in_progress entry at this station gets the SAME
    entry back (``idempotent: true`` — the repeat/reconnect contract);
    two nurses claiming concurrently always get DIFFERENT patients. The
    transition is committed with an actor-attributed UserAuditLog row;
    ``called_by_user_id`` is the claiming Nurse.
    """
    from fastapi.concurrency import run_in_threadpool

    result = await run_in_threadpool(
        lambda: _run(
            lambda: _service(db).call_next(
                current_user.id,
                queue_resource_id,
                acting_username=current_user.username,
                audit_context=audit_context,
            )
        )
    )

    # --- Notification contract (fresh claims only; best-effort) ---
    if result and result.get("entry") and not result.get("idempotent"):
        entry_id = result["entry"]["id"]
        cabinet = result.get("cabinet")
        entry = None

        # 1. Patient notification (mobile/PWA) — the NURSE'S cabinet.
        try:
            from app.models.online_queue import OnlineQueueEntry
            from app.services.queue_position_notifications import (
                get_queue_position_service,
            )

            notify_service = get_queue_position_service(db)
            entry = (
                db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.id == entry_id)
                .first()
            )
            if entry:
                await notify_service.notify_patient_called(
                    entry, cabinet_number=cabinet
                )
        except Exception as exc:  # noqa: BLE001 — non-fatal by design
            logger.warning(
                "Nurse call-next: patient notification failed for entry %s: %s",
                entry_id,
                exc,
            )

        # 2. Display board (TV) — resource-axis naming (QD-2C round-12/13).
        try:
            from app.services.display_websocket import get_display_manager

            manager = get_display_manager()
            if not entry:
                from app.models.online_queue import OnlineQueueEntry

                entry = (
                    db.query(OnlineQueueEntry)
                    .filter(OnlineQueueEntry.id == entry_id)
                    .first()
                )
            if entry:
                queue = entry.queue
                if queue is not None and queue.queue_resource_id is not None:
                    resource = queue.queue_resource
                    owner_name = (
                        resource.display_name
                        if resource is not None
                        else "Ресурс очереди"
                    )
                    cabinet = cabinet or (
                        resource.default_cabinet if resource is not None else None
                    )
                else:
                    owner_name = "Процедурный кабинет"
                await manager.broadcast_patient_call(
                    queue_entry=entry,
                    doctor_name=owner_name,
                    cabinet=cabinet,
                )
        except Exception as exc:  # noqa: BLE001 — non-fatal by design
            logger.warning(
                "Nurse call-next: display broadcast failed for entry %s: %s",
                entry_id,
                exc,
            )

        # 3. Queue WS rooms — the routing identity of the chosen queue
        # (the QD-2C round-24 pattern).
        try:
            from app.ws.queue_ws import broadcast_queue_update, queue_update_departments

            if entry is not None:
                broadcast_day = (
                    entry.queue.day
                    if entry.queue is not None and entry.queue.day is not None
                    else None
                )
                queue_date_str = (
                    broadcast_day.strftime("%Y-%m-%d") if broadcast_day else ""
                )
                for dept in queue_update_departments(db, entry.queue):
                    broadcast_queue_update(
                        department=dept,
                        date=queue_date_str,
                        event_type="queue_update",
                        data={
                            "action": "call_next",
                            "entry_id": entry_id,
                            "surface": "nurse_serving",
                        },
                    )
        except Exception as exc:  # noqa: BLE001 — non-fatal by design
            logger.warning(
                "Nurse call-next: queue WS broadcast failed for entry %s: %s",
                entry_id,
                exc,
            )

    return NurseServingCallNextResponse(**result)


@router.post(
    f"{_BASE}/queue-resources/{{queue_resource_id}}/entries/{{entry_id}}/start",
    response_model=NurseServingStartResponse,
    responses={
        400: {
            "model": NurseServingErrorDetail,
            "description": "Недопустимый статус записи (требуется called)",
        },
        404: {
            "model": NurseServingErrorDetail,
            "description": "Запись не найдена в очереди рабочего места",
        },
        **_AUTH_ERROR_RESPONSES,
    },
)
def start_serving(
    queue_resource_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Nurse")),
    audit_context: dict[str, Any] = Depends(audit_log_dependency),
):
    """Start serving the called patient (called -> in_progress).

    Station-assignment-authorized (any assigned nurse may start a
    called entry of her station — the admin-called display-board flow
    works too); idempotent while in_progress (the D1 handover surface).
    The visit is resolved (visit_id-first, else station-branch with the
    open|in_progress widening) and linked to the entry; an ``open``
    visit transitions to ``in_progress`` (the doctor-surface BUG-3
    lesson). NOTHING closes the visit here.
    """
    return _run(
        lambda: _service(db).start_entry(
            current_user.id,
            queue_resource_id,
            entry_id,
            acting_username=current_user.username,
            audit_context=audit_context,
        )
    )


@router.post(
    f"{_BASE}/queue-resources/{{queue_resource_id}}/executions",
    response_model=NurseServingExecutionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "model": NurseServingExecutionResponse,
            "description": "Идемпотентный повтор той же медсестрой (in_progress attempt)",
        },
        400: {
            "model": NurseServingErrorDetail,
            "description": (
                "Запись не in_progress / не связана с визитом, услуга не "
                "маршрутизирована на станцию или чужой визит"
            ),
        },
        404: {
            "model": NurseServingErrorDetail,
            "description": "Запись очереди или VisitService не найдены",
        },
        409: {
            "model": NurseServingErrorDetail,
            "description": (
                "Услуга уже исполняется другой медсестрой или уже выполнена"
            ),
        },
        **_AUTH_ERROR_RESPONSES,
    },
)
def start_service_execution(
    queue_resource_id: int,
    payload: NurseServingExecutionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Nurse")),
    audit_context: dict[str, Any] = Depends(audit_log_dependency),
    response: Response = None,  # injected by FastAPI (status override below)
):
    """Start an execution attempt of a concrete VisitService (D1 FINAL).

    ``queue_entry_id`` is REQUIRED (the D1 contract for the nurse API —
    the queue entry is the serving context, stored on the attempt); the
    service must route to the station (D3: queue_tag match +
    requires_doctor=false). Same-nurse repeat POST is a no-op (200 with
    the existing in_progress attempt); a DIFFERENT nurse gets 409 (the
    one-active claim). A retry after incomplete creates a NEW attempt
    (attempt_no = previous + 1); history is never overwritten.
    """
    data = _run(
        lambda: _service(db).create_execution(
            current_user.id,
            queue_resource_id,
            queue_entry_id=payload.queue_entry_id,
            visit_service_id=payload.visit_service_id,
            acting_username=current_user.username,
            audit_context=audit_context,
        )
    )
    if response is not None and not data.get("created", True):
        # Same-nurse idempotent replay: 200, not a second 201.
        response.status_code = status.HTTP_200_OK
    return data


@router.post(
    f"{_BASE}/executions/{{execution_id}}/complete",
    response_model=NurseServingExecutionResponse,
    responses={
        400: {
            "model": NurseServingErrorDetail,
            "description": "Исполнение не в статусе in_progress",
        },
        404: {
            "model": NurseServingErrorDetail,
            "description": "ServiceExecution не найден",
        },
        409: {
            "model": NurseServingErrorDetail,
            "description": "Уже завершено другим пользователем",
        },
        **_AUTH_ERROR_RESPONSES,
    },
)
def complete_service_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Nurse")),
    audit_context: dict[str, Any] = Depends(audit_log_dependency),
):
    """Complete an in_progress attempt (performed_by = the ACTUAL nurse).

    D1 handover: one nurse may start, another finishes. The
    last-completer contract: the completion that observes ALL
    station-routed services of the visit done flips the queue entry to
    ``served`` with ``served_by_user_id`` = the flipping nurse (§6
    attribution); exactly one concurrent completion wins the flip.
    Mid-flight assignment deactivation does not strand the attempt: the
    STARTER may always complete what she started (graceful drain).
    Same-nurse repeat = 200 no-op; a different actor on a terminal
    attempt = 409.
    """
    return _run(
        lambda: _service(db).complete_execution(
            current_user.id,
            execution_id,
            acting_username=current_user.username,
            audit_context=audit_context,
        )
    )


@router.post(
    f"{_BASE}/executions/{{execution_id}}/incomplete",
    response_model=NurseServingExecutionResponse,
    responses={
        400: {
            "model": NurseServingErrorDetail,
            "description": "Исполнение не в статусе in_progress",
        },
        404: {
            "model": NurseServingErrorDetail,
            "description": "ServiceExecution не найден",
        },
        409: {
            "model": NurseServingErrorDetail,
            "description": "Уже отмечено незавершённым другим пользователем",
        },
        **_AUTH_ERROR_RESPONSES,
    },
)
def incomplete_service_execution(
    execution_id: int,
    payload: NurseServingExecutionIncompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Nurse")),
    audit_context: dict[str, Any] = Depends(audit_log_dependency),
):
    """Abort an in_progress attempt with a mandatory reason (no flip).

    The service stays PENDING (the retry is a NEW attempt — D1
    history); the queue entry must NOT flip to served. The entry-level
    terminal (patient done, not everything performed) is the separate
    entry-incomplete operation.
    """
    return _run(
        lambda: _service(db).incomplete_execution(
            current_user.id,
            execution_id,
            payload.reason,
            acting_username=current_user.username,
            audit_context=audit_context,
        )
    )


@router.post(
    f"{_BASE}/queue-resources/{{queue_resource_id}}/entries/{{entry_id}}/no-show",
    response_model=NurseServingEntryActionResponse,
    responses={
        400: {
            "model": NurseServingErrorDetail,
            "description": "Недопустимый статус записи (допустимо waiting или called)",
        },
        404: {
            "model": NurseServingErrorDetail,
            "description": "Запись не найдена в очереди рабочего места",
        },
        409: {
            "model": NurseServingErrorDetail,
            "description": "Запись связана с незавершённым исполнением услуги",
        },
        **_AUTH_ERROR_RESPONSES,
    },
)
def mark_entry_no_show(
    queue_resource_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Nurse")),
    audit_context: dict[str, Any] = Depends(audit_log_dependency),
):
    """Mark the patient as no-show (queue-level only).

    The sibling-pending services decision (N2-3 brief): VisitServices
    and ServiceExecutions are deliberately NOT touched — the patient
    may be restored (the existing Admin restore path) and serving
    continues. The mutation is committed with an actor-attributed
    UserAuditLog row.
    """
    return _run(
        lambda: _service(db).mark_entry_no_show(
            current_user.id,
            queue_resource_id,
            entry_id,
            acting_username=current_user.username,
            audit_context=audit_context,
        )
    )


@router.post(
    f"{_BASE}/queue-resources/{{queue_resource_id}}/entries/{{entry_id}}/incomplete",
    response_model=NurseServingEntryActionResponse,
    responses={
        400: {
            "model": NurseServingErrorDetail,
            "description": "Недопустимый статус записи (допустимо called или in_progress)",
        },
        404: {
            "model": NurseServingErrorDetail,
            "description": "Запись не найдена в очереди рабочего места",
        },
        409: {
            "model": NurseServingErrorDetail,
            "description": "Есть незавершённые исполнения услуг по записи",
        },
        **_AUTH_ERROR_RESPONSES,
    },
)
def mark_entry_incomplete(
    queue_resource_id: int,
    entry_id: int,
    payload: NurseServingEntryIncompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_roles("Nurse")),
    audit_context: dict[str, Any] = Depends(audit_log_dependency),
):
    """Terminate the entry-level serving with a mandatory reason.

    409 while any in_progress execution is linked — each attempt must
    be resolved explicitly (billing/medical audit). The visit is NOT
    closed (the §5 forbidden list); entry-level terminal states are
    queue facts.
    """
    return _run(
        lambda: _service(db).mark_entry_incomplete(
            current_user.id,
            queue_resource_id,
            entry_id,
            payload.reason,
            acting_username=current_user.username,
            audit_context=audit_context,
        )
    )
