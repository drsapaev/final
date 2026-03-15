from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit


def _create_specialist(
    db_session,
    *,
    username: str,
    email: str,
    full_name: str,
    specialty: str,
) -> Doctor:
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

    doctor = Doctor(
        user_id=user.id,
        specialty=specialty,
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


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
    queue_tag: str,
) -> DailyQueue:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=specialist_id,
        queue_tag=queue_tag,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _create_queue_entry(
    db_session,
    *,
    queue_id: int,
    patient_id: int,
    patient_name: str,
    phone: str | None,
    visit_id: int | None,
    number: int,
    status: str,
    source: str,
    queue_time: datetime,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue_id,
        patient_id=patient_id,
        patient_name=patient_name,
        phone=phone,
        visit_id=visit_id,
        number=number,
        status=status,
        source=source,
        queue_time=queue_time,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def _cart_payload(*, patient_id: int, visits: list[dict]) -> dict:
    return {
        "patient_id": patient_id,
        "discount_mode": "none",
        "payment_method": "cash",
        "visits": visits,
    }


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_wizard_characterization_same_day_cart_creates_desk_queue_entry(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    test_service,
):
    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                {
                    "doctor_id": test_doctor.id,
                    "visit_date": date.today().isoformat(),
                    "department": "cardiology",
                    "services": [
                        {
                            "service_id": test_service.id,
                            "quantity": 1,
                        }
                    ],
                }
            ],
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["visit_ids"]) == 1

    visit_id = payload["visit_ids"][0]
    visit = db_session.query(Visit).filter(Visit.id == visit_id).one()
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.visit_id == visit_id)
        .one()
    )

    assert visit.status == "open"
    assert entry.source == "desk"
    assert entry.status == "waiting"
    assert entry.queue_time is not None
    assert entry.number > 0
    assert payload["queue_numbers"][str(visit_id)][0]["number"] == entry.number


