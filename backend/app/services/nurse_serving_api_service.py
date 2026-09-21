"""NURSE-V2 N2-3 — the assignment-scoped nurse serving domain service.

Owner GO 2026-09-20 («Начинай N2-3 (serving API) отдельным PR»), slice
table row N2-3 of ``.ai-factory/plans/nurse-v2-clinical-serving.md``.

Authorization model (deny-by-default, the §5 contract):
- the endpoint layer authenticates the JWT AND enforces the canonical
  role via ``require_active_roles("Nurse")`` (a deactivated Nurse with
  an unexpired JWT fails closed, the N2-2 factory);
- the DATA-level authorization lives here: an ACTIVE
  NurseWorkplaceAssignment row for (caller, queue_resource). Even a
  superuser needs the assignment row on this plane — the superuser
  bypass covers the ROLE check only; Admin keeps its own existing
  resource-queue surfaces (doctor-panel Admin-only paths), which this
  API deliberately does not touch or widen;
- the QueueResource registry row's ``active`` flag is NOT re-checked
  here: serving follows the QD-2C deactivation-resilient surface rule
  (an existing station queue remains the serving surface; N2-2 already
  stops NEW assignments for inactive resources).

State machines this service drives (the N2-3 brief transition matrix):

* entry level (online_queue_entries.status):
  ``waiting -> called`` (call-next, atomic claim, called_by = Nurse)
  ``called -> in_progress`` (start serving; visit resolves + links;
      idempotent while in_progress — the station state, not a personal
      claim: D1 handover means another assigned nurse may take over)
  ``called|in_progress -> no_show`` (queue-level only — sibling pending
      VisitServices/ServiceExecutions are deliberately NOT touched: the
      Admin restore path can bring the patient back)
  ``called|in_progress -> incomplete`` (entry terminal; 409 while any
      in_progress execution is linked — each attempt must be resolved
      explicitly first)
  ``in_progress -> served`` (the last-completer flip: the completion
      that observes ALL station-routed services of the visit done)

* execution level (service_executions.status, D1 FINAL):
  ``in_progress -> completed`` (performed_by may differ from
      started_by — one nurse may start, another finishes)
  ``in_progress -> incomplete`` (reason mandatory; retry = NEW attempt)
  idempotent replay: same terminal state + same actor -> 200 no-op;
  a DIFFERENT actor -> 409 (the claim holder is reconstructable).

Mid-flight assignment deactivation (the brief's open question) —
DECISION: graceful drain. NEW operations (call-next / start / execution
create / no-show / entry incomplete) require the ACTIVE assignment and
answer 403 without it. Completing or incompleting an ALREADY-started
execution stays available to its starter (``started_by == caller``)
even without an active assignment — otherwise a deactivation mid-flight
would strand the row in ``in_progress`` forever (the partial unique
one-active index would block every retry). The drain is bounded: it can
only end an attempt the nurse already holds, never claim new patients.

Visit handling (start): ``visit_id``-first — the entry's linked visit is
trusted (linked by confirmation / a previous start). Without a link the
STATION-branch resolution mirrors the doctor-surface resource branch
(patient + queue day + department == queue_tag) with one deliberate
widening: the search accepts ``open`` OR ``in_progress`` visits,
because the canonical procedures flow (doctor orders -> patient walks
to the station) has the visit already in_progress, and an open-only
search would duplicate it. A missing visit is created (doctor_id=None,
department=queue_tag) and immediately linked to the entry — the
qr_queue/_online_entries precedent. The visit's ``open ->
in_progress`` transition reuses VisitLifecycleService (the doctor
surface's BUG-3 lesson: a visit left ``open'' cannot be completed
later). NOTHING here closes the visit: closing stays with the
doctor/cashier/admin lifecycle (the §5 forbidden list).

Serialization (lock order — canonical, documented to avoid PG
deadlocks): DailyQueue row -> queue entry row -> visit_service row ->
execution row. Call-next additionally takes the DailyQueue row FOR
UPDATE FIRST: same-station claimants serialize there, which makes the
held-claim idempotency check race-free for a same-nurse double-tap
(two concurrent requests cannot both observe "no held claim"). The
waiting-candidate claim itself keeps the QRQueueService canonical order
(``priority DESC, coalesce(queue_time, created_at) ASC, id ASC``) under
``with_for_update`` — the same locking pattern the plan mandates to
reuse. The last-completer flip runs UNDER the entry row lock as a
single guarded ``UPDATE ... WHERE status = 'in_progress'``: exactly one
concurrent completion flips the entry, the loser's guarded update
no-ops (rowcount=0), and ``served_by_user_id`` is the actual flipping
nurse (§6 proof point).

Audit (billing/medical ledger, the N2-3 brief): every mutation commits
an actor-attributed ``UserAuditLog`` row IN THE SAME TRANSACTION
(``log_audit_event``; table vocabulary ``online_queue_entries`` /
``service_executions`` — the same snake_case the success-path ledger
and ``get_by_resource()`` joins already use). Attempts are append-only
by construction (D1: a retry is a NEW row, history is never
overwritten); the entry keeps its QF-1 attribution columns.

Error mapping: 404 = referenced entity (resource / queue / entry /
execution / visit service) not found; 400 = boundary validation (wrong
state, service not routed to the station, wrong visit); 403 = no ACTIVE
assignment for (caller, resource); 409 = claim/terminal conflicts
(another nurse holds the in_progress attempt, entry already terminal,
in_progress executions block an entry terminal).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.core.audit import log_audit_event
from app.crud import visit as crud_visit
from app.crud.clinic import clinic_today
from app.crud.queue_resource_routing import find_active_tag_queue
from app.models.appointment import Appointment
from app.models.nurse_workplace import NurseWorkplaceAssignment
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.service import Service
from app.models.service_execution import ServiceExecution
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.visit_lifecycle_service import VisitLifecycleService

# Entry-level states this plane drives (the model's documented vocabulary).
_ENTRY_ACTIVE_STATES = ("called", "in_progress")
_ENTRY_TERMINAL_STATES = ("served", "incomplete", "no_show", "cancelled")


# The station-routed service predicate (D3 FINAL): the QD-2 SSOT
# Service.queue_tag == QueueResource.queue_tag plus the
# requires_doctor=false resource-serving gate. A doctor-routed service
# is NEVER the station's concern and never blocks the entry flip.
def _service_routed_to_station(service: Service, resource: QueueResource) -> bool:
    return (
        service.queue_tag is not None
        and service.queue_tag == resource.queue_tag
        and not bool(service.requires_doctor)
    )


def _now() -> datetime:
    return datetime.now(UTC)


class NurseServingApiDomainError(Exception):
    """Domain error carrying an HTTP status and a user-readable detail."""

    status_code: int
    detail: str

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class NurseServingApiService:
    """Assignment-scoped serving operations (the N2-3 contract)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # authorization / resolution helpers
    # ------------------------------------------------------------------

    def _resource_or_error(self, queue_resource_id: int) -> QueueResource:
        resource = self.db.get(QueueResource, queue_resource_id)
        if resource is None:
            raise NurseServingApiDomainError(
                404, f"QueueResource id={queue_resource_id} не найден"
            )
        return resource

    def _active_assignment_or_error(
        self, user_id: int, queue_resource_id: int
    ) -> NurseWorkplaceAssignment:
        """DATA-level authorization: an ACTIVE assignment row is required.

        Deny-by-default for everyone on this plane (superuser included —
        the role bypass lives in the endpoint factory, not here). The
        resource registry row's ``active`` flag is deliberately NOT
        re-checked (QD-2C deactivation-resilient surface semantics); N2-2
        already blocks NEW assignments for inactive resources.
        """
        assignment = (
            self.db.query(NurseWorkplaceAssignment)
            .filter(
                NurseWorkplaceAssignment.user_id == user_id,
                NurseWorkplaceAssignment.queue_resource_id == queue_resource_id,
                NurseWorkplaceAssignment.is_active.is_(True),
            )
            .first()
        )
        if assignment is None:
            raise NurseServingApiDomainError(
                403,
                "Нет активного назначения на рабочее место "
                f"queue_resource_id={queue_resource_id}",
            )
        return assignment

    def _effective_cabinet(
        self, assignment: NurseWorkplaceAssignment, resource: QueueResource
    ) -> str | None:
        # D2 FINAL literal (override ?? default) — the N2-2 enrichment
        # contract; "" never survives the write boundary, but a
        # hand-applied NULL stays NULL.
        if assignment.cabinet_override is not None:
            return assignment.cabinet_override
        return resource.default_cabinet

    def _station_queue_or_error(
        self,
        resource: QueueResource,
        target_date: date | None = None,
    ) -> DailyQueue:
        """The station's queue for the clinic-local today (tag-first).

        ``find_active_tag_queue`` is the QD-2C tag-first unification:
        bridged, resource-owned or legacy synthetic rows all resolve to
        ONE routing surface per (day, tag).
        """
        day = target_date or clinic_today(self.db)
        queue = find_active_tag_queue(self.db, day, resource.queue_tag)
        if queue is None:
            raise NurseServingApiDomainError(
                404,
                "Очередь рабочего места не активна на дату "
                f"{day.isoformat()} (queue_tag={resource.queue_tag!r})",
            )
        return queue

    def _station_entry_or_error(
        self, queue: DailyQueue, entry_id: int
    ) -> OnlineQueueEntry:
        """Entry must belong to the STATION's queue (not just any queue)."""
        entry = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.id == entry_id,
                OnlineQueueEntry.queue_id == queue.id,
            )
            .first()
        )
        if entry is None:
            raise NurseServingApiDomainError(
                404,
                f"Запись очереди id={entry_id} не найдена в очереди "
                f"рабочего места (queue_id={queue.id})",
            )
        return entry

    def _audit(
        self,
        *,
        action: str,
        table_name: str,
        row_id: int,
        description: str,
        actor: User,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        audit_context: dict[str, Any] | None = None,
    ) -> None:
        """Actor-attributed ledger row, IN the caller's transaction."""
        log_audit_event(
            db=self.db,
            user_id=actor.id,
            action=action,
            table_name=table_name,
            row_id=row_id,
            old_values=old_values,
            new_values=new_values,
            request_id=(audit_context or {}).get("request_id"),
            ip_address=(audit_context or {}).get("ip_address"),
            user_agent=(audit_context or {}).get("user_agent"),
            description=description,
        )

    # ------------------------------------------------------------------
    # read-side payloads
    # ------------------------------------------------------------------

    def _station_services_payload(
        self, entry: OnlineQueueEntry, resource: QueueResource
    ) -> list[dict[str, Any]]:
        """Station-routed VisitServices of the entry's visit + execution state.

        The tablet's "what is left to perform" list for a called /
        in_progress patient. Empty when the entry has no linked visit
        yet (start links it).

        Single-entry convenience over the batched loader below (the
        mutation paths enrich exactly ONE entry — the same two queries
        as before: VisitService JOIN Service, then the executions).
        """
        return self._station_services_batch([entry], resource)[entry.id]

    def _station_services_batch(
        self, entries: list[OnlineQueueEntry], resource: QueueResource
    ) -> dict[int, list[dict[str, Any]]]:
        """Per-entry station-services payloads for MANY entries, 2 queries.

        Codex round-3 P2 (N+1): ALL entries' VisitServices + Services
        load in ONE IN-batch query and all their ServiceExecutions in
        ONE more; routing and folding happen in memory. The station
        board polls with a CONSTANT query budget instead of the previous
        per-row pair (2 queries per active/terminal entry, plus a full
        second enrichment pass for every late_pending row) — the
        terminal list grows during the working day and several tablets
        poll the same board.
        """
        payloads: dict[int, list[dict[str, Any]]] = {entry.id: [] for entry in entries}
        visit_ids = {entry.visit_id for entry in entries if entry.visit_id is not None}
        if not visit_ids:
            return payloads
        rows = (
            self.db.query(VisitService, Service)
            .outerjoin(Service, VisitService.service_id == Service.id)
            .filter(VisitService.visit_id.in_(visit_ids))
            .order_by(VisitService.visit_id.asc(), VisitService.id.asc())
            .all()
        )
        rows_by_visit: dict[int, list[tuple[VisitService, Service | None]]] = {}
        for visit_service, service in rows:
            rows_by_visit.setdefault(visit_service.visit_id, []).append(
                (visit_service, service)
            )
        visit_service_ids = [visit_service.id for visit_service, _svc in rows]
        executions: dict[int, list[ServiceExecution]] = {}
        if visit_service_ids:
            exec_rows = (
                self.db.query(ServiceExecution)
                .filter(ServiceExecution.visit_service_id.in_(visit_service_ids))
                .order_by(
                    ServiceExecution.visit_service_id.asc(),
                    ServiceExecution.attempt_no.asc(),
                )
                .all()
            )
            for execution in exec_rows:
                executions.setdefault(execution.visit_service_id, []).append(execution)
        for entry in entries:
            if entry.visit_id is None:
                continue
            payloads[entry.id] = self._fold_station_service_items(
                rows_by_visit.get(entry.visit_id, []), executions, resource
            )
        return payloads

    @staticmethod
    def _fold_station_service_items(
        rows: list[tuple[VisitService, Service | None]],
        executions: dict[int, list[ServiceExecution]],
        resource: QueueResource,
    ) -> list[dict[str, Any]]:
        """Route + fold ONE visit's rows into the board service items."""
        items: list[dict[str, Any]] = []
        for visit_service, service in rows:
            if service is None or not _service_routed_to_station(service, resource):
                # Not this station's service (doctor-routed or another
                # tag) — never shown, never blocks the entry flip.
                continue
            attempts = executions.get(visit_service.id, [])
            latest = attempts[-1] if attempts else None
            completed_any = any(a.status == "completed" for a in attempts)
            latest_cancelled = latest is not None and latest.status == "cancelled"
            in_progress = next((a for a in attempts if a.status == "in_progress"), None)
            items.append(
                {
                    "visit_service_id": visit_service.id,
                    "service_id": visit_service.service_id,
                    "code": visit_service.code,
                    "name": visit_service.name,
                    "qty": visit_service.qty,
                    "latest_attempt_no": latest.attempt_no if latest else None,
                    "latest_attempt_status": latest.status if latest else None,
                    "in_progress_execution_id": (
                        in_progress.id if in_progress is not None else None
                    ),
                    "pending": not (completed_any or latest_cancelled),
                }
            )
        return items

    def _entry_payload(
        self,
        entry: OnlineQueueEntry,
        *,
        my_user_id: int,
        resource: QueueResource | None = None,
        with_services: bool = False,
        services: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": entry.id,
            "number": entry.number,
            "status": entry.status,
            "priority": entry.priority or 0,
            "source": entry.source,
            "patient_id": entry.patient_id,
            "patient_name": entry.patient_name,
            "phone": entry.phone,
            "queue_time": entry.queue_time,
            "called_at": entry.called_at,
            "called_by_user_id": entry.called_by_user_id,
            "served_by_user_id": entry.served_by_user_id,
            "served_at": entry.served_at,
            "visit_id": entry.visit_id,
            "is_my_claim": (
                entry.called_by_user_id == my_user_id
                and entry.status in _ENTRY_ACTIVE_STATES
            ),
            "services": [],
        }
        if services is not None:
            # Pre-folded by the batch loader (the board path): reuse
            # as-is — no second enrichment pass (codex round-3 P2).
            payload["services"] = services
        elif with_services and resource is not None:
            payload["services"] = self._station_services_payload(entry, resource)
        return payload

    def _replay_payload(self, execution: ServiceExecution) -> dict[str, Any]:
        """Codex round-2 P2: the terminal replay reports the DURABLE entry
        state, not a defaulted false.

        A lost-response retry of a completion that flipped the entry must
        not answer ``entry_served=false`` — the consumer would believe
        the station event is still open. The authoritative flip record
        lives on the entry row itself (status/served_by/served_at); the
        replay reflects the CURRENT state truthfully.
        """
        entry = (
            self.db.get(OnlineQueueEntry, execution.queue_entry_id)
            if execution.queue_entry_id is not None
            else None
        )
        served = entry is not None and entry.status == "served"
        return self._execution_payload(
            execution,
            entry_served=served,
            entry_served_by_user_id=entry.served_by_user_id if served else None,
        )

    def _execution_payload(
        self,
        execution: ServiceExecution,
        *,
        entry_served: bool = False,
        entry_served_by_user_id: int | None = None,
    ) -> dict[str, Any]:
        return {
            "id": execution.id,
            "visit_service_id": execution.visit_service_id,
            "queue_entry_id": execution.queue_entry_id,
            "attempt_no": execution.attempt_no,
            "status": execution.status,
            "started_by_user_id": execution.started_by_user_id,
            "started_at": execution.started_at,
            "performed_by_user_id": execution.performed_by_user_id,
            "completed_at": execution.completed_at,
            "incomplete_reason": execution.incomplete_reason,
            "created_at": execution.created_at,
            "updated_at": execution.updated_at,
            "entry_served": entry_served,
            "entry_served_by_user_id": entry_served_by_user_id,
        }

    # ------------------------------------------------------------------
    # operations — read plane
    # ------------------------------------------------------------------

    def list_workplaces(self, user_id: int) -> tuple[list[dict[str, Any]], int]:
        """The caller's ACTIVE workplaces (self-scope, no admin surface)."""
        query = self.db.query(NurseWorkplaceAssignment).filter(
            NurseWorkplaceAssignment.user_id == user_id,
            NurseWorkplaceAssignment.is_active.is_(True),
        )
        total = query.count()
        rows = query.order_by(NurseWorkplaceAssignment.id.asc()).all()
        resource_ids = {row.queue_resource_id for row in rows}
        resources: dict[int, QueueResource] = {}
        if resource_ids:
            resources = {
                r.id: r
                for r in self.db.query(QueueResource).filter(
                    QueueResource.id.in_(resource_ids)
                )
            }
        items = []
        for row in rows:
            resource = resources.get(row.queue_resource_id)
            items.append(
                {
                    "assignment_id": row.id,
                    "queue_resource_id": row.queue_resource_id,
                    "resource_code": resource.code if resource else None,
                    "resource_display_name": (
                        resource.display_name if resource else None
                    ),
                    "resource_queue_tag": resource.queue_tag if resource else None,
                    "resource_default_cabinet": (
                        resource.default_cabinet if resource else None
                    ),
                    "cabinet_override": row.cabinet_override,
                    "effective_cabinet": (
                        self._effective_cabinet(row, resource)
                        if resource is not None
                        else None
                    ),
                }
            )
        return items, total

    def get_station_state(self, user_id: int, queue_resource_id: int) -> dict[str, Any]:
        """The station board: waiting + active + my claim + late_pending.

        ``late_pending`` (codex round-2 P1): terminal entries whose visit
        still has PENDING station-routed services (a procedure prescribed
        after the last-completer flip) — surfaced so nothing prescribed
        is silently stranded; the servable path is the existing rejoin
        flow (a new ticket for the same visit).
        """
        resource = self._resource_or_error(queue_resource_id)
        assignment = self._active_assignment_or_error(user_id, queue_resource_id)
        queue = self._station_queue_or_error(resource)

        waiting_rows = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue.id,
                OnlineQueueEntry.status == "waiting",
            )
            .order_by(
                OnlineQueueEntry.priority.desc(),
                func.coalesce(
                    OnlineQueueEntry.queue_time,
                    OnlineQueueEntry.created_at,
                ).asc(),
                OnlineQueueEntry.id.asc(),
            )
            .all()
        )
        active_rows = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue.id,
                OnlineQueueEntry.status.in_(_ENTRY_ACTIVE_STATES),
            )
            .order_by(OnlineQueueEntry.id.asc())
            .all()
        )
        # Codex round-2 P1 (late services are never SILENTLY stranded):
        # terminal entries of today's station queue whose visit still has
        # PENDING station-routed services — e.g. a procedure the doctor
        # prescribed AFTER the last-completer flip (the add-service paths
        # append VisitServices without touching queue entries). The
        # serving plane deliberately does NOT reopen terminal entries
        # (the patient is no longer at the station); the servable path is
        # the EXISTING rejoin flow — a new ticket for the same visit (the
        # next entry's serving sees ALL pending station services of the
        # visit, including the late one). The board surfaces the state so
        # the desk can re-ticket: nothing prescribed is invisible.
        terminal_rows = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue.id,
                OnlineQueueEntry.status.in_(_ENTRY_TERMINAL_STATES),
                OnlineQueueEntry.visit_id.isnot(None),
            )
            .order_by(OnlineQueueEntry.id.asc())
            .all()
        )

        waiting = [self._entry_payload(e, my_user_id=user_id) for e in waiting_rows]
        # Codex round-3 P2 (batched enrichment): ALL active + terminal
        # rows' station services load in TWO IN-batch queries, and the
        # late_pending pass REUSES the already-folded items — the board
        # keeps a constant query budget under tablet polling (the
        # terminal list grows during the working day).
        enriched = self._station_services_batch(
            [*active_rows, *terminal_rows], resource
        )
        active = [
            self._entry_payload(e, my_user_id=user_id, services=enriched[e.id])
            for e in active_rows
        ]
        my_entry = next((item for item in active if item["is_my_claim"]), None)

        late_pending = []
        for terminal_entry in terminal_rows:
            services = enriched[terminal_entry.id]
            if any(item["pending"] for item in services):
                late_pending.append(
                    self._entry_payload(
                        terminal_entry,
                        my_user_id=user_id,
                        services=services,
                    )
                )
        return {
            "queue_resource_id": queue_resource_id,
            "resource_queue_tag": resource.queue_tag,
            "resource_display_name": resource.display_name,
            "effective_cabinet": self._effective_cabinet(assignment, resource),
            "queue_id": queue.id,
            "queue_day": queue.day,
            "waiting": waiting,
            "active": active,
            "my_entry": my_entry,
            "late_pending": late_pending,
            "counts": {
                "waiting": len(waiting),
                "called": sum(1 for e in active_rows if e.status == "called"),
                "in_progress": sum(1 for e in active_rows if e.status == "in_progress"),
                "late_pending": len(late_pending),
            },
        }

    # ------------------------------------------------------------------
    # operations — call-next (the §6 atomic claim)
    # ------------------------------------------------------------------

    def call_next(
        self,
        user_id: int,
        queue_resource_id: int,
        *,
        acting_username: str | None = None,
        audit_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Atomically claim the next waiting patient (idempotent per Nurse).

        Serialization: the DailyQueue row is taken FOR UPDATE FIRST —
        every same-station claimant (and a same-nurse double-tap)
        serializes there, so the held-claim idempotency check below is
        race-free. The waiting-candidate claim then reuses the
        QRQueueService canonical order + row lock.
        """
        resource = self._resource_or_error(queue_resource_id)
        assignment = self._active_assignment_or_error(user_id, queue_resource_id)
        queue = self._station_queue_or_error(resource)

        # Serialize claimants on this station's queue row (held until
        # commit) — the get_next_queue_number numbering precedent.
        queue = (
            self.db.query(DailyQueue)
            .filter(DailyQueue.id == queue.id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if queue is None:  # pragma: no cover - guarded above
            raise NurseServingApiDomainError(404, "Очередь рабочего места не найдена")

        # §6 idempotency: a called/in_progress entry ALREADY held by this
        # nurse at this station is returned as-is (reconnect/reload safe).
        held = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue.id,
                OnlineQueueEntry.called_by_user_id == user_id,
                OnlineQueueEntry.status.in_(_ENTRY_ACTIVE_STATES),
            )
            .order_by(OnlineQueueEntry.id.asc())
            .first()
        )
        if held is not None:
            waiting_count = (
                self.db.query(OnlineQueueEntry)
                .filter(
                    OnlineQueueEntry.queue_id == queue.id,
                    OnlineQueueEntry.status == "waiting",
                )
                .count()
            )
            return {
                "entry": self._entry_payload(
                    held,
                    my_user_id=user_id,
                    resource=resource,
                    with_services=True,
                ),
                "idempotent": True,
                "waiting_count": waiting_count,
                # Consumed by the endpoint's notification blocks (a fresh
                # claim announces THE NURSE'S station cabinet); stripped
                # by the response model.
                "cabinet": self._effective_cabinet(assignment, resource),
            }

        # The canonical claim (QRQueueService order + row lock).
        candidate = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue.id,
                OnlineQueueEntry.status == "waiting",
            )
            .order_by(
                OnlineQueueEntry.priority.desc(),
                func.coalesce(
                    OnlineQueueEntry.queue_time,
                    OnlineQueueEntry.created_at,
                ).asc(),
                OnlineQueueEntry.id.asc(),
            )
            .with_for_update()
            .first()
        )
        if candidate is None:
            raise NurseServingApiDomainError(404, "Нет ожидающих пациентов")

        changed_at = _now()
        candidate.status = "called"
        candidate.called_at = changed_at
        candidate.called_by_user_id = user_id
        candidate.updated_at = changed_at

        self._audit(
            action="CALL_NEXT",
            table_name="online_queue_entries",
            row_id=candidate.id,
            description=(
                "NURSE-V2 N2-3: nurse "
                f"{acting_username or user_id} called entry "
                f"id={candidate.id} (number={candidate.number}) at "
                f"queue_resource_id={queue_resource_id} "
                f"(cabinet={self._effective_cabinet(assignment, resource)!r})"
            ),
            actor=self._actor_or_stub(user_id),
            old_values={"status": "waiting"},
            new_values={
                "status": "called",
                "called_by_user_id": user_id,
            },
            audit_context=audit_context,
        )
        self.db.commit()
        self.db.refresh(candidate)
        waiting_count = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue.id,
                OnlineQueueEntry.status == "waiting",
            )
            .count()
        )
        return {
            "entry": self._entry_payload(
                candidate,
                my_user_id=user_id,
                resource=resource,
                with_services=True,
            ),
            "idempotent": False,
            "waiting_count": waiting_count,
            "cabinet": self._effective_cabinet(assignment, resource),
        }

    def _actor_or_stub(self, user_id: int) -> User:
        user = self.db.get(User, user_id)
        if user is not None:
            return user
        # Fabricated ids in unit harnesses: the ledger row is still
        # written (unattributed rows record WHAT changed — the N2-2
        # contract); production always passes the authenticated user.
        stub = User(id=user_id, username=f"user_{user_id}", role="Nurse")
        return stub

    # ------------------------------------------------------------------
    # operations — start serving (entry level)
    # ------------------------------------------------------------------

    def start_entry(
        self,
        user_id: int,
        queue_resource_id: int,
        entry_id: int,
        *,
        acting_username: str | None = None,
        audit_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """called -> in_progress (station-assignment-authorized, idempotent).

        The start is the STATION's state, not a personal claim: any
        assigned nurse may start a called entry of her station (the
        admin-called display-board flow), and an in_progress entry
        answers 200 idempotently (the D1 handover: another nurse takes
        over seamlessly). Personal-claim semantics live at the execution
        level (started_by) and the call level (called_by).
        """
        resource = self._resource_or_error(queue_resource_id)
        self._active_assignment_or_error(user_id, queue_resource_id)
        queue = self._station_queue_or_error(resource)

        entry = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.id == entry_id,
                OnlineQueueEntry.queue_id == queue.id,
            )
            .populate_existing()
            .with_for_update()
            .first()
        )
        if entry is None:
            raise NurseServingApiDomainError(
                404,
                f"Запись очереди id={entry_id} не найдена в очереди "
                f"рабочего места (queue_id={queue.id})",
            )

        if entry.status == "in_progress":
            # Idempotent station state — reconnect/reload safe.
            visit = self._visit_if_linked(entry)
            return {
                "entry_id": entry.id,
                "status": entry.status,
                "visit_id": entry.visit_id,
                "visit_status": visit.status if visit is not None else None,
                "idempotent": True,
            }
        if entry.status != "called":
            raise NurseServingApiDomainError(
                400,
                "Начать обслуживание можно только для записи в статусе "
                f"called, текущий: {entry.status}",
            )
        if entry.patient_id is None:
            # VisitService belongs to a Visit of a REGISTERED patient —
            # an unregistered walk-in entry has no servable service
            # context; the boundary answers 400, not an IntegrityError.
            raise NurseServingApiDomainError(
                400,
                f"Запись id={entry.id} не связана с зарегистрированным "
                "пациентом — обслуживание невозможно (визит и услуги "
                "требуют пациента)",
            )

        visit = self._resolve_entry_visit(entry, resource)
        # The doctor surface's BUG-3 lesson: a visit left 'open' cannot
        # be completed later — the serving start transitions it.
        if visit.status == "open":
            visit = VisitLifecycleService(self.db).start_visit(
                visit_id=visit.id,
                current_user=self._actor_or_stub(user_id),
                commit=False,
            )

        changed_at = _now()
        entry.status = "in_progress"
        entry.updated_at = changed_at

        self._audit(
            action="START_SERVING",
            table_name="online_queue_entries",
            row_id=entry.id,
            description=(
                "NURSE-V2 N2-3: nurse "
                f"{acting_username or user_id} started serving entry "
                f"id={entry.id} (number={entry.number}) at "
                f"queue_resource_id={queue_resource_id} "
                f"(visit_id={visit.id})"
            ),
            actor=self._actor_or_stub(user_id),
            old_values={"status": "called"},
            new_values={"status": "in_progress", "visit_id": visit.id},
            audit_context=audit_context,
        )
        self.db.commit()
        self.db.refresh(entry)
        return {
            "entry_id": entry.id,
            "status": entry.status,
            "visit_id": entry.visit_id,
            "visit_status": visit.status,
            "idempotent": False,
        }

    def _visit_if_linked(self, entry: OnlineQueueEntry) -> Visit | None:
        if entry.visit_id is None:
            return None
        return self.db.get(Visit, entry.visit_id)

    def _resolve_entry_visit(
        self, entry: OnlineQueueEntry, resource: QueueResource
    ) -> Visit:
        """visit_id-first; else station-branch resolution + immediate link.

        Codex round-1 P1: the linked visit is REVALIDATED against the
        entry's queue day before it is trusted — a force-majeure
        transfer (``ForceMajeureService.transfer_to_tomorrow``) copies
        ``visit_id`` onto the new day's entry, and serving must not run
        on yesterday's visit. The mirror of the doctor-surface contract
        (``doctor_integration/_queue_ops.py::_resolve_entry_visit``,
        codex rounds 40/41/43):

        - same-day visit -> served as-is;
        - visit of ANOTHER day, not anchored by live same-day tickets ->
          re-stamped to the queue day, its paired appointment follows
          (the round-43 lesson: without the appointment re-pairing the
          canonical visit pairing can later spawn a duplicate);
        - visit still shared by live tickets of its own day -> a FRESH
          visit is resolved for the queue day below and the entry is
          relinked (the peers keep the old visit).

        The station branch (patient + queue day + department ==
        queue_tag) keeps one deliberate widening over the doctor
        surface: the search accepts ``open`` OR ``in_progress`` visits —
        the canonical procedures flow (doctor orders -> patient walks to
        the station) has the visit already in_progress, and an
        open-only search would create a duplicate visit. A missing visit
        is created (doctor_id=None) and immediately linked to the entry
        (the qr_queue/_online_entries precedent: start and completion
        mutate ONE station event, not two visits).
        """
        if entry.visit_id:
            visit = self.db.get(Visit, entry.visit_id)
            if visit is not None:
                queue_day = getattr(entry.queue, "day", None)
                if queue_day is None or visit.visit_date == queue_day:
                    return visit
                # A transferred (or hand-relinked) entry pointing at a
                # visit of another day: validate the anchor before
                # trusting the link.
                shared = (
                    self.db.query(OnlineQueueEntry.id)
                    .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
                    .filter(
                        OnlineQueueEntry.visit_id == visit.id,
                        OnlineQueueEntry.id != entry.id,
                        # Retired tickets no longer anchor the visit.
                        OnlineQueueEntry.status.not_in(["cancelled", "no_show"]),
                        # Only SAME-day peers anchor; entries already
                        # moved to a new day follow their own resolution.
                        DailyQueue.day == visit.visit_date,
                    )
                    .first()
                    is not None
                )
                if not shared:
                    # The solo visit follows the transferred ticket
                    # (re-stamped to the day of actual serving) — and its
                    # paired appointment follows too, the round-43
                    # doctor-surface contract: the canonical visit
                    # pairing (patient/date/time/doctor) would otherwise
                    # keep the appointment on the old day and could spawn
                    # a second visit for it later.
                    appointment_filters = [
                        Appointment.patient_id == visit.patient_id,
                        Appointment.appointment_date == visit.visit_date,
                        Appointment.status.not_in(
                            ["cancelled", "completed", "no_show"]
                        ),
                    ]
                    if visit.doctor_id is None:
                        appointment_filters.append(Appointment.doctor_id.is_(None))
                    else:
                        appointment_filters.append(
                            Appointment.doctor_id == visit.doctor_id
                        )
                    if visit.visit_time:
                        _hhmm = visit.visit_time[:5]
                        appointment_filters.append(
                            Appointment.appointment_time.in_((_hhmm, f"{_hhmm}:00"))
                        )
                    else:
                        appointment_filters.append(
                            Appointment.appointment_time.is_(None)
                        )
                    self.db.query(Appointment).filter(*appointment_filters).update(
                        {"appointment_date": queue_day}, synchronize_session=False
                    )
                    visit.visit_date = queue_day
                    return visit
                # Shared by live same-day tickets: fall through to the
                # branch resolution below (a fresh visit for THIS queue
                # day + relink — the peers keep the old one).

        queue_day = getattr(entry.queue, "day", None) or clinic_today(self.db)
        visit = (
            self.db.query(Visit)
            .filter(
                Visit.patient_id == entry.patient_id,
                Visit.visit_date == queue_day,
                Visit.department == resource.queue_tag,
                Visit.status.in_(("open", "in_progress")),
            )
            .order_by(Visit.id.asc())
            .first()
        )
        if visit is None:
            # commit=False: the visit INSERT joins THIS transaction
            # (visit + entry link + audit row commit atomically — the
            # N2-2 single-transaction discipline; the Fix C precedent).
            visit = crud_visit.create_visit(
                db=self.db,
                patient_id=entry.patient_id,
                doctor_id=None,
                visit_date=queue_day,
                department=resource.queue_tag,
                commit=False,
            )
        # Immediate link — idempotent for every later mutation on this
        # entry (both surfaces mutate ONE station event).
        entry.visit_id = visit.id
        return visit

    # ------------------------------------------------------------------
    # operations — executions (D1 FINAL)
    # ------------------------------------------------------------------

    def create_execution(
        self,
        user_id: int,
        queue_resource_id: int,
        *,
        queue_entry_id: int,
        visit_service_id: int,
        acting_username: str | None = None,
        audit_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Start an execution attempt (or idempotently re-claim own one).

        ``visit_service_id`` MUST belong to the entry's visit and route
        to the station (D3: queue_tag match + requires_doctor=false).
        The VisitService row is locked FOR UPDATE (attempt ordinals
        serialize per service); the one-in_progress invariant is checked
        deterministically under that lock (same starter -> 200 no-op,
        another nurse -> 409) and enforced on PG by the 0072 partial
        unique index.
        """
        resource = self._resource_or_error(queue_resource_id)
        self._active_assignment_or_error(user_id, queue_resource_id)
        queue = self._station_queue_or_error(resource)

        entry = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.id == queue_entry_id,
                OnlineQueueEntry.queue_id == queue.id,
            )
            .populate_existing()
            .with_for_update()
            .first()
        )
        if entry is None:
            raise NurseServingApiDomainError(
                404,
                f"Запись очереди id={queue_entry_id} не найдена в очереди "
                f"рабочего места (queue_id={queue.id})",
            )
        if entry.status != "in_progress":
            raise NurseServingApiDomainError(
                400,
                "Исполнение услуги требует запись в статусе in_progress "
                f"(начните обслуживание), текущий: {entry.status}",
            )
        if entry.visit_id is None:
            raise NurseServingApiDomainError(
                400,
                "Запись очереди не связана с визитом (начните обслуживание)",
            )

        visit_service = (
            self.db.query(VisitService)
            .filter(VisitService.id == visit_service_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if visit_service is None:
            raise NurseServingApiDomainError(
                404, f"VisitService id={visit_service_id} не найден"
            )
        if visit_service.visit_id != entry.visit_id:
            raise NurseServingApiDomainError(
                400,
                f"VisitService id={visit_service_id} принадлежит визиту "
                f"id={visit_service.visit_id}, а не визиту записи "
                f"(visit_id={entry.visit_id})",
            )
        service = (
            self.db.query(Service)
            .filter(Service.id == visit_service.service_id)
            .first()
        )
        if service is None or not _service_routed_to_station(service, resource):
            raise NurseServingApiDomainError(
                400,
                f"Услуга VisitService id={visit_service_id} не обслуживается "
                f"на этой станции (queue_tag={resource.queue_tag!r}, "
                "requires_doctor=false требуется)",
            )

        # Attempt serialization under the VisitService row lock.
        attempts = (
            self.db.query(ServiceExecution)
            .filter(ServiceExecution.visit_service_id == visit_service_id)
            .order_by(ServiceExecution.attempt_no.asc())
            .all()
        )
        in_progress = next((a for a in attempts if a.status == "in_progress"), None)
        if in_progress is not None:
            if in_progress.started_by_user_id == user_id:
                # Same-nurse repeat POST = no-op (the tablet contract);
                # the endpoint answers 200 instead of 201 via `created`.
                return {**self._execution_payload(in_progress), "created": False}
            raise NurseServingApiDomainError(
                409,
                "Услуга уже исполняется другой медсестрой "
                f"(execution id={in_progress.id}, "
                f"started_by_user_id={in_progress.started_by_user_id})",
            )
        latest = attempts[-1] if attempts else None
        if latest is not None and latest.status == "completed":
            raise NurseServingApiDomainError(
                409,
                f"Услуга уже выполнена (execution id={latest.id}, "
                f"attempt_no={latest.attempt_no})",
            )

        execution = ServiceExecution(
            visit_service_id=visit_service_id,
            queue_entry_id=entry.id,
            attempt_no=(latest.attempt_no + 1) if latest is not None else 1,
            status="in_progress",
            started_by_user_id=user_id,
            started_at=_now(),
        )
        self.db.add(execution)
        self.db.flush()

        self._audit(
            action="CREATE",
            table_name="service_executions",
            row_id=execution.id,
            description=(
                "NURSE-V2 N2-3: nurse "
                f"{acting_username or user_id} started attempt "
                f"no={execution.attempt_no} of visit_service_id="
                f"{visit_service_id} (entry id={entry.id}) at "
                f"queue_resource_id={queue_resource_id}"
            ),
            actor=self._actor_or_stub(user_id),
            new_values={
                "visit_service_id": visit_service_id,
                "queue_entry_id": entry.id,
                "attempt_no": execution.attempt_no,
                "status": "in_progress",
                "started_by_user_id": user_id,
            },
            audit_context=audit_context,
        )
        self.db.commit()
        self.db.refresh(execution)
        return {**self._execution_payload(execution), "created": True}

    def _execution_or_error(self, execution_id: int) -> ServiceExecution:
        execution = (
            self.db.query(ServiceExecution)
            .filter(ServiceExecution.id == execution_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if execution is None:
            raise NurseServingApiDomainError(
                404, f"ServiceExecution id={execution_id} не найден"
            )
        return execution

    def _execution_station_resource(
        self, execution: ServiceExecution
    ) -> tuple[QueueResource | None, OnlineQueueEntry | None]:
        """The station (resource + entry) an execution belongs to."""
        entry = None
        if execution.queue_entry_id is not None:
            entry = self.db.get(OnlineQueueEntry, execution.queue_entry_id)
            if entry is not None and entry.queue is not None:
                queue = entry.queue
                if queue.queue_resource_id is not None:
                    resource = self.db.get(QueueResource, queue.queue_resource_id)
                    if resource is not None:
                        return resource, entry
                if queue.queue_tag is not None:
                    # Bridged/legacy surface: resolve via the tag axis.
                    resource = (
                        self.db.query(QueueResource)
                        .filter(QueueResource.queue_tag == queue.queue_tag)
                        .first()
                    )
                    if resource is not None:
                        return resource, entry
        return None, entry

    def _execution_station_or_error(
        self, execution: ServiceExecution
    ) -> tuple[QueueResource, OnlineQueueEntry]:
        """The execution's station, with the FULL chain validated (codex P1).

        The graceful-drain bypass must never authorize a mutation whose
        station identity is not reconstructable AND consistent:
        - the entry must exist (``queue_entry_id`` is nullable — an entry
          purge SET NULLs it; an orphaned execution has no servable
          station context, only the ledger keeps its history);
        - the resource must resolve from the entry's queue (owner axis or
          the bridged tag axis);
        - the CHAIN must be consistent: the execution's VisitService
          belongs to the entry's visit AND routes to that resource (D3:
          queue_tag match + requires_doctor=false). Without this a
          hand-applied cross-station row (station-A entry, station-B
          service) let an A-assigned starter complete B-routed work and
          the last-completer check — seeing NO station-A services — flip
          the entry to served on the empty-station predicate.
        """
        resource, entry = self._execution_station_resource(execution)
        if resource is None or entry is None:
            raise NurseServingApiDomainError(
                403,
                "Исполнение id="
                f"{execution.id} не связано с записью очереди рабочего "
                "места (контекст станции невосстановим) — операция "
                "недоступна с обслуживающей поверхности",
            )
        visit_service = self.db.get(VisitService, execution.visit_service_id)
        service = (
            self.db.get(Service, visit_service.service_id)
            if visit_service is not None
            else None
        )
        if (
            visit_service is None
            or entry.visit_id is None
            or visit_service.visit_id != entry.visit_id
            or service is None
            or not _service_routed_to_station(service, resource)
        ):
            raise NurseServingApiDomainError(
                403,
                "Исполнение id="
                f"{execution.id} не согласовано со станцией "
                f"(queue_resource_id={resource.id}): услуга не принадлежит "
                "визиту записи или не маршрутизирована на эту станцию "
                "(D3) — операция недоступна",
            )
        return resource, entry

    def _authorize_execution_terminal(
        self, execution: ServiceExecution, user_id: int
    ) -> tuple[QueueResource, OnlineQueueEntry]:
        """Validated station + ACTIVE assignment, or the bounded drain rule.

        Codex round-1 P1: the station chain is validated FIRST — the
        starter bypass (below) never applies to an orphaned or
        cross-station execution. The drain (the brief's mid-flight
        deactivation decision): the STARTER of an in_progress attempt
        may always END it — without this, a deactivation mid-flight
        would strand the row in_progress forever (the 0072 partial
        unique one-active index would block every retry). The drain
        cannot claim anything new.
        """
        resource, entry = self._execution_station_or_error(execution)
        assignment = (
            self.db.query(NurseWorkplaceAssignment)
            .filter(
                NurseWorkplaceAssignment.user_id == user_id,
                NurseWorkplaceAssignment.queue_resource_id == resource.id,
                NurseWorkplaceAssignment.is_active.is_(True),
            )
            .first()
        )
        if assignment is not None:
            return resource, entry
        if execution.started_by_user_id == user_id:
            # Graceful drain: the starter ends the attempt she holds —
            # on a VALIDATED station chain only (see above).
            return resource, entry
        raise NurseServingApiDomainError(
            403,
            "Нет активного назначения на рабочее место "
            f"(queue_resource_id={resource.id}) для завершения исполнения "
            f"id={execution.id}",
        )

    def complete_execution(
        self,
        user_id: int,
        execution_id: int,
        *,
        acting_username: str | None = None,
        audit_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """in_progress -> completed; the last-completer flips the entry.

        ``performed_by`` = the ACTUAL completing nurse (D1: may differ
        from the starter). The flip check runs under the entry row lock
        as a guarded UPDATE — exactly one concurrent completion flips,
        ``served_by_user_id`` is the flipping nurse (§6).
        """
        execution = self._execution_or_error(execution_id)

        # Codex round-1 P2: the same-PERFORMER terminal replay is checked
        # BEFORE the assignment authorization — a nurse who completed the
        # attempt and lost the response must still get her 200 no-op after
        # a mid-flight assignment deactivation (the replay discloses only
        # her own already-committed attribution, never new state).
        if execution.status == "completed":
            if execution.performed_by_user_id == user_id:
                return self._replay_payload(execution)

        resource, _entry = self._authorize_execution_terminal(execution, user_id)

        if execution.status == "completed":
            raise NurseServingApiDomainError(
                409,
                f"Исполнение id={execution_id} уже завершено "
                f"(performed_by_user_id={execution.performed_by_user_id})",
            )
        if execution.status != "in_progress":
            raise NurseServingApiDomainError(
                400,
                "Завершить можно только исполнение в статусе in_progress, "
                f"текущий: {execution.status}",
            )

        changed_at = _now()
        execution.status = "completed"
        execution.performed_by_user_id = user_id
        execution.completed_at = changed_at

        entry_served = False
        entry_served_by: int | None = None
        entry = (
            self.db.get(OnlineQueueEntry, execution.queue_entry_id)
            if execution.queue_entry_id is not None
            else None
        )
        if entry is not None and resource is not None and entry.status == "in_progress":
            entry = (
                self.db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.id == entry.id)
                .populate_existing()
                .with_for_update()
                .first()
            )
            if entry is not None and entry.status == "in_progress":
                if self._entry_all_station_services_done(entry, resource):
                    # Guarded flip: exactly one concurrent completion
                    # wins; the loser's UPDATE no-ops (rowcount=0).
                    result = self.db.execute(
                        update(OnlineQueueEntry)
                        .where(
                            OnlineQueueEntry.id == entry.id,
                            OnlineQueueEntry.status == "in_progress",
                        )
                        .values(
                            status="served",
                            served_by_user_id=user_id,
                            served_at=changed_at,
                            updated_at=changed_at,
                        )
                    )
                    if result.rowcount:
                        entry_served = True
                        entry_served_by = user_id
                        self._audit(
                            action="UPDATE",
                            table_name="online_queue_entries",
                            row_id=entry.id,
                            description=(
                                "NURSE-V2 N2-3: last-completer flip — nurse "
                                f"{acting_username or user_id} completed the "
                                f"final station service (execution "
                                f"id={execution.id}); entry "
                                f"id={entry.id} served"
                            ),
                            actor=self._actor_or_stub(user_id),
                            old_values={"status": "in_progress"},
                            new_values={
                                "status": "served",
                                "served_by_user_id": user_id,
                            },
                            audit_context=audit_context,
                        )

        self._audit(
            action="UPDATE",
            table_name="service_executions",
            row_id=execution.id,
            description=(
                "NURSE-V2 N2-3: nurse "
                f"{acting_username or user_id} completed attempt "
                f"no={execution.attempt_no} of visit_service_id="
                f"{execution.visit_service_id}"
                + (" (entry served — last station service)" if entry_served else "")
            ),
            actor=self._actor_or_stub(user_id),
            old_values={"status": "in_progress"},
            new_values={
                "status": "completed",
                "performed_by_user_id": user_id,
            },
            audit_context=audit_context,
        )
        self.db.commit()
        self.db.refresh(execution)
        return self._execution_payload(
            execution,
            entry_served=entry_served,
            entry_served_by_user_id=entry_served_by,
        )

    def incomplete_execution(
        self,
        user_id: int,
        execution_id: int,
        reason: str,
        *,
        acting_username: str | None = None,
        audit_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """in_progress -> incomplete (reason mandatory; NO entry flip).

        An incomplete attempt leaves the service PENDING (the retry is a
        NEW attempt, D1) — the entry must not flip to served; the nurse
        either retries or terminates the entry explicitly.
        """
        execution = self._execution_or_error(execution_id)

        # Codex round-1 P2: the same-PERFORMER terminal replay precedes
        # the assignment authorization (see complete_execution).
        if execution.status == "incomplete":
            if execution.performed_by_user_id == user_id:
                return self._replay_payload(execution)

        _resource, _entry = self._authorize_execution_terminal(execution, user_id)

        if execution.status == "incomplete":
            raise NurseServingApiDomainError(
                409,
                f"Исполнение id={execution_id} уже отмечено незавершённым "
                f"(performed_by_user_id={execution.performed_by_user_id})",
            )
        if execution.status != "in_progress":
            raise NurseServingApiDomainError(
                400,
                "Отметить незавершённым можно только исполнение в статусе "
                f"in_progress, текущий: {execution.status}",
            )

        changed_at = _now()
        execution.status = "incomplete"
        execution.performed_by_user_id = user_id
        execution.completed_at = changed_at
        execution.incomplete_reason = reason

        self._audit(
            action="UPDATE",
            table_name="service_executions",
            row_id=execution.id,
            description=(
                "NURSE-V2 N2-3: nurse "
                f"{acting_username or user_id} marked attempt "
                f"no={execution.attempt_no} of visit_service_id="
                f"{execution.visit_service_id} incomplete "
                f"(reason_present=True, reason_length={len(reason)})"
            ),
            actor=self._actor_or_stub(user_id),
            old_values={"status": "in_progress"},
            new_values={
                "status": "incomplete",
                "performed_by_user_id": user_id,
                # Codex round-3 P1 (PHI containment): the free-text
                # clinical reason lives ONLY in the clinical row
                # (service_executions.incomplete_reason); the general
                # UserAuditLog is a different access/search/export
                # surface, so it records presence + length, never
                # the text itself.
                "reason_present": True,
                "reason_length": len(reason),
            },
            audit_context=audit_context,
        )
        self.db.commit()
        self.db.refresh(execution)
        return self._execution_payload(execution)

    def _entry_all_station_services_done(
        self, entry: OnlineQueueEntry, resource: QueueResource
    ) -> bool:
        """The last-completer predicate (D3 + D1).

        Every VisitService of the entry's visit ROUTED to this station
        (queue_tag match + requires_doctor=false) is done: some attempt
        completed it, or its LATEST attempt was explicitly cancelled.
        Doctor-routed and other-station services never block the flip.
        An entry whose visit has NO station-routed services flips on the
        first completion of any linked execution (the served state is
        the nurse's explicit terminal act for the station event).
        """
        if entry.visit_id is None:
            return True
        rows = (
            self.db.query(VisitService, Service)
            .outerjoin(Service, VisitService.service_id == Service.id)
            .filter(VisitService.visit_id == entry.visit_id)
            .all()
        )
        station_ids = [
            vs.id
            for vs, svc in rows
            if svc is not None and _service_routed_to_station(svc, resource)
        ]
        if not station_ids:
            return True
        attempts = (
            self.db.query(ServiceExecution)
            .filter(ServiceExecution.visit_service_id.in_(station_ids))
            .order_by(ServiceExecution.attempt_no.asc())
            .all()
        )
        by_service: dict[int, list[ServiceExecution]] = {}
        for attempt in attempts:
            by_service.setdefault(attempt.visit_service_id, []).append(attempt)
        for visit_service_id in station_ids:
            service_attempts = by_service.get(visit_service_id, [])
            if not service_attempts:
                return False
            if any(a.status == "completed" for a in service_attempts):
                continue
            latest = service_attempts[-1]
            if latest.status == "cancelled":
                continue
            return False
        return True

    # ------------------------------------------------------------------
    # operations — entry-level terminals
    # ------------------------------------------------------------------

    def _terminal_entry(
        self,
        user_id: int,
        queue_resource_id: int,
        entry_id: int,
        *,
        allowed_from: tuple[str, ...],
    ) -> tuple[QueueResource, DailyQueue, OnlineQueueEntry]:
        resource = self._resource_or_error(queue_resource_id)
        self._active_assignment_or_error(user_id, queue_resource_id)
        queue = self._station_queue_or_error(resource)
        entry = (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.id == entry_id,
                OnlineQueueEntry.queue_id == queue.id,
            )
            .populate_existing()
            .with_for_update()
            .first()
        )
        if entry is None:
            raise NurseServingApiDomainError(
                404,
                f"Запись очереди id={entry_id} не найдена в очереди "
                f"рабочего места (queue_id={queue.id})",
            )
        if entry.status not in allowed_from:
            raise NurseServingApiDomainError(
                400,
                f"Недопустимый переход из статуса {entry.status} "
                f"(допустимо: {', '.join(allowed_from)})",
            )
        return resource, queue, entry

    def mark_entry_no_show(
        self,
        user_id: int,
        queue_resource_id: int,
        entry_id: int,
        *,
        acting_username: str | None = None,
        audit_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """waiting|called -> no_show (QUEUE-level only, siblings untouched).

        The N2-3 brief's sibling decision: no_show does NOT touch the
        visit's pending VisitServices or any ServiceExecution — the
        patient may be restored (the existing Admin restore path) and
        serving continues. Structurally no in_progress execution can be
        linked (executions require an in_progress entry), the defensive
        409 below keeps that invariant honest under hand-applied data.
        """
        resource, _queue, entry = self._terminal_entry(
            user_id,
            queue_resource_id,
            entry_id,
            allowed_from=("waiting", "called"),
        )
        linked_in_progress = (
            self.db.query(ServiceExecution)
            .filter(
                ServiceExecution.queue_entry_id == entry.id,
                ServiceExecution.status == "in_progress",
            )
            .count()
        )
        if linked_in_progress:
            raise NurseServingApiDomainError(
                409,
                "Запись связана с незавершённым исполнением услуги — "
                "завершите или отмените исполнение сначала",
            )

        prior_status = entry.status
        changed_at = _now()
        entry.status = "no_show"
        entry.updated_at = changed_at

        self._audit(
            action="MARK_NO_SHOW",
            table_name="online_queue_entries",
            row_id=entry.id,
            description=(
                "NURSE-V2 N2-3: nurse "
                f"{acting_username or user_id} marked entry "
                f"id={entry.id} (number={entry.number}) no_show at "
                f"queue_resource_id={queue_resource_id} "
                f"(cabinet={self._lookup_cabinet(user_id, resource)!r})"
            ),
            actor=self._actor_or_stub(user_id),
            old_values={"status": prior_status},
            new_values={"status": "no_show"},
            audit_context=audit_context,
        )
        self.db.commit()
        self.db.refresh(entry)
        return {"entry_id": entry.id, "new_status": entry.status, "reason": None}

    def _lookup_cabinet(self, user_id: int, resource: QueueResource) -> str | None:
        assignment = (
            self.db.query(NurseWorkplaceAssignment)
            .filter(
                NurseWorkplaceAssignment.user_id == user_id,
                NurseWorkplaceAssignment.queue_resource_id == resource.id,
                NurseWorkplaceAssignment.is_active.is_(True),
            )
            .first()
        )
        if assignment is None:
            return resource.default_cabinet
        return self._effective_cabinet(assignment, resource)

    def mark_entry_incomplete(
        self,
        user_id: int,
        queue_resource_id: int,
        entry_id: int,
        reason: str,
        *,
        acting_username: str | None = None,
        audit_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """called|in_progress -> incomplete (entry terminal, reason mandatory).

        409 while any in_progress execution is linked: each attempt must
        be resolved explicitly (complete/incomplete) — an implicit
        auto-cancel would be unauditable for billing/medical purposes.
        """
        _resource, _queue, entry = self._terminal_entry(
            user_id,
            queue_resource_id,
            entry_id,
            allowed_from=("called", "in_progress"),
        )
        linked_in_progress = (
            self.db.query(ServiceExecution)
            .filter(
                ServiceExecution.queue_entry_id == entry.id,
                ServiceExecution.status == "in_progress",
            )
            .count()
        )
        if linked_in_progress:
            raise NurseServingApiDomainError(
                409,
                "Запись связана с незавершённым исполнением услуги "
                f"({linked_in_progress}) — завершите или отметьте "
                "незавершённым каждое исполнение сначала",
            )

        prior_status = entry.status
        changed_at = _now()
        entry.status = "incomplete"
        entry.incomplete_reason = reason
        entry.updated_at = changed_at

        self._audit(
            action="MARK_INCOMPLETE",
            table_name="online_queue_entries",
            row_id=entry.id,
            description=(
                "NURSE-V2 N2-3: nurse "
                f"{acting_username or user_id} marked entry "
                f"id={entry.id} (number={entry.number}) incomplete "
                f"(reason_present=True, reason_length={len(reason)})"
            ),
            actor=self._actor_or_stub(user_id),
            old_values={"status": prior_status},
            # Codex round-3 P1 (PHI containment): same contract as the
            # execution-level incomplete — the clinical text stays ONLY
            # in online_queue_entries.incomplete_reason; the general
            # audit ledger records presence + length, never the text.
            new_values={
                "status": "incomplete",
                "reason_present": True,
                "reason_length": len(reason),
            },
            audit_context=audit_context,
        )
        self.db.commit()
        self.db.refresh(entry)
        return {
            "entry_id": entry.id,
            "new_status": entry.status,
            "reason": entry.incomplete_reason,
        }
