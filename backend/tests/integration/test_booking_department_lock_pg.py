"""Round-13 (PR #3386 review round-2) — the REAL two-session department
lock proof.

The sqlite round-12 pin (``test_create_revalidates_department_under_lock``)
runs the "admin" deactivation on the SAME session that serves the booking:
``commit()`` expires the identity map, so the next access is forced to
re-read and the race can never reproduce. The real race is:

    Session A (booking):
        Department.active == True already in the identity map
        (the earlier routing reads / ``doctor_row.department`` load
        put it there);

    Session B (admin):
        UPDATE departments SET active = false; COMMIT;

    Session A:
        SELECT ... FOR UPDATE  -> PostgreSQL delivers the NEW row
        version, but SQLAlchemy's identity map returns the already
        loaded instance WITHOUT refreshing its attributes unless the
        query carries ``populate_existing()``.

Without ``populate_existing()`` the ``active`` check answers the stale
``True`` and the booking persists ``department_id`` pointing at a
deactivated department — exactly the defect round-12 claimed closed.

This module pins the cross-transaction behavior against real PostgreSQL
(same gating pattern as ``test_nurse_serving_pg_concurrency``): a
PostgreSQL ``DATABASE_URL`` (CI or an explicitly disposable clinic_test*
database); SQLite runs skip. Every test uses TWO independent sessions
with SEPARATE transactions — the mutation that must be observed is
always committed by a session the booking session cannot see into.

Schema is disposable (uuid-suffixed), built via ``create_all``.
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.department import Department
from app.services.appointment_booking_routing import (
    lock_department_for_booking,
    resolve_booking_department,
    resolve_doctor_routing_department,
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def booking_pg_engine():
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        pytest.skip(
            "booking department lock proof requires DATABASE_URL for PostgreSQL"
        )
    url = make_url(raw_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("booking department lock proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_booking_lock_" + uuid.uuid4().hex
    admin = create_engine(url, pool_pre_ping=True)
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(schema))
    except Exception as exc:  # noqa: BLE001 - environmental skip, not product logic
        admin.dispose()
        pytest.skip(f"disposable PostgreSQL unavailable: {exc}")

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "options": (
                f"-csearch_path={schema} "
                "-cstatement_timeout=15000 -clock_timeout=15000"
            )
        },
    )
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _mk_department(db: Session, *, key: str) -> Department:
    department = Department(
        key=key,
        name_ru=f"Кардиология {key}",
        name_uz=key,
        active=True,
    )
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def _deactivate_from_other_session(engine, department_id: int) -> None:
    """The admin's deactivation on a FULLY SEPARATE session/transaction.

    This is the commit the booking session must observe through its
    locked re-read; the sqlite same-session harness cannot reproduce it
    (its commit expires the very identity map under test).
    """
    with Session(engine) as admin_session:
        row = admin_session.get(Department, department_id)
        assert row is not None
        row.active = False
        admin_session.commit()


def test_lock_refreshes_stale_identity_map(booking_pg_engine):
    """``lock_department_for_booking`` must observe the committed
    deactivation even though the SAME Session already holds the row in
    its identity map (round-13 owner P1)."""
    engine = booking_pg_engine
    token = uuid.uuid4().hex[:8]

    with Session(engine) as booking_session:
        department = _mk_department(booking_session, key=f"cardio_{token}")
        department_id = int(department.id)

        # Re-read AFTER the setup commit so the identity map holds a
        # live (not expired) instance — the pre-deactivation state.
        loaded = (
            booking_session.query(Department)
            .filter(Department.id == department_id)
            .first()
        )
        assert loaded is not None and loaded.active is True

        _deactivate_from_other_session(engine, department_id)

        with pytest.raises(HTTPException) as exc_info:
            lock_department_for_booking(booking_session, loaded)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == {"reason": "department_inactive"}

        # The locked re-read must have REFRESHED the ORM instance, not
        # only the row: the caller's object can no longer claim active.
        assert loaded.active is False

        assert (
            booking_session.query(Appointment).count() == 0
        ), "a raced deactivation never materializes an appointment"


def test_resolve_for_update_refreshes_stale_identity_map(booking_pg_engine):
    """``resolve_booking_department(..., for_update=True)`` — the
    department-only create path — carries the same populate_existing
    refresh: the plain read earlier in the request leaves the row in the
    identity map, and the locked re-read must still see the
    deactivation committed by the other session."""
    engine = booking_pg_engine
    token = uuid.uuid4().hex[:8]

    with Session(engine) as booking_session:
        department = _mk_department(booking_session, key=f"derma_{token}")
        department_id = int(department.id)
        key = str(department.key)

        # The plain (unlocked) resolve — the exact first read the
        # create path performs; loads the PK into the identity map.
        first_seen = resolve_booking_department(booking_session, key)
        assert first_seen is not None and first_seen.active is True

        _deactivate_from_other_session(engine, department_id)

        with pytest.raises(HTTPException) as exc_info:
            resolve_booking_department(booking_session, key, for_update=True)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == {"reason": "department_inactive"}
        assert first_seen.active is False


def test_doctor_booking_sequence_refuses_raced_deactivation(booking_pg_engine):
    """The full doctor-booking read sequence (resolve by key -> canonical
    routing -> FOR UPDATE lock) with the admin deactivation committed
    BETWEEN the routing reads and the lock. The lock must refuse with
    the SAME 400 department_inactive contract and no appointment may
    exist afterwards."""
    engine = booking_pg_engine
    token = uuid.uuid4().hex[:8]

    with Session(engine) as booking_session:
        department = _mk_department(booking_session, key=f"cardio_{token}")
        department_id = int(department.id)
        key = str(department.key)

        doctor = Doctor(
            specialty="Кардиология",
            department_id=department_id,
            active=True,
        )
        booking_session.add(doctor)
        booking_session.commit()

        # The create-path reads: the submitted key resolves (plain), the
        # canonical routing loads ``doctor_row.department`` — BOTH put
        # the same PK into the identity map BEFORE the final lock.
        submitted = resolve_booking_department(booking_session, key)
        routing_department = resolve_doctor_routing_department(doctor, submitted)
        assert routing_department.active is True

        _deactivate_from_other_session(engine, department_id)

        with pytest.raises(HTTPException) as exc_info:
            lock_department_for_booking(booking_session, routing_department)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == {"reason": "department_inactive"}

    with Session(engine) as verifier:
        assert verifier.query(Appointment).count() == 0, (
            "the booking session refused before any INSERT: no appointment "
            "may reference the deactivated department"
        )
