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

from sqlalchemy.orm import Session

from app.models.clinic import Doctor


def lock_doctor_for_slot_reservation(db: Session, doctor_id: int | None) -> Doctor | None:
    """Take the per-doctor reservation lock for the current transaction.

    Returns the locked Doctor row (or None when ``doctor_id`` is None —
    the doctorless appointment shape has no concrete slot to serialize).
    """
    if doctor_id is None:
        return None
    return db.query(Doctor).filter(Doctor.id == doctor_id).with_for_update().first()
