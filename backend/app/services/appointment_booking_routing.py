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
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.department import Department


def resolve_booking_department(
    db: Session, department: str | None
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
    """
    if department is None or not department.strip():
        return None
    normalized_key = department.strip()
    department_row = (
        db.query(Department).filter(Department.key == normalized_key).first()
    )
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


def attach_department_id(
    payload: dict[str, Any], department_row: Department | None
) -> dict[str, Any]:
    """Attach the resolved `department_id` to an echo payload (typed field)."""
    if department_row is not None:
        payload["appointment"]["department_id"] = int(department_row.id)
    return payload
