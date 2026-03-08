from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.service import Service
from app.models.user import User


def _create_specialist_user(
    db_session,
    *,
    username: str,
    email: str,
    full_name: str,
) -> User:
    user = User(
        username=username,
        email=email,
        full_name=full_name,
        hashed_password="hashed",
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_service(
    db_session,
    *,
    code: str,
    name: str,
    queue_tag: str,
) -> Service:
    service = Service(
        code=code,
        name=name,
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=True,
        queue_tag=queue_tag,
        is_consultation=True,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _create_daily_queue(
    db_session,
    *,
    specialist_id: int,
) -> DailyQueue:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=specialist_id,
        queue_tag=None,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _create_existing_entry(
    db_session,
    *,
    queue_id: int,
    patient_id: int,
    patient_name: str,
    phone: str | None,
    number: int,
    status: str,
    source: str = "online",
    queue_time: datetime | None = None,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue_id,
        number=number,
        patient_id=patient_id,
        patient_name=patient_name,
        phone=phone,
        source=source,
        status=status,
        queue_time=queue_time
        or datetime.now(ZoneInfo("Asia/Tashkent")).replace(microsecond=0),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_characterization_preserves_request_source_on_create(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    cardio_user,
    test_service,
):
    response = client.post(
        "/api/v1/registrar-integration/queue/entries/batch",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "source": "morning_assignment",
            "services": [
                {
                    "specialist_id": cardio_user.id,
                    "service_id": test_service.id,
                    "quantity": 1,
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["entries"]) == 1

    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .order_by(OnlineQueueEntry.id.desc())
        .one()
    )

    assert entry.source == "morning_assignment"
    assert entry.session_id is not None
    assert entry.status == "waiting"
    assert entry.queue_time is not None
    assert payload["entries"][0]["number"] == entry.number
    assert payload["entries"][0]["queue_time"].startswith(entry.queue_time.isoformat())


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_characterization_groups_services_by_specialist_not_queue_tag(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    cardio_user,
    test_service,
):
    diagnostics_service = _create_service(
        db_session,
        code="BATCH-DIAG-01",
        name="Batch Diagnostics",
        queue_tag="cardiology_diagnostics",
    )

    response = client.post(
        "/api/v1/registrar-integration/queue/entries/batch",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "source": "desk",
            "services": [
                {
                    "specialist_id": cardio_user.id,
                    "service_id": test_service.id,
                    "quantity": 1,
                },
                {
                    "specialist_id": cardio_user.id,
                    "service_id": diagnostics_service.id,
                    "quantity": 1,
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["entries"]) == 1

    patient_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .all()
    )
    assert len(patient_entries) == 1
    assert patient_entries[0].source == "desk"


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_characterization_mixed_specialist_batch_reuses_one_and_creates_one(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    cardio_user,
    test_service,
):
    second_specialist = _create_specialist_user(
        db_session,
        username="batch_second_specialist",
        email="batch_second_specialist@test.local",
        full_name="Batch Second Specialist",
    )
    second_service = _create_service(
        db_session,
        code="BATCH-LAB-01",
        name="Batch Second Service",
        queue_tag="laboratory_general",
    )
    existing_queue = _create_daily_queue(db_session, specialist_id=cardio_user.id)
    existing_queue_time = datetime.now(ZoneInfo("Asia/Tashkent")).replace(microsecond=0)
    existing_entry = OnlineQueueEntry(
        queue_id=existing_queue.id,
        number=7,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
        queue_time=existing_queue_time,
    )
    db_session.add(existing_entry)
    db_session.commit()
    db_session.refresh(existing_entry)

    response = client.post(
        "/api/v1/registrar-integration/queue/entries/batch",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "source": "desk",
            "services": [
                {
                    "specialist_id": cardio_user.id,
                    "service_id": test_service.id,
                    "quantity": 1,
                },
                {
                    "specialist_id": second_specialist.id,
                    "service_id": second_service.id,
                    "quantity": 1,
                },
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["entries"]) == 2

    entries_by_specialist = {
        item["specialist_id"]: item for item in payload["entries"]
    }
    assert entries_by_specialist[cardio_user.id]["number"] == 7

    patient_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .order_by(OnlineQueueEntry.queue_id.asc(), OnlineQueueEntry.number.asc())
        .all()
    )
    assert len(patient_entries) == 2

    created_entry = next(entry for entry in patient_entries if entry.id != existing_entry.id)
    assert created_entry.source == "desk"
    assert created_entry.status == "waiting"
    assert entries_by_specialist[second_specialist.id]["number"] == created_entry.number

    db_session.refresh(existing_entry)
    assert existing_entry.queue_time == existing_queue_time.replace(tzinfo=None)
    assert existing_entry.source == "online"


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_characterization_existing_diagnostics_entry_reuses_existing_row(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    cardio_user,
    test_service,
):
    existing_queue = _create_daily_queue(db_session, specialist_id=cardio_user.id)
    diagnostics_entry = _create_existing_entry(
        db_session,
        queue_id=existing_queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        number=5,
        status="diagnostics",
        source="online",
    )

    response = client.post(
        "/api/v1/registrar-integration/queue/entries/batch",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "source": "desk",
            "services": [
                {
                    "specialist_id": cardio_user.id,
                    "service_id": test_service.id,
                    "quantity": 1,
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["entries"]) == 1

    queue_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.queue_id == existing_queue.id,
            OnlineQueueEntry.patient_id == test_patient.id,
        )
        .order_by(OnlineQueueEntry.number.asc())
        .all()
    )

    assert len(queue_entries) == 1
    assert queue_entries[0].id == diagnostics_entry.id
    assert queue_entries[0].status == "diagnostics"
    assert queue_entries[0].number == 5
    assert payload["entries"][0]["number"] == diagnostics_entry.number
    assert payload["entries"][0]["queue_time"].startswith(
        queue_entries[0].queue_time.isoformat()
    )


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_characterization_existing_in_service_entry_reuses_existing_row(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    cardio_user,
    test_service,
):
    existing_queue = _create_daily_queue(db_session, specialist_id=cardio_user.id)
    in_service_entry = _create_existing_entry(
        db_session,
        queue_id=existing_queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        number=9,
        status="in_service",
        source="online",
    )

    response = client.post(
        "/api/v1/registrar-integration/queue/entries/batch",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "source": "desk",
            "services": [
                {
                    "specialist_id": cardio_user.id,
                    "service_id": test_service.id,
                    "quantity": 1,
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["entries"]) == 1

    queue_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.queue_id == existing_queue.id,
            OnlineQueueEntry.patient_id == test_patient.id,
        )
        .order_by(OnlineQueueEntry.number.asc())
        .all()
    )

    assert len(queue_entries) == 1
    assert queue_entries[0].id == in_service_entry.id
    assert queue_entries[0].status == "in_service"
    assert payload["entries"][0]["number"] == in_service_entry.number
    assert payload["entries"][0]["queue_time"].startswith(
        queue_entries[0].queue_time.isoformat()
    )


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_characterization_ambiguous_active_rows_return_409(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    cardio_user,
    test_service,
):
    existing_queue = _create_daily_queue(db_session, specialist_id=cardio_user.id)
    _create_existing_entry(
        db_session,
        queue_id=existing_queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        number=4,
        status="waiting",
        source="online",
    )
    _create_existing_entry(
        db_session,
        queue_id=existing_queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        number=5,
        status="diagnostics",
        source="online",
    )

    response = client.post(
        "/api/v1/registrar-integration/queue/entries/batch",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "source": "desk",
            "services": [
                {
                    "specialist_id": cardio_user.id,
                    "service_id": test_service.id,
                    "quantity": 1,
                }
            ],
        },
    )

    assert response.status_code == 409
    payload = response.json()
    assert "Неоднозначная активная запись очереди" in payload["detail"]

    queue_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.queue_id == existing_queue.id,
            OnlineQueueEntry.patient_id == test_patient.id,
        )
        .order_by(OnlineQueueEntry.number.asc())
        .all()
    )
    assert len(queue_entries) == 2
    assert [entry.status for entry in queue_entries] == ["waiting", "diagnostics"]
