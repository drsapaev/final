"""
Integration tests for QR queue join flow (start/complete).
Focus: public endpoints and duplicate protection.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.models.queue_profile import QueueProfile
from app.services.queue_service import QueueBusinessService


@pytest.mark.queue
def test_qr_join_flow_success(client, db_session, test_doctor, monkeypatch):
    # Ensure time restrictions never block the test
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    # Arrange: daily queue + active token
    daily_queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    db_session.commit()

    token_value = "test-qr-token"
    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token=token_value,
        day=date.today(),
        specialist_id=test_doctor.id,
        department="cardiology",
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.commit()

    # Act: start join session
    start_resp = client.post("/api/v1/queue/join/start", json={"token": token_value})
    assert start_resp.status_code == 200
    session_token = start_resp.json()["session_token"]

    # Act: complete join session
    complete_resp = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token,
            "patient_name": "Test Patient",
            "phone": "+998901112233",
        },
    )
    assert complete_resp.status_code == 200
    payload = complete_resp.json()

    # Assert
    assert payload["success"] is True
    assert payload["queue_number"] >= 1


@pytest.mark.queue
def test_qr_join_duplicate_is_not_recreated(client, db_session, test_doctor, monkeypatch):
    # Ensure time restrictions never block the test
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    daily_queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    db_session.commit()

    token_value = "test-qr-token-dup"
    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token=token_value,
        day=date.today(),
        specialist_id=test_doctor.id,
        department="cardiology",
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.commit()

    # First join
    start_resp = client.post("/api/v1/queue/join/start", json={"token": token_value})
    assert start_resp.status_code == 200
    session_token = start_resp.json()["session_token"]

    complete_resp = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token,
            "patient_name": "Test Patient",
            "phone": "+998901112233",
        },
    )
    assert complete_resp.status_code == 200
    first_number = complete_resp.json()["queue_number"]

    # Second join with same phone (should reuse existing entry)
    start_resp_2 = client.post("/api/v1/queue/join/start", json={"token": token_value})
    assert start_resp_2.status_code == 200
    session_token_2 = start_resp_2.json()["session_token"]

    complete_resp_2 = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token_2,
            "patient_name": "Test Patient",
            "phone": "+998901112233",
        },
    )
    assert complete_resp_2.status_code == 200
    second_number = complete_resp_2.json()["queue_number"]

    assert first_number == second_number

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .all()
    )
    assert len(entries) == 1


@pytest.mark.queue
def test_clinic_wide_qr_exposes_backend_selectable_specialists(
    client, db_session, test_doctor, monkeypatch
):
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    test_doctor.specialty = "cardio"
    profile = QueueProfile(
        key="cardiology",
        title="Cardiology",
        title_ru="Cardiology",
        queue_tags=["cardio", "cardiology", "cardiology_common"],
        display_order=1,
        is_active=True,
        show_on_qr_page=True,
        icon="Heart",
        color="#FF3B30",
    )
    db_session.add(profile)

    token_value = "test-clinic-wide-qr-token"
    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token=token_value,
        day=date.today(),
        specialist_id=None,
        department="clinic",
        is_clinic_wide=True,
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.commit()

    info_resp = client.get(f"/api/v1/queue/qr-tokens/{token_value}/info")
    assert info_resp.status_code == 200
    info_payload = info_resp.json()
    assert info_payload["is_clinic_wide"] is True
    assert info_payload["selectable_specialists"] == [
        {
            "id": test_doctor.id,
            "specialty": "cardiology",
            "specialty_display": "Cardiology",
            "icon": "❤️",
            "color": "#FF3B30",
            "doctor_name": "Test Cardiologist",
            "cabinet": None,
        }
    ]

    start_resp = client.post("/api/v1/queue/join/start", json={"token": token_value})
    assert start_resp.status_code == 200
    assert start_resp.json()["queue_info"]["selectable_specialists"] == info_payload[
        "selectable_specialists"
    ]
