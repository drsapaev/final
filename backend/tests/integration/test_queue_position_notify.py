from __future__ import annotations

from datetime import date

import pytest

from app.api.v1.endpoints import queue_position as queue_position_endpoint
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry


@pytest.mark.integration
def test_diagnostics_return_notification_uses_doctor_user_profile_name(
    client,
    db_session,
    test_doctor_user,
    test_patient,
    monkeypatch,
):
    doctor = Doctor(
        user_id=test_doctor_user.id,
        specialty="general",
        active=True,
        cabinet="101",
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag="general",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)

    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=1,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="desk",
        status="diagnostics",
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    captured: dict[str, object] = {}

    class FakeQueuePositionService:
        async def notify_diagnostics_return_needed(self, entry, specialist_name):
            captured["entry_id"] = entry.id
            captured["specialist_name"] = specialist_name
            return {
                "success": True,
                "sent": True,
                "message_id": "msg-1",
                "reason": None,
                "error": None,
            }

    monkeypatch.setattr(
        queue_position_endpoint,
        "get_queue_position_service",
        lambda db: FakeQueuePositionService(),
    )

    login_response = client.post(
        "/api/v1/authentication/login",
        json={"username": test_doctor_user.username, "password": "doctor123"},
    )
    assert login_response.status_code == 200
    headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}

    response = client.post(
        f"/api/v1/queue/position/notify/diagnostics-return/{entry.id}",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["sent"] is True
    assert captured["entry_id"] == entry.id
    assert captured["specialist_name"] == test_doctor_user.full_name
