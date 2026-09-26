"""Merged-#3340 follow-up (owner P1): the portal booking's FINAL routing
department must be re-read under the booking row lock and re-validated
ATOMICALLY with the appointment INSERT.

The plain resolves (`_resolve_portal_department` / the doctor's canonical
`doctor.department` relationship load) guard only the SNAPSHOT they
observed: an admin deactivation (or a hard delete) committing between that
snapshot and the booking transaction previously produced an appointment
whose persisted `department_id` pointed at an INACTIVE department.

The helper `lock_department_for_booking` re-reads with
``.populate_existing().with_for_update()``. ``populate_existing()`` is the
load-bearing half on ANY dialect: the Department object is already in the
session identity map when the final routing context is known, and
``with_for_update()`` alone does NOT rewrite already-loaded attributes —
the re-check would read the stale ``active=True``.

SQLite pins here: the attribute-refresh contract and the endpoint wiring
(refusal + no INSERT + denied audit trail, 400-before-409 ordering). The
row-lock serialization itself is dialect-enforced and pinned on a
disposable PostgreSQL (test_portal_department_booking_lock_pg.py).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.department import Department
from app.models.patient_access_audit import PatientAccessAuditLog
from app.services.appointment_slot_guard import lock_department_for_booking

# ---------------------------------------------------------------------------
# Fixtures mirrored from the portal suite (module-local there).
# ---------------------------------------------------------------------------


@pytest.fixture
def portal_department(db_session: Session) -> Department:
    row = db_session.query(Department).filter(Department.key == "cardio").first()
    if not row:
        row = Department(
            key="cardio",
            name_ru="Кардиология",
            name_uz="Kardiologiya",
            active=True,
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
    return row


@pytest.fixture
def linked_patient_headers(client: TestClient, db_session: Session, test_patient):
    from app.core.security import get_password_hash
    from app.models.user import User

    user = db_session.query(User).filter(User.username == "portal_patient").first()
    if not user:
        user = User(
            username="portal_patient",
            email="portal_patient@test.com",
            hashed_password=get_password_hash("portal123"),
            role="Patient",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        db_session.flush()
        test_patient.user_id = user.id
        db_session.commit()
        db_session.refresh(user)

    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


def _future_date() -> str:
    return str(date.today() + timedelta(days=3))


# ---------------------------------------------------------------------------
# Helper-level pins: the identity-map refresh contract.
# ---------------------------------------------------------------------------


class TestLockDepartmentForBooking:
    def test_none_passthrough(self, db_session):
        assert lock_department_for_booking(db_session, None) is None

    def test_active_row_is_returned(self, db_session, portal_department):
        locked = lock_department_for_booking(db_session, portal_department)
        assert locked is not None
        assert int(locked.id) == int(portal_department.id)
        assert locked.active is True

    def test_stale_identity_map_is_refreshed_before_the_active_check(
        self, db_session, portal_department
    ):
        """THE pin for this fix: the department sits in the identity map with
        active=True; a concurrently COMMITTED deactivation (raw UPDATE — the
        second transaction's write) must be visible to the lock's re-read.
        Pre-fix (``with_for_update()`` without ``populate_existing()``) the
        stale object passed the check and the booking persisted an inactive
        routing context."""
        stale_view = (
            db_session.query(Department)
            .filter(Department.id == portal_department.id)
            .first()
        )
        assert stale_view.active is True, "harness sanity: seeded active"

        db_session.execute(
            text("UPDATE departments SET active = 0 WHERE id = :i"),
            {"i": int(portal_department.id)},
        )
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            lock_department_for_booking(db_session, stale_view)
        assert exc.value.status_code == 400
        assert exc.value.detail == {"reason": "department_inactive"}

    def test_row_deleted_after_resolution_is_department_unknown(
        self, db_session, portal_department
    ):
        """A concurrent hard delete between the plain resolve and the lock
        leaves NOTHING to re-read — a controlled 400, never a persisted
        appointment with a dangling/SET-NULL routing context. The resolved
        instance here is EXPIRED-AND-DELETED (the committing delete expired
        it in this session): the helper must translate that into the 400,
        not leak an ObjectDeletedError as a 500."""
        stale_view = (
            db_session.query(Department)
            .filter(Department.id == portal_department.id)
            .first()
        )
        db_session.execute(
            text("DELETE FROM departments WHERE id = :i"),
            {"i": int(portal_department.id)},
        )
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            lock_department_for_booking(db_session, stale_view)
        assert exc.value.status_code == 400
        assert exc.value.detail == {"reason": "department_unknown"}

    def test_query_finds_no_row_is_department_unknown(self, db_session):
        """The other ``department_unknown`` path: the PK survives on a
        detached value but the re-read answers no row (row deleted by a
        foreign transaction the session has not yet seen)."""
        from types import SimpleNamespace

        with pytest.raises(HTTPException) as exc:
            lock_department_for_booking(db_session, SimpleNamespace(id=987654321))
        assert exc.value.status_code == 400
        assert exc.value.detail == {"reason": "department_unknown"}


# ---------------------------------------------------------------------------
# Endpoint-level pins: wiring, ordering, no-INSERT, audit trail.
# ---------------------------------------------------------------------------


class TestPortalCreateAtomicDepartmentRevalidation:
    def _latest_denied(self, db_session, subject_patient_id):
        return (
            db_session.query(PatientAccessAuditLog)
            .filter(
                PatientAccessAuditLog.subject_patient_id == subject_patient_id,
                PatientAccessAuditLog.outcome == "denied",
            )
            .order_by(PatientAccessAuditLog.id.desc())
            .first()
        )

    def test_department_deactivated_after_resolution_is_refused_before_insert(
        self,
        client,
        db_session,
        test_patient,
        linked_patient_headers,
        portal_department,
        monkeypatch,
    ):
        """Full production interleaving, deterministic: the endpoint resolves
        the department (plain SELECT), THEN the admin transaction commits a
        deactivation, THEN the booking transaction must refuse. Pre-fix the
        snapshot-time check passed and the appointment was created."""
        from app.api.v1.endpoints import patient_portal as pp_module

        real_resolve = pp_module._resolve_portal_department

        def resolve_then_concurrent_deactivation(db, department):
            row = real_resolve(db, department)
            # The concurrently committed admin write, between the resolve
            # and the booking lock (raw SQL — a foreign transaction's
            # committed state the identity map does not know about).
            db.execute(
                text("UPDATE departments SET active = 0 WHERE id = :i"),
                {"i": int(row.id)},
            )
            db.commit()
            return row

        monkeypatch.setattr(
            pp_module,
            "_resolve_portal_department",
            resolve_then_concurrent_deactivation,
        )

        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "dept-lock-1"},
            json={
                "appointmentDate": _future_date(),
                "department": portal_department.key,
            },
        )
        assert created.status_code == 400, created.text
        assert created.json()["detail"]["reason"] == "department_inactive"

        assert (
            db_session.query(Appointment).count() == 0
        ), "the refused booking must not persist anything"

        row = self._latest_denied(db_session, test_patient.id)
        assert row is not None, "the refusal leaves the per-patient trail row"
        assert row.extra_data["reason"] == "department_inactive"
        assert row.extra_data["surface"] == "jwt_portal"

    def test_department_deleted_after_resolution_is_refused_before_insert(
        self,
        client,
        db_session,
        test_patient,
        linked_patient_headers,
        portal_department,
        monkeypatch,
    ):
        from app.api.v1.endpoints import patient_portal as pp_module

        real_resolve = pp_module._resolve_portal_department

        def resolve_then_concurrent_delete(db, department):
            row = real_resolve(db, department)
            db.execute(
                text("DELETE FROM departments WHERE id = :i"),
                {"i": int(row.id)},
            )
            db.commit()
            return row

        monkeypatch.setattr(
            pp_module, "_resolve_portal_department", resolve_then_concurrent_delete
        )

        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "dept-lock-2"},
            json={
                "appointmentDate": _future_date(),
                "department": portal_department.key,
            },
        )
        assert created.status_code == 400, created.text
        assert created.json()["detail"]["reason"] == "department_unknown"
        assert db_session.query(Appointment).count() == 0

    def test_department_refusal_outranks_slot_conflict(
        self,
        client,
        db_session,
        test_patient,
        test_doctor,
        linked_patient_headers,
        portal_department,
        monkeypatch,
    ):
        """Ordering contract preserved: the department re-validation (400)
        happens BEFORE the occupancy check (409) — a routing refusal never
        reports an unrelated slot conflict."""
        from app.api.v1.endpoints import patient_portal as pp_module

        test_doctor.department_id = portal_department.id
        db_session.commit()

        # An occupied slot for the SAME doctor/date/time.
        db_session.add(
            Appointment(
                patient_id=test_patient.id,
                doctor_id=test_doctor.id,
                department_id=portal_department.id,
                appointment_date=date.today() + timedelta(days=3),
                appointment_time="10:00",
                status="scheduled",
            )
        )
        db_session.commit()

        real_resolve = pp_module._resolve_portal_department

        def resolve_then_concurrent_deactivation(db, department):
            row = real_resolve(db, department)
            db.execute(
                text("UPDATE departments SET active = 0 WHERE id = :i"),
                {"i": int(row.id)},
            )
            db.commit()
            return row

        monkeypatch.setattr(
            pp_module,
            "_resolve_portal_department",
            resolve_then_concurrent_deactivation,
        )

        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "dept-lock-3"},
            json={
                "appointmentDate": _future_date(),
                "appointmentTime": "10:00",
                "doctorId": test_doctor.id,
                "department": portal_department.key,
            },
        )
        assert created.status_code == 400, created.text
        assert created.json()["detail"]["reason"] == "department_inactive"

    def test_happy_path_still_books_active_department(
        self,
        client,
        db_session,
        test_patient,
        linked_patient_headers,
        portal_department,
    ):
        """Control: the atomic re-validation must not disturb the normal
        doctorless department booking."""
        created = client.post(
            "/api/v1/patients/booking",
            headers={**linked_patient_headers, "Idempotency-Key": "dept-lock-ok-1"},
            json={
                "appointmentDate": _future_date(),
                "department": portal_department.key,
            },
        )
        assert created.status_code == 201, created.text
        appointment_id = created.json()["appointment_id"]
        row = db_session.get(Appointment, appointment_id)
        assert row is not None
        assert int(row.department_id) == int(portal_department.id)