@pytest.mark.integration
@pytest.mark.queue
@pytest.mark.parametrize("existing_status", ["waiting", "called", "in_service", "diagnostics"])
def test_registrar_wizard_characterization_reuses_existing_same_queue_row(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    test_service,
    existing_status,
):
    daily_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag=test_service.queue_tag,
    )
    preserved_queue_time = datetime.now(ZoneInfo("Asia/Tashkent")).replace(
        microsecond=0
    )
    existing_entry = _create_queue_entry(
        db_session,
        queue_id=daily_queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        visit_id=None,
        number=17,
        status=existing_status,
        source="online",
        queue_time=preserved_queue_time,
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                {
                    "doctor_id": test_doctor.id,
                    "visit_date": date.today().isoformat(),
                    "department": "cardiology",
                    "services": [
                        {
                            "service_id": test_service.id,
                            "quantity": 1,
                        }
                    ],
                }
            ],
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    visit_id = payload["visit_ids"][0]

    patient_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .all()
    )
    assert len(patient_entries) == 1
    assert patient_entries[0].id == existing_entry.id
    assert patient_entries[0].number == existing_entry.number
    assert patient_entries[0].queue_time == preserved_queue_time.replace(tzinfo=None)
    assert patient_entries[0].status == existing_status
    assert payload["queue_numbers"][str(visit_id)][0]["number"] == existing_entry.number


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_wizard_characterization_same_specialist_different_queue_tags_create_multiple_rows(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    test_service,
):
    diagnostics_service = _create_service(
        db_session,
        code="WIZ-DIAG-01",
        name="Wizard Diagnostics",
        queue_tag="cardiology_diagnostics",
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                {
                    "doctor_id": test_doctor.id,
                    "visit_date": date.today().isoformat(),
                    "department": "cardiology",
                    "services": [
                        {
                            "service_id": test_service.id,
                            "quantity": 1,
                        },
                        {
                            "service_id": diagnostics_service.id,
                            "quantity": 1,
                        },
                    ],
                }
            ],
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    visit_id = payload["visit_ids"][0]

    visit_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.visit_id == visit_id)
        .all()
    )
    assert len(visit_entries) == 2
    assert len(payload["queue_numbers"][str(visit_id)]) == 2

    queue_tags = {
        db_session.query(DailyQueue)
        .filter(DailyQueue.id == entry.queue_id)
        .one()
        .queue_tag
        for entry in visit_entries
    }
    assert queue_tags == {"cardiology_common", "cardiology_diagnostics"}


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_wizard_characterization_different_specialists_create_separate_rows(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    test_service,
):
    second_doctor = _create_specialist(
        db_session,
        username="wizard_second_doctor",
        email="wizard_second_doctor@test.local",
        full_name="Wizard Second Doctor",
        specialty="Dermatology",
    )
    second_service = _create_service(
        db_session,
        code="WIZ-DERM-01",
        name="Wizard Dermatology",
        queue_tag="dermatology",
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                {
                    "doctor_id": test_doctor.id,
                    "visit_date": date.today().isoformat(),
                    "department": "cardiology",
                    "services": [
                        {
                            "service_id": test_service.id,
                            "quantity": 1,
                        }
                    ],
                },
                {
                    "doctor_id": second_doctor.id,
                    "visit_date": date.today().isoformat(),
                    "department": "dermatology",
                    "services": [
                        {
                            "service_id": second_service.id,
                            "quantity": 1,
                        }
                    ],
                },
            ],
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["visit_ids"]) == 2

    patient_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .all()
    )
    assert len(patient_entries) == 2
    assert {entry.number for entry in patient_entries} == {1}
    assert {entry.source for entry in patient_entries} == {"desk"}

    assert {entry.visit_id for entry in patient_entries} == set(payload["visit_ids"])
    assert len({entry.queue_id for entry in patient_entries}) == 2


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_wizard_characterization_future_day_cart_defers_queue_creation(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    test_service,
):
    tomorrow = date.today() + timedelta(days=1)

    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                {
                    "doctor_id": test_doctor.id,
                    "visit_date": tomorrow.isoformat(),
                    "department": "cardiology",
                    "services": [
                        {
                            "service_id": test_service.id,
                            "quantity": 1,
                        }
                    ],
                }
            ],
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    visit_id = payload["visit_ids"][0]
    visit = db_session.query(Visit).filter(Visit.id == visit_id).one()
    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.visit_id == visit_id)
        .first()
    )

    assert payload["queue_numbers"] == {}
    assert entry is None
    assert visit.status == "confirmed"


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_wizard_characterization_ambiguous_same_queue_tag_claim_skips_allocation(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    test_service,
):
    second_doctor = _create_specialist(
        db_session,
        username="wizard_ambiguous_doctor",
        email="wizard_ambiguous_doctor@test.local",
        full_name="Wizard Ambiguous Doctor",
        specialty="Cardiology",
    )
    first_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag=test_service.queue_tag,
    )
    second_queue = _create_daily_queue(
        db_session,
        specialist_id=second_doctor.id,
        queue_tag=test_service.queue_tag,
    )
    _create_queue_entry(
        db_session,
        queue_id=first_queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        visit_id=None,
        number=10,
        status="waiting",
        source="online",
        queue_time=datetime.now(ZoneInfo("Asia/Tashkent")).replace(microsecond=0),
    )
    _create_queue_entry(
        db_session,
        queue_id=second_queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        visit_id=None,
        number=11,
        status="diagnostics",
        source="online",
        queue_time=datetime.now(ZoneInfo("Asia/Tashkent")).replace(microsecond=0),
    )

    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json=_cart_payload(
            patient_id=test_patient.id,
            visits=[
                {
                    "doctor_id": test_doctor.id,
                    "visit_date": date.today().isoformat(),
                    "department": "cardiology",
                    "services": [
                        {
                            "service_id": test_service.id,
                            "quantity": 1,
                        }
                    ],
                }
            ],
        ),
    )

    assert response.status_code == 200
    payload = response.json()
    visit_id = payload["visit_ids"][0]
    visit = db_session.query(Visit).filter(Visit.id == visit_id).one()
    patient_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .all()
    )

    assert payload["queue_numbers"] == {}
    assert len(patient_entries) == 2
    assert visit.status == "confirmed"
