"""Corrective follow-up (owner verdict on merged #3355 + #3358 runtime):
precise Visit<->Appointment pairing when a transferred ticket re-stamps
its solo visit to the queue day.

The defect (owner P1): both serving surfaces moved the paired appointment
with a bulk ``UPDATE`` filtered ONLY by (patient, old date, non-terminal
status, doctor, appointment_time). For resource queues the whole filter
block degenerates to (patient, date, status) — ``doctor_id`` is NULL and
``appointment_time`` is NULL — so a patient holding TWO doctorless
same-day appointments (laboratory + procedures, different departments)
had BOTH rows moved when the procedures queue entry was transferred to
the next day. The Visit already carries ``department`` /
``department_id``; the move must use that axis and must never touch more
than one row.

Contract (this module, shared by the nurse serving service and the
doctor-integration queue surface — the round-43 mirror pair):

- the canonical pairing filters stay EXACTLY as before (the
  CanonicalVisitRepository vocabulary: patient / old visit_date /
  non-terminal status / doctor equality incl. the NULL axis / time with
  both spellings);
- candidate eligibility is STAGED by the department axis (codex round-1
  P1/P2 hardening):
  1. when the visit's department resolves (``Visit.department_id`` FK,
     else ``Department.key == Visit.department`` — the queue-tag =
     department-key convention): the EXACT set is the canonical filters +
     ``Appointment.department_id == visit department``;
  2. the UNSCOPED fallback set is ALWAYS the canonical filters +
     ``Appointment.department_id IS NULL`` — it serves (a) the resolvable
     case whose uniquely-matching appointment predates the department
     axis (codex round-1 P2: a single NULL-department row must still
     follow its visit instead of stranding on the old day), and (b) the
     LEGACY case where the visit's department resolves to nothing (codex
     round-1 P1: a SCOPED appointment — non-NULL department_id — then
     belongs to a KNOWN department and is provably NOT this visit's
     pair; the un-narrowed broad set is never used, so a lone
     foreign-department appointment can no longer be silently moved);
- each staged query locks its candidates FOR UPDATE and the move applies
  to EXACTLY ONE row (``appointment_date = new_day``);
- zero candidates in BOTH stages -> nothing moves (the pre-existing
  no-op — an absent appointment was always a legal state);
- MORE than one candidate in EITHER stage ->
  :class:`AmbiguousAppointmentPairingError` — the caller FAILS CLOSED
  (its transaction rolls back, nothing moves). Bulk-moving every match
  is precisely the defect being fixed.

The explicit ``Visit.appointment_id`` link (the owner's preferred
long-term shape) stays future work: it needs its own migration and a
creation-path contract; until then this module is the minimum safe
pairing the verdict mandates.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.department import Department
from app.models.visit import Visit

_NON_TERMINAL_APPOINTMENT_STATUSES = ("cancelled", "completed", "no_show")


class AmbiguousAppointmentPairingError(Exception):
    """More than one live appointment matches a pairing stage.

    Raised instead of moving foreign rows: the caller must fail closed
    (rollback the transfer) — an ambiguous pairing is a data state a
    human must resolve, not something a queue transfer may guess about.
    """

    def __init__(self, stage: str, count: int, context: str) -> None:
        self.stage = stage
        self.count = count
        super().__init__(
            f"{context}: стадия «{stage}» дала {count} подходящих "
            "незакрытых appointment — перенос отклонён (fail closed), "
            "сопоставление неоднозначно"
        )


def resolve_visit_department_id(db: Session, visit: Visit) -> int | None:
    """The visit's canonical department FK, when provable.

    ``Visit.department_id`` wins when present; otherwise the
    ``Visit.department`` string (the queue tag) is resolved through
    ``Department.key`` — the canonical FK resolution the owner verdict
    names as the minimum narrowing. Returns ``None`` when neither axis
    resolves (legacy visits): the caller then has only the UNSCOPED
    (NULL-department) eligibility stage — never the broad set.
    """
    if visit.department_id is not None:
        return visit.department_id
    if visit.department is None:
        return None
    row: Any = (
        db.query(Department.id).filter(Department.key == visit.department).first()
    )
    return row[0] if row is not None else None


def _canonical_filters(visit: Visit) -> list[Any]:
    """The CanonicalVisitRepository pairing vocabulary (unchanged)."""
    filters: list[Any] = [
        Appointment.patient_id == visit.patient_id,
        Appointment.appointment_date == visit.visit_date,
        Appointment.status.not_in(_NON_TERMINAL_APPOINTMENT_STATUSES),
    ]
    if visit.doctor_id is None:
        filters.append(Appointment.doctor_id.is_(None))
    else:
        filters.append(Appointment.doctor_id == visit.doctor_id)
    if visit.visit_time:
        hhmm = visit.visit_time[:5]
        filters.append(Appointment.appointment_time.in_((hhmm, f"{hhmm}:00")))
    else:
        filters.append(Appointment.appointment_time.is_(None))
    return filters


def _locked_candidates(
    db: Session, filters: list[Any], *, stage: str, context: str
) -> list[Appointment]:
    rows = db.query(Appointment).filter(*filters).with_for_update().all()
    if len(rows) > 1:
        raise AmbiguousAppointmentPairingError(stage, len(rows), context)
    return rows


def move_paired_appointment_to_day(
    db: Session, *, visit: Visit, new_day: date
) -> Appointment | None:
    """Move the ONE appointment paired with ``visit`` to ``new_day``.

    Returns the moved row, or ``None`` when no live appointment is
    eligible in either stage (an absent appointment is a legal no-op).
    Raises :class:`AmbiguousAppointmentPairingError` when a stage yields
    more than one row — the fail-closed contract; NOTHING is moved in
    that case (the caller's transaction rolls back).
    """
    context = (
        f"визит id={visit.id} (patient_id={visit.patient_id}, "
        f"visit_date={visit.visit_date}, department={visit.department!r}, "
        f"department_id={visit.department_id!r})"
    )
    canonical = _canonical_filters(visit)

    department_id = resolve_visit_department_id(db, visit)
    if department_id is not None:
        # Stage 1 — the EXACT set: the owner-verdict narrowing. A
        # resource-queue visit only ever pairs with the appointment of
        # ITS department; the sibling laboratory appointment of the same
        # patient/day stays on its own day.
        exact = _locked_candidates(
            db,
            [*canonical, Appointment.department_id == department_id],
            stage="точный департамент",
            context=context,
        )
        if exact:
            appointment = exact[0]
            appointment.appointment_date = new_day
            return appointment

    # Stage 2 — the UNSCOPED fallback: appointments that predate the
    # department axis. NEVER the un-narrowed broad set: a scoped
    # appointment of another department is provably not this visit's
    # pair (codex round-1 P1), while a single unscoped row remains the
    # legitimate legacy pair (codex round-1 P2) and follows its visit.
    unscoped = _locked_candidates(
        db,
        [*canonical, Appointment.department_id.is_(None)],
        stage="legacy без департамента",
        context=context,
    )
    if unscoped:
        appointment = unscoped[0]
        appointment.appointment_date = new_day
        return appointment
    return None
