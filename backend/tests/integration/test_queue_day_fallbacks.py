"""Doctor-integration complete-flow host-day fallback (DOCWORKLIST-neighbor wave, 2026-11-16).

``complete_patient_visit``'s Appointment sync (``doctor_integration/
_queue_ops.py``) completes the appointment matched by patient +
visit_date + doctor. ``Visit.visit_date`` IS nullable, and
``_resolve_entry_visit`` RE-STAMPS a dateless solo visit to the queue day
before the sync runs, while the canonical pairing (patient/date/time/
doctor) can never have paired a NULL-day visit (``Appointment.
appointment_date == NULL`` matches nothing) — so the sync treats the
re-stamped host-day date as a proven visit↔appointment link: the
doctor's unrelated TODAY appointment gets completed for a visit that
belongs to no day at all. A false completion is worse than skipping the
sync with a warning. (The neighboring ``_resolve_entry_visit``
``or date.today()`` fallbacks are unreachable defensive code:
``DailyQueue.day`` is NOT NULL.)

Red-first: a dateless in-progress visit with a paid payment and the
doctor's today appointment — the sync must NOT complete that
appointment.

Run: pytest backend/tests/integration/test_queue_day_fallbacks.py -v
"""
from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.api.v1.endpoints.doctor_integration import _queue_ops as qops
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.user import User
from app.models.visit import Visit


def _mk_user(db, *, role: str = "Doctor") -> User:
    suffix = uuid4().hex[:8]
    user = User(
        username=f"{role.lower()}_{suffix}",
        email=f"{role.lower()}_{suffix}@t.local",
        full_name=f"Test {role}",
        hashed_password=get_password_hash("doctor123"),
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    return user


def _mk_doctor(db, user: User, specialty: str) -> Doctor:
    doctor = Doctor(user_id=user.id, specialty=specialty, active=True)
    db.add(doctor)
    db.flush()
    return doctor


def _mk_patient(db) -> Patient:
    suffix = uuid4().hex[:8]
    patient = Patient(
        last_name="Тестов", first_name="Пациент", birth_date=date(1990, 1, 1),
        sex="M",
        phone="+998900000000",
        email=f"p_{suffix}@t.local",
        is_deleted=False,
    )
    db.add(patient)
    db.flush()
    return patient


@pytest.mark.integration
class TestCompleteAppointmentSyncDatelessVisit:
    def test_dateless_visit_does_not_mark_todays_appointment_completed(
        self, db_session,
    ):
        """complete_patient_visit with a dateless legacy visit must NOT
        complete the doctor's TODAY appointment. Root cause: the canonical
        pairing (patient/date/time/doctor) can never pair a NULL-day visit
        (Appointment.appointment_date == NULL matches nothing), while
        _resolve_entry_visit re-stamps the dateless solo visit to the queue
        day before the appointment sync runs — syncing by that re-stamped
        date fabricates a visit↔appointment link that never existed."""
        admin = _mk_user(db_session, role="Admin")
        user = _mk_user(db_session)
        doctor = _mk_doctor(db_session, user, "dentistry")
        patient = _mk_patient(db_session)
        queue = DailyQueue(
            day=date.today(),
            specialist_id=doctor.id,
            queue_tag=f"tag_{uuid4().hex[:8]}",
            active=True,
        )
        db_session.add(queue)
        db_session.flush()
        # Explicit disjoint primary keys: complete_patient_visit's legacy
        # fallback probes the route id against Visit.id and Appointment.id
        # BEFORE the queue-entry path, and fresh SQLite tables would hand
        # every first row the same id=1, silently hitting the legacy path
        # instead of the queue-entry sync under test. Explicit PKs keep the
        # probes guaranteed to miss.
        visit = Visit(
            id=7001,
            patient_id=patient.id,
            doctor_id=doctor.id,
            visit_date=None,  # legacy defect: dateless visit (nullable)
            status="in_progress",
            source="desk",
        )
        db_session.add(visit)
        db_session.flush()
        appointment = Appointment(
            id=7002,
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=date.today(),  # TODAY (host) appointment
            status="confirmed",
        )
        db_session.add(appointment)
        payment = Payment(
            visit_id=visit.id,
            amount=100000,
            status="paid",
            method="cash",
        )
        db_session.add(payment)
        db_session.flush()
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=patient.id,
            visit_id=visit.id,
            status="in_progress",
        )
        db_session.add(entry)
        db_session.flush()
        assert entry.id not in (visit.id, appointment.id), (
            "test precondition: entry.id must not collide with visit/appointment PKs"
        )
        db_session.commit()

        qops.complete_patient_visit(
            entry_id=entry.id,
            visit_data=qops.CompleteVisitRequest(),
            db=db_session,
            current_user=admin,
        )
        db_session.expire_all()

        db_session.refresh(appointment)
        assert appointment.status != "completed", (
            "host-day fallback completed an UNRELATED today appointment for "
            "a dateless visit — the sync must skip (with a warning) instead"
        )
