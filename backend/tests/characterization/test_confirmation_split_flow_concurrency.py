from __future__ import annotations

import threading
import uuid
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.repositories.visit_confirmation_repository import VisitConfirmationRepository
from app.services.confirmation_security import ConfirmationSecurityService


def _make_pending_confirmation_visit(
    test_db, suffix: str
) -> tuple[str, int, int, int, int]:
    session_local = sessionmaker(bind=test_db, autocommit=False, autoflush=False)
    session = session_local()
    try:
        digit_suffix = "".join(ch for ch in suffix if ch.isdigit())[:7].ljust(7, "0")
        user = User(
            username=f"confirm_user_{suffix}",
            email=f"confirm_{suffix}@test.local",
            full_name=f"Confirm User {suffix}",
            hashed_password="hashed",
            role="Doctor",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        doctor = Doctor(
            user_id=user.id,
            specialty="cardiology",
            active=True,
        )
        session.add(doctor)
        session.commit()
        session.refresh(doctor)

        patient = Patient(
            first_name="Queue",
            last_name=f"Patient{suffix}",
            phone=f"+99890{digit_suffix}",
            birth_date=date(1990, 1, 1),
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)

        visit = Visit(
            patient_id=patient.id,
            doctor_id=doctor.id,
            visit_date=date.today(),
            visit_time="10:00",
            status="pending_confirmation",
            discount_mode="none",
            department="cardiology",
            confirmation_token=f"confirm-token-{suffix}",
            confirmation_channel="telegram",
            confirmation_expires_at=datetime.utcnow() + timedelta(hours=2),
        )
        session.add(visit)
        session.commit()
        session.refresh(visit)
        return visit.confirmation_token, visit.id, patient.id, doctor.id, user.id
    finally:
        session.close()


@pytest.mark.integration
@pytest.mark.queue
@pytest.mark.confirmation
def test_parallel_confirmation_validation_can_allow_same_pending_token(test_db):
    token, visit_id, patient_id, doctor_id, user_id = _make_pending_confirmation_visit(
        test_db,
        suffix=uuid.uuid4().hex[:8],
    )
    session_local = sessionmaker(bind=test_db, autocommit=False, autoflush=False)
    barrier = threading.Barrier(2)
    results: list[bool] = []
    lock = threading.Lock()

    def worker() -> None:
        session = session_local()
        try:
            barrier.wait()
            service = ConfirmationSecurityService(session)
            result = service.validate_confirmation_request(
                token=token,
                source_ip="127.0.0.1",
                user_agent="Mozilla/5.0",
                channel="telegram",
            )
            with lock:
                results.append(result.allowed)
        finally:
            session.close()

    try:
        threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert results == [True, True]
    finally:
        cleanup = session_local()
        try:
            cleanup.query(Visit).filter(Visit.id == visit_id).delete()
            cleanup.query(Patient).filter(Patient.id == patient_id).delete()
            cleanup.query(Doctor).filter(Doctor.id == doctor_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()


@pytest.mark.integration
@pytest.mark.queue
@pytest.mark.confirmation
def test_parallel_confirmation_pending_lookup_can_observe_same_pending_visit(test_db):
    token, visit_id, patient_id, doctor_id, user_id = _make_pending_confirmation_visit(
        test_db,
        suffix=uuid.uuid4().hex[:8],
    )
    session_local = sessionmaker(bind=test_db, autocommit=False, autoflush=False)
    barrier = threading.Barrier(2)
    observed_visit_ids: list[int | None] = []
    lock = threading.Lock()

    def worker() -> None:
        session = session_local()
        try:
            repository = VisitConfirmationRepository(session)
            barrier.wait()
            visit = repository.get_pending_visit_by_token(token)
            with lock:
                observed_visit_ids.append(visit.id if visit else None)
        finally:
            session.close()

    try:
        threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert observed_visit_ids == [visit_id, visit_id]
    finally:
        cleanup = session_local()
        try:
            cleanup.query(Visit).filter(Visit.id == visit_id).delete()
            cleanup.query(Patient).filter(Patient.id == patient_id).delete()
            cleanup.query(Doctor).filter(Doctor.id == doctor_id).delete()
            cleanup.query(User).filter(User.id == user_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()
