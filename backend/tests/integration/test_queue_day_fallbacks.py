"""Doctor-integration complete-flow host-day fallback (DOCWORKLIST-neighbor wave, 2026-11-16).

``complete_patient_visit``'s Appointment sync (``doctor_integration/
_queue_ops.py`` :1215) matches the appointment with
``appointment_date == (visit.visit_date if visit.visit_date else date.today())``.
``Visit.visit_date`` IS nullable, so a legacy/import dateless visit falls
back to the HOST day: the doctor's unrelated TODAY appointment (same
patient) gets marked completed even though the visit belongs to no day
at all — a false completion is worse than skipping the sync with a
warning. (The neighboring ``_resolve_entry_visit`` ``or date.today()``
fallbacks are unreachable defensive code: ``DailyQueue.day`` is NOT NULL.)

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
        complete the doctor's TODAY appointment via the host-day fallback."""
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
        visit = Visit(            patient_id=patient.id,
            doctor_id=doctor.id,
            visit_date=None,  # legacy defect: dateless visit (nullable)
            status="in_progress",
            source="desk",
        )
        db_session.add(visit)
        db_session.flush()
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            patient_id=patient.id,
            visit_id=visit.id,
            status="in_progress",
        )
        db_session.add(entry)
        appointment = Appointment(
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
