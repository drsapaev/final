from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from app.api.v1.endpoints import queue_position as queue_position_endpoint
from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User


def _create_doctor_user(db_session, *, label: str) -> tuple[User, Doctor]:
    suffix = uuid4().hex[:10]
    user = User(
        username=f"queue_position_{label}_{suffix}",
        email=f"queue-position-{label}-{suffix}@test.local",
        full_name=f"Queue Position {label}",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty="general",
        active=True,
        cabinet="101",
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return user, doctor


def _doctor_headers(client, user: User) -> dict[str, str]:
    login_response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "doctor123"},
    )
    assert login_response.status_code == 200
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


def _create_queue_entry(db_session, *, doctor: Doctor, status: str) -> OnlineQueueEntry:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag=f"queue-position-{doctor.id}",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)

    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=1,
        patient_name="Guarded Patient",
        phone="+998901555555",
        source="desk",
        status=status,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.mark.integration
@pytest.mark.parametrize(
    ("endpoint_kind", "entry_status"),
    [
        ("position", "waiting"),
        ("call", "waiting"),
        ("diagnostics-return", "diagnostics"),
    ],
)
def test_doctor_cannot_send_queue_position_notification_for_other_doctor_entry(
    client,
    db_session,
    monkeypatch,
    endpoint_kind,
    entry_status,
):
    actor_user, actor_doctor = _create_doctor_user(db_session, label=f"actor_{endpoint_kind}")
    _other_user, other_doctor = _create_doctor_user(db_session, label=f"other_{endpoint_kind}")
    entry = _create_queue_entry(db_session, doctor=other_doctor, status=entry_status)

    calls: list[str] = []

    class FakeQueuePositionService:
        def _count_people_ahead(self, entry):
            calls.append("count_people_ahead")
            return 0

        async def notify_position_update(self, entry, people_ahead):
            calls.append("notify_position_update")
            return {"success": True, "sent": True}

        async def notify_patient_called(self, entry, cabinet_number):
            calls.append("notify_patient_called")
            return {"success": True, "sent": True}

        async def notify_diagnostics_return_needed(self, entry, specialist_name):
            calls.append("notify_diagnostics_return_needed")
            return {"success": True, "sent": True}

    monkeypatch.setattr(
        queue_position_endpoint,
        "get_queue_position_service",
        lambda db: FakeQueuePositionService(),
    )

    headers = _doctor_headers(client, actor_user)
    if endpoint_kind == "diagnostics-return":
        response = client.post(
            f"/api/v1/queue/position/notify/diagnostics-return/{entry.id}",
            headers=headers,
        )
    else:
        payload = {"entry_id": entry.id}
        if endpoint_kind == "call":
            payload["cabinet_number"] = "101"
        response = client.post(
            f"/api/v1/queue/position/notify/{endpoint_kind}",
            headers=headers,
            json=payload,
        )

    assert actor_doctor.id != other_doctor.id
    assert response.status_code == 403
    assert calls == []


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
