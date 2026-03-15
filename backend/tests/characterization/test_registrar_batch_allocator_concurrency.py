from __future__ import annotations

import threading
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.repositories.queue_batch_repository import QueueBatchRepository

pytestmark = pytest.mark.postgres_pilot


def _create_user(session, *, suffix: str) -> User:
    user = User(
        username=f"batch_concurrency_{suffix}",
        email=f"batch_concurrency_{suffix}@test.local",
        full_name=f"Batch Concurrency {suffix}",
        hashed_password="hashed",
        role="Doctor",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    doctor = Doctor(
        user_id=user.id,
        specialty="Кардиология",
        active=True,
    )
    session.add(doctor)
    session.commit()
    session.refresh(user)
    setattr(user, "queue_doctor_id", doctor.id)
    return user


def _create_patient(session, *, suffix: str) -> Patient:
    digits = "".join(ch for ch in suffix if ch.isdigit())[:7].ljust(7, "0")
    patient = Patient(
        first_name="Batch",
        last_name=f"Patient{suffix}",
        phone=f"+99893{digits}",
        birth_date=date(1990, 1, 1),
    )
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


def _create_service(session, *, suffix: str) -> Service:
    service = Service(
        code=f"BATCH-CONC-{suffix[:6]}",
        name=f"Batch Concurrency Service {suffix}",
        price=120000.00,
        duration_minutes=20,
        active=True,
        requires_doctor=True,
        queue_tag="cardiology_common",
        is_consultation=True,
    )
    session.add(service)
    session.commit()
    session.refresh(service)
    return service


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_concurrency_characterization_repeated_submission_reuses_existing_waiting_entry(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    cardio_user,
    test_doctor,
    test_service,
):
    request_payload = {
        "patient_id": test_patient.id,
        "source": "desk",
        "services": [
            {
                "specialist_id": cardio_user.id,
                "service_id": test_service.id,
                "quantity": 1,
            }
        ],
    }

    first_response = client.post(
        "/api/v1/registrar-integration/queue/entries/batch",
        headers=registrar_auth_headers,
        json=request_payload,
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()

    second_response = client.post(
        "/api/v1/registrar-integration/queue/entries/batch",
        headers=registrar_auth_headers,
        json={
            **request_payload,
            "source": "online",
        },
    )
    assert second_response.status_code == 200
    second_payload = second_response.json()

    assert second_payload["entries"][0]["queue_id"] == first_payload["entries"][0]["queue_id"]
    assert second_payload["entries"][0]["number"] == first_payload["entries"][0]["number"]

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .all()
    )
    assert len(entries) == 1
    assert entries[0].source == "desk"
    assert entries[0].session_id is not None
    assert entries[0].status == "waiting"


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_concurrency_characterization_parallel_duplicate_reads_can_both_see_no_entry(
    test_db,
):
    session_local = sessionmaker(bind=test_db, autocommit=False, autoflush=False)
    seed = session_local()
    suffix = uuid.uuid4().hex[:8]
    try:
        specialist = _create_user(seed, suffix=suffix)
        patient = _create_patient(seed, suffix=suffix)
        _create_service(seed, suffix=suffix)
        queue = DailyQueue(
            day=date.today(),
            specialist_id=specialist.queue_doctor_id,
            queue_tag=None,
            active=True,
        )
        seed.add(queue)
        seed.commit()
        seed.refresh(queue)
        specialist_id = specialist.queue_doctor_id
        patient_id = patient.id
        queue_id = queue.id
    finally:
        seed.close()

    barrier = threading.Barrier(2)
    observed_results: list[int | None] = []
    lock = threading.Lock()

    def worker() -> None:
        session = session_local()
        try:
            repository = QueueBatchRepository(session)
            barrier.wait()
            existing_entry = repository.find_existing_active_entry(
                specialist_id=specialist_id,
                day=date.today(),
                patient_id=patient_id,
            )
            with lock:
                observed_results.append(existing_entry.id if existing_entry else None)
        finally:
            session.close()

    try:
        threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert observed_results == [None, None]
    finally:
        cleanup = session_local()
        try:
            cleanup.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.queue_id == queue_id
            ).delete()
            cleanup.query(DailyQueue).filter(DailyQueue.id == queue_id).delete()
            cleanup.query(Patient).filter(Patient.id == patient_id).delete()
            cleanup.query(User).filter(User.id == specialist_id).delete()
            cleanup.commit()
        finally:
            cleanup.close()
