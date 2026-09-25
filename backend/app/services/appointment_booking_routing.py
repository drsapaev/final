"""Shared appointment-booking routing resolvers (PR #3340 round-11 parity).

Round-9/10 of PR #3340 gave the JWT patient portal (`POST /patients/booking`)
a canonical doctor-department routing contract. The Telegram Mini App booking
endpoints (`POST /telegram/mini-app/appointments[/preview]`) share the SAME
draft builder but kept their pre-round-9 flow: the client's `department`
string was echoed by the preview and silently DROPPED at create time, so a
doctor-booking always persisted `department_id = NULL` and a contradictory
doctor/department pair was never refused.

Both protected patient booking surfaces now resolve their routing context
through THIS module, so a preview and its create always agree and the
persisted `departments.id` is the single source every schedule join uses.
The 400 reason contract is identical on both surfaces:

* ``department_unknown`` / ``department_inactive`` — the submitted
  ``Department.key`` does not resolve to an ACTIVE row;
* ``doctor_department_missing`` — the doctor has no canonical department
  (an explicit refusal, never a NULL routing context);
* ``doctor_department_mismatch`` — the submitted department is not the
  doctor's own canonical department;
* ``department_inactive`` (canonical path) — the doctor's own department
  exists but is deactivated (round-10 owner P1).

Round-12 (owner P1, PR #3386 review): the ACTIVE check is only as strong
as the row version it read. The create endpoints re-validate the FINAL
department row under ``FOR UPDATE`` (``lock_department_for_booking``)
inside the booking transaction, so an admin deactivate/delete that races
the appointment INSERT either commits first (the locked re-read refuses
with the SAME 400 reasons) or commits after the booking — the persisted
routing context can never point at a row that is no longer active.

Round-13 (owner P1, PR #3386 review round-2): the locked re-read is only
as strong as the ORM refresh. SQLAlchemy's identity map returns the
ALREADY-LOADED instance for a PK without refreshing its attributes, so
``with_for_update()`` alone can observe a stale ``active`` even though
PostgreSQL delivered the new row version. Every locked read here also
passes ``populate_existing()`` — the same correctness-sensitive locking
pattern the repo already uses in payment/Nurse/queue guards — and the
real two-session PostgreSQL pin lives in
``tests/integration/test_booking_department_lock_pg.py``.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.department import Department
from app.services.appointment_slot_guard import (
    lock_department_for_booking as _slot_guard_department_lock,
)


def resolve_booking_department(
    db: Session, department: str | None, *, for_update: bool = False
) -> Department | None:
    """Resolve a booking `department` to an ACTIVE department row.

    The request carries the canonical `Department.key`; the persisted
    routing context is `departments.id`. Unknown keys and deactivated
    departments are rejected with 400 BEFORE any appointment is created —
    a silently-dropped department produced `department_id = NULL` rows
    (routing context loss: preview echoed a department the row never got).

    The value is STRIPPED before the lookup: the SSOT builder normalizes
    the draft (`str(value).strip()`) while resolving the RAW request string
    could 400 on `" cardio "` the preview had already accepted. Normalizing
    here keeps the resolver safe for ANY caller, not just the draft-fed
    path.

    Round-12 (owner P1, PR #3386 review): ``for_update=True`` is for the
    CREATE paths where the resolved row is the one about to be persisted —
    the row is read ``FOR UPDATE`` inside the booking transaction, so a
    concurrent admin deactivate/delete serializes: the lock acquisition
    re-reads the latest committed row version BEFORE the ``active`` check
    below, making the check atomic with the appointment INSERT. Previews
    keep the default (a non-mutating read must not take row locks).

    Round-13 (owner P1, PR #3386 review round-2): the locked read also
    carries ``populate_existing()`` — the earlier routing reads (and the
    canonical ``doctor_row.department`` load) put the same PK into the
    Session's identity map, and without the refresh flag SQLAlchemy is
    not obliged to overwrite attributes it already holds, so the
    ``active`` check could answer a PRE-deactivation value.
    """
    if department is None or not department.strip():
        return None
    normalized_key = department.strip()
    department_query = db.query(Department).filter(Department.key == normalized_key)
    if for_update:
        department_query = department_query.populate_existing().with_for_update()
    department_row = department_query.first()
    if department_row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "department_unknown"},
        )
    if not getattr(department_row, "active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "department_inactive"},
        )
    return department_row


def resolve_doctor_routing_department(
    doctor_row: Doctor,
    submitted_department_row: Department | None,
) -> Department:
    """A doctor-booking's routing department is the doctor's CANONICAL
    department — never the independently submitted string.

    The previous flows persisted the submitted `department` (or NULL when
    omitted) next to the requested doctor: a cardiology doctor booked into
    a dentistry department stored contradictory routing data (the row
    surfaced in one doctor's schedule and in the WRONG department's), and
    a doctor-only booking stored `department_id = NULL` — a routing
    context no schedule could join on. Both booking surfaces (preview and
    create) resolve through THIS helper, so preview and create always
    agree on the routing context.

    Refusals are controlled 400s BEFORE any mutation:

    * ``doctor_department_missing`` — the doctor has no canonical
      department (an explicit refusal, not a NULL routing context);
    * ``department_inactive`` — the doctor's CANONICAL department exists
      but is DEACTIVATED (round-10 owner P1): the routing helper returned
      the relationship unconditionally, so an active doctor bound to an
      inactive department still booked — the preview even echoed the
      inactive department_id the create then persisted. Every OTHER
      department path (`resolve_booking_department`) refuses inactive
      keys with this SAME reason; the canonical path refuses with the
      identical 400 (it is already part of the published booking error
      contract), so preview and create answer BEFORE any mutation and the
      persisted routing context can never point at a deactivated
      department;
    * ``doctor_department_mismatch`` — the submitted department is not
      the doctor's own. Compared by the resolved department's id, which
      is key-equivalent: the submitted row was looked up BY key.
    """
    if doctor_row.department_id is None or doctor_row.department is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "doctor_department_missing"},
        )
    department = doctor_row.department
    if not getattr(department, "active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "department_inactive"},
        )
    if submitted_department_row is not None and int(submitted_department_row.id) != int(
        doctor_row.department_id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"reason": "doctor_department_mismatch"},
        )
    return department


def lock_department_for_booking(
    db: Session, department_row: Department | None
) -> Department | None:
    """Re-validate the FINAL routing department under ``FOR UPDATE``.

    Round-12 (owner P1, PR #3386 review): the create endpoints call THIS
    immediately before persisting ``department_id`` — an admin
    deactivate/delete that races the appointment INSERT either commits
    first (controlled 400 ``department_unknown``/``department_inactive``)
    or serializes BEHIND the booking.

    PR #3386 merge note: the implementation is the SINGLE canonical
    ``appointment_slot_guard.lock_department_for_booking`` (owner-reviewed
    in #3402) — this wrapper exists so both protected booking surfaces
    (JWT portal + Telegram Mini App) keep importing the guard from THIS
    module, the SSOT entry. The slot-guard implementation is strictly
    stronger than the pre-merge local one: it additionally maps an
    expired-and-deleted instance (``ObjectDeletedError`` on the PK read)
    to the controlled 400 ``department_unknown`` instead of a 500, while
    keeping the same ``populate_existing().with_for_update()`` re-read,
    the same 400 reasons, and the same ``None`` pass-through.
    """
    return _slot_guard_department_lock(db, department_row)


def attach_department_id(
    payload: dict[str, Any], department_row: Department | None
) -> dict[str, Any]:
    """Attach the resolved `department_id` to an echo payload (typed field)."""
    if department_row is not None:
        payload["appointment"]["department_id"] = int(department_row.id)
    return payload
