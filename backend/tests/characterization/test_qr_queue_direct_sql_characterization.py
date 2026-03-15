from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.models.queue_profile import QueueProfile
from app.models.service import Service
from app.models.user import User
from app.services.queue_service import QueueBusinessService

pytestmark = pytest.mark.postgres_pilot


def _local_now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)


def _queue_time_wall_clock(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def _create_qr_token(
    db_session,
    *,
    token_value: str,
    specialist_id: int | None,
    department: str,
    is_clinic_wide: bool = False,
) -> QueueToken:
    token = QueueToken(
        token=token_value,
        day=date.today(),
        specialist_id=specialist_id,
        department=department,
        is_clinic_wide=is_clinic_wide,
        expires_at=_local_now() + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(token)
    return token


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


def _create_doctor_with_user(
    db_session,
    *,
    username: str,
    specialty: str,
) -> Doctor:
    user = User(
        username=username,
        full_name=f"{username} full",
        email=f"{username}@example.com",
        hashed_password="test-hash",
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()

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
    queue_tag: str,
    name: str | None = None,
    is_consultation: bool = False,
) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=name or code,
        price=50000,
        active=True,
        queue_tag=queue_tag,
        is_consultation=is_consultation,
        requires_doctor=is_consultation,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


@pytest.mark.integration
@pytest.mark.queue
def test_qr_direct_sql_characterization_successful_join_creates_waiting_online_entry(
    client,
    db_session,
    test_doctor,
    monkeypatch,
):
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    daily_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
    )
    token = _create_qr_token(
        db_session,
        token_value="w2c-qr-direct-sql-single",
        specialist_id=test_doctor.id,
        department="cardiology",
    )

    start_response = client.post("/api/v1/queue/join/start", json={"token": token.token})
    assert start_response.status_code == 200
    session_token = start_response.json()["session_token"]

    complete_response = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token,
            "patient_name": "QR Single Patient",
            "phone": "+998901010101",
        },
    )

    assert complete_response.status_code == 200
    payload = complete_response.json()
    assert payload["success"] is True
    assert payload["queue_number"] >= 1

    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .one()
    )
    assert entry.number == payload["queue_number"]
    assert entry.source == "online"
    assert entry.status == "waiting"
    assert entry.queue_time is not None


@pytest.mark.integration
@pytest.mark.queue
def test_qr_direct_sql_characterization_duplicate_same_day_reuses_existing_entry(
    client,
    db_session,
    test_doctor,
    monkeypatch,
):
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    daily_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
    )
    token = _create_qr_token(
        db_session,
        token_value="w2c-qr-direct-sql-duplicate",
        specialist_id=test_doctor.id,
        department="cardiology",
    )

    start_response_1 = client.post("/api/v1/queue/join/start", json={"token": token.token})
    start_response_2 = client.post("/api/v1/queue/join/start", json={"token": token.token})
    assert start_response_1.status_code == 200
    assert start_response_2.status_code == 200

    complete_response_1 = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": start_response_1.json()["session_token"],
            "patient_name": "QR Duplicate Patient",
            "phone": "+998902020202",
        },
    )
    complete_response_2 = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": start_response_2.json()["session_token"],
            "patient_name": "QR Duplicate Patient",
            "phone": "+998902020202",
        },
    )

    assert complete_response_1.status_code == 200
    assert complete_response_2.status_code == 200
    assert complete_response_1.json()["queue_number"] == complete_response_2.json()["queue_number"]

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .all()
    )
    assert len(entries) == 1
    assert entries[0].source == "online"
    assert entries[0].queue_time is not None


