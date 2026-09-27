"""Atomic same-slot reservation guard for appointment write paths.

Codex P1 (lifecycle PR round-7): every writer performs a check-then-act
occupancy pre-check (``is_time_slot_occupied``) followed by an INSERT/UPDATE
that commits later. Two concurrent requests for the same doctor/date/time can
both read the slot as free before either commits — the ``appointments`` table
has no UNIQUE constraint covering the slot — so both bookings succeed and the
slot is double-booked.

Fix: serialize same-doctor writers by locking the doctor row with
``SELECT ... FOR UPDATE`` BEFORE the occupancy pre-check. The row lock is
held until the writer's own transaction commits (the booking INSERT/UPDATE
runs on the same session), so a concurrent writer for the same doctor blocks
at this call, then re-runs its occupancy check against the committed state
and receives its usual conflict response. Writers for DIFFERENT doctors take
different row locks and are never serialized against each other.

Dialect note: PostgreSQL (production) enforces the row lock; SQLite (tests)
silently drops FOR UPDATE at statement-compilation time, so existing tests
keep running unchanged — the serialization property is exercised in
production, and the wiring itself is covered by spy tests here.

Every appointment writer must call this immediately before its occupancy
check:

- web   POST/PUT /appointments            (app/api/v1/endpoints/appointments.py)
- v2    POST/PATCH /appointments/         (app/services/appointments_api_service.py)
- mobile POST /mobile/appointments/book   (app/api/v1/endpoints/mobile_api.py)
- telegram Mini App booking confirm       (app/api/v1/endpoints/telegram_webhook/_routes.py)
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import ObjectDeletedError

from app.models.clinic import Doctor
from app.models.department import Department


def lock_doctor_for_slot_reservation(
    db: Session, doctor_id: int | None
) -> Doctor | None:
    """Take the per-doctor reservation lock for the current transaction.

    Returns the locked Doctor row (or None when ``doctor_id`` is None —
    the doctorless appointment shape has no concrete slot to serialize).
    """
    if doctor_id is None:
        return None
    return db.query(Doctor).filter(Doctor.id == doctor_id).with_for_update().first()


def lock_department_for_booking(
    db: Session, department_row: Department | None
) -> Department | None:
    """Re-read the FINAL routing department under the booking row lock.

    Merged-#3340 follow-up (owner P1): the portal create resolved the
    department with a PLAIN ``SELECT`` long before the appointment INSERT
    (``_resolve_portal_department`` + ``_resolve_doctor_routing_department``),
    so a concurrent admin ``Department.active = False`` (or a DELETE) that
    committed in between was invisible: the inactive department passed the
    snapshot-time check and was persisted as the appointment's routing
    context. ``Department.active`` must be re-validated ATOMICALLY with the
    INSERT — this helper re-reads the row with

        ``.populate_existing().with_for_update()``

    in the BOOKING transaction and refuses before the insert unless the
    department is still ACTIVE:

    * ``department_unknown``  — the row vanished between resolution and the
      lock (a concurrent hard delete: the re-read answers no row, or the
      resolved instance was already expired-and-deleted — a controlled 400
      either way, never an ``ObjectDeletedError`` 500);
    * ``department_inactive`` — the department was deactivated by a
      concurrently committed transaction.

    ``populate_existing()`` is NOT optional: the department object is
    ALREADY in the session identity map by the time the final routing
    context is known (the plain resolve, or the ``doctor.department``
    relationship load), and ``with_for_update()`` alone does NOT rewrite
    already-loaded attributes — the re-check would read the STALE
    ``active=True`` and the lock would silently re-validate nothing
    (the same identity-map staleness class pinned for the booking
    department lock in PR #3386).

    The row lock is held until the booking transaction commits (the
    appointment INSERT runs on the same session), so a concurrent
    deactivate/delete serializes BEHIND the booking. ``None`` input
    (doctorless booking without a submitted department) has nothing to
    lock and passes through.

    Dialect note: PostgreSQL (production) enforces the row lock; SQLite
    (tests) silently drops FOR UPDATE — the attribute-refresh contract is
    still deterministic there and pinned, the serialization property is
    pinned on a disposable PostgreSQL.
    """
    if department_row is None:
        return None
    try:
        department_pk = int(department_row.id)
    except ObjectDeletedError:
        # The instance was expired and its row is gone (the delete committed
        # between the plain resolve and this lock) — a controlled refusal,
        # never an ObjectDeletedError leaking as a 500.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "department_unknown"},
        )
    locked_row = (
        db.query(Department)
        .filter(Department.id == department_pk)
        .populate_existing()
        .with_for_update()
        .first()
    )
    if locked_row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "department_unknown"},
        )
    if not getattr(locked_row, "active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "department_inactive"},
        )
    return locked_row
