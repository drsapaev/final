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
- the filters are NARROWED by the department axis first:
  ``Visit.department_id`` when present, else the canonical FK resolved
  from the ``Visit.department`` string (``Department.key == tag``, the
  queue-tag = department-key convention). A visit with NEITHER axis
  keeps the un-narrowed filter — the ambiguity guard below still
  protects it;
- candidates are locked FOR UPDATE and the move applies to EXACTLY ONE
  row (``appointment_date = new_day``);
- zero candidates -> nothing moves (the pre-existing no-op);
- MORE than one candidate -> :class:`AmbiguousAppointmentPairingError`
  — the caller FAILS CLOSED (its transaction rolls back, nothing moves).
  Bulk-moving every match is precisely the defect being fixed.

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
    """More than one live appointment matches the narrowed pairing.

    Raised instead of moving foreign rows: the caller must fail closed
    (rollback the transfer) — an ambiguous pairing is a data state a
    human must resolve, not something a queue transfer may guess about.
    """


def resolve_visit_department_id(db: Session, visit: Visit) -> int | None:
    """The visit's canonical department FK, when provable.

    ``Visit.department_id`` wins when present; otherwise the
    ``Visit.department`` string (the queue tag) is resolved through
    ``Department.key`` — the canonical FK resolution the owner verdict
    names as the minimum narrowing. Returns ``None`` when neither axis
    resolves (legacy visits): the caller then relies on the ambiguity
    guard alone.
    """
    if visit.department_id is not None:
        return visit.department_id
    if visit.department is None:
        return None
    row: Any = (
        db.query(Department.id).filter(Department.key == visit.department).first()
    )
    return row[0] if row is not None else None


def move_paired_appointment_to_day(
    db: Session, *, visit: Visit, new_day: date
) -> Appointment | None:
    """Move the ONE appointment paired with ``visit`` to ``new_day``.

    Returns the moved row, or ``None`` when no live appointment matches
    the (narrowed) canonical pairing. Raises
    :class:`AmbiguousAppointmentPairingError` when more than one row
    matches — the fail-closed contract; NOTHING is moved in that case
    (the caller's transaction rolls back).
    """
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

    department_id = resolve_visit_department_id(db, visit)
    if department_id is not None:
        # The owner-verdict narrowing: a resource-queue visit only ever
        # pairs with the appointment of ITS department — the sibling
        # laboratory appointment of the same patient/day must stay on
        # its own day.
        filters.append(Appointment.department_id == department_id)

    candidates = db.query(Appointment).filter(*filters).with_for_update().all()
    if not candidates:
        return None
    if len(candidates) > 1:
        raise AmbiguousAppointmentPairingError(
            f"визит id={visit.id} (patient_id={visit.patient_id}, "
            f"visit_date={visit.visit_date}, department="
            f"{visit.department!r}, department_id={visit.department_id!r}) "
            f"имеет {len(candidates)} подходящих незакрытых appointment — "
            "перенос отклонён (fail closed), сопоставление неоднозначно"
        )
    appointment = candidates[0]
    appointment.appointment_date = new_day
    return appointment