@pytest.mark.integration
@pytest.mark.queue
def test_qr_direct_sql_characterization_clinic_wide_multi_specialist_join_creates_multiple_rows(
    client,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    cardiology_doctor = _create_doctor_with_user(
        db_session,
        username="w2c_qr_cardio",
        specialty="cardiology_common",
    )
    lab_doctor = _create_doctor_with_user(
        db_session,
        username="w2c_qr_lab",
        specialty="lab",
    )
    cardiology_profile = QueueProfile(
        key="w2c_cardiology",
        title="Cardiology",
        title_ru="Кардиология",
        queue_tags=["cardiology_common"],
        display_order=1,
        is_active=True,
        show_on_qr_page=True,
    )
    lab_profile = QueueProfile(
        key="w2c_lab",
        title="Laboratory",
        title_ru="Лаборатория",
        queue_tags=["lab"],
        display_order=2,
        is_active=True,
        show_on_qr_page=True,
    )
    db_session.add_all([cardiology_profile, lab_profile])
    db_session.commit()
    db_session.refresh(cardiology_profile)
    db_session.refresh(lab_profile)

    token = _create_qr_token(
        db_session,
        token_value="w2c-qr-clinic-wide",
        specialist_id=None,
        department="clinic",
        is_clinic_wide=True,
    )

    start_response = client.post("/api/v1/queue/join/start", json={"token": token.token})
    assert start_response.status_code == 200
    session_token = start_response.json()["session_token"]

    complete_response = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token,
            "patient_name": "QR Clinic Patient",
            "phone": "+998903030303",
            "specialist_ids": [cardiology_profile.id, lab_profile.id],
        },
    )

    assert complete_response.status_code == 200
    payload = complete_response.json()
    assert payload["success"] is True
    assert len(payload["entries"]) == 2

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.phone == "+998903030303")
        .order_by(OnlineQueueEntry.id.asc())
        .all()
    )
    assert len(entries) == 2
    assert all(entry.source == "online" for entry in entries)
    assert all(entry.status == "waiting" for entry in entries)
    assert all(entry.queue_time is not None for entry in entries)

    queue_tags = {
        db_session.query(DailyQueue)
        .filter(DailyQueue.id == entry.queue_id)
        .first()
        .queue_tag
        for entry in entries
    }
    assert queue_tags == {"w2c_cardiology", "w2c_lab"}


@pytest.mark.integration
@pytest.mark.queue
def test_qr_direct_sql_characterization_full_update_first_fill_uses_raw_next_number_and_current_time(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    test_service,
):
    original_queue_time = _local_now() - timedelta(hours=2)
    original_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
    )
    lab_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="lab",
    )
    _create_service(
        db_session,
        code="W2C-QR-LAB-EXISTING",
        queue_tag="lab",
        name="Existing lab marker",
    )
    existing_lab_entry = OnlineQueueEntry(
        queue_id=lab_queue.id,
        number=7,
        patient_id=None,
        patient_name="Existing Lab Patient",
        phone="+998909999999",
        source="desk",
        status="waiting",
        queue_time=datetime.now(ZoneInfo("Asia/Tashkent")) - timedelta(minutes=30),
    )
    db_session.add(existing_lab_entry)
    db_session.flush()

    lab_service = _create_service(
        db_session,
        code="W2C-QR-LAB-NEW",
        queue_tag="lab",
        name="Lab new service",
    )

    original_entry = OnlineQueueEntry(
        queue_id=original_queue.id,
        number=1,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
        queue_time=original_queue_time,
        services=[],
        service_codes=[],
        total_amount=0,
    )
    db_session.add(original_entry)
    db_session.commit()
    db_session.refresh(original_entry)

    response = client.put(
        f"/api/v1/queue/online-entry/{original_entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": test_patient.short_name(),
                "phone": test_patient.phone,
                "birth_year": 1990,
                "address": "QR address",
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [
                {"service_id": test_service.id, "quantity": 1},
                {"service_id": lab_service.id, "quantity": 1},
            ],
            "all_free": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .order_by(OnlineQueueEntry.id.asc())
        .all()
    )
    assert len(entries) == 2

    db_session.refresh(original_entry)
    assert original_entry.number == 1
    assert _queue_time_wall_clock(original_entry.queue_time) == _queue_time_wall_clock(
        original_queue_time
    )
    assert original_entry.source == "online"

    new_entry = next(entry for entry in entries if entry.id != original_entry.id)
    assert new_entry.queue_id == lab_queue.id
    assert new_entry.number == 8
    assert new_entry.source == "online"
    assert new_entry.status == "waiting"
    assert new_entry.birth_year == 1990
    assert new_entry.address == "QR address"
    assert new_entry.queue_time is not None
    assert new_entry.queue_time != original_entry.queue_time
