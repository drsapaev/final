from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import app.api.v1.endpoints.registrar_integration as registrar_integration_module
import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry


def _create_daily_queue(db_session, *, specialist_id: int) -> DailyQueue:
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


def _create_entry(
    db_session,
    *,
    queue_id: int,
    patient_id: int,
    patient_name: str,
    phone: str | None,
    number: int,
    status: str,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue_id,
        number=number,
        patient_id=patient_id,
        patient_name=patient_name,
        phone=phone,
        source="online",
        status=status,
        queue_time=datetime.now(ZoneInfo("Asia/Tashkent")).replace(microsecond=0),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.mark.unit
def test_registrar_batch_create_uses_queue_domain_boundary(
    client,
    registrar_auth_headers,
    test_patient,
    cardio_user,
    test_doctor,
    test_service,
    monkeypatch,
):
    domain_service = Mock()

    def _allocate(**kwargs):
        return SimpleNamespace(
            queue_id=kwargs["daily_queue"].id,
            number=12,
            queue_time=kwargs["queue_time"],
        )

    domain_service.allocate_ticket.side_effect = _allocate
    monkeypatch.setattr(
        registrar_integration_module,
        "_queue_domain_service",
        lambda db: domain_service,
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
    assert payload["entries"][0]["number"] == 12

    domain_service.allocate_ticket.assert_called_once()
    call = domain_service.allocate_ticket.call_args
    assert call.kwargs["allocation_mode"] == "create_entry"
    assert call.kwargs["patient_id"] == test_patient.id
    assert call.kwargs["patient_name"] == test_patient.short_name()
    assert call.kwargs["phone"] == test_patient.phone
    assert call.kwargs["source"] == "desk"
    assert call.kwargs["auto_number"] is True
    assert call.kwargs["commit"] is False
    assert call.kwargs["daily_queue"].specialist_id == test_doctor.id


@pytest.mark.unit
def test_registrar_batch_reuse_path_does_not_call_boundary(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    cardio_user,
    test_doctor,
    test_service,
    monkeypatch,
):
    existing_queue = _create_daily_queue(db_session, specialist_id=test_doctor.id)
    existing_entry = _create_entry(
        db_session,
        queue_id=existing_queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        number=7,
        status="diagnostics",
    )

    domain_service = Mock()
    monkeypatch.setattr(
        registrar_integration_module,
        "_queue_domain_service",
        lambda db: domain_service,
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
    assert payload["entries"][0]["number"] == existing_entry.number
    domain_service.allocate_ticket.assert_not_called()


@pytest.mark.unit
def test_registrar_batch_ambiguity_returns_409_before_boundary_call(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    cardio_user,
    test_doctor,
    test_service,
    monkeypatch,
):
    existing_queue = _create_daily_queue(db_session, specialist_id=test_doctor.id)
    _create_entry(
        db_session,
        queue_id=existing_queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        number=3,
        status="waiting",
    )
    _create_entry(
        db_session,
        queue_id=existing_queue.id,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        number=4,
        status="diagnostics",
    )

    domain_service = Mock()
    monkeypatch.setattr(
        registrar_integration_module,
        "_queue_domain_service",
        lambda db: domain_service,
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
    domain_service.allocate_ticket.assert_not_called()
